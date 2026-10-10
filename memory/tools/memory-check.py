#!/usr/bin/env python3
"""memory-check.py - 记忆系统自检

检查记忆系统是否在自欺：路径是否真实存在、证据状态是否有依据、
是否混入秘密、是否有内容过期。

用法:
    python memory-check.py                 # 检查默认根目录
    python memory-check.py    # 或 --root <记忆库目录>
    python memory-check.py --json          # 机器可读输出

退出码:
    0 = 全部通过
    1 = 有 ERROR（必须处理）
    2 = 只有 WARN（可以继续，但要知情）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

from config import describe_root, resolve_root  # 同目录，支持插拔式根目录解析

# ---------------------------------------------------------------- 常量

SECRET_PATTERNS = [
    (r"sk-[A-Za-z0-9]{16,}", "OpenAI 风格 key"),
    (r"mpg-[A-Za-z0-9]{8,}", "MemOS key"),
    (r"ghp_[A-Za-z0-9]{20,}", "GitHub token"),
    (r"gho_[A-Za-z0-9]{20,}", "GitHub OAuth token"),
    (r"AIza[A-Za-z0-9_\-]{30,}", "Google API key"),
    (r"xox[baprs]-[A-Za-z0-9\-]{10,}", "Slack token"),
    (r"Bearer\s+[A-Za-z0-9\-._~+/]{20,}", "Bearer token"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "私钥"),
    (
        r"(?i)\b(api[_-]?key|apikey|secret|passwd|password|access[_-]?token)\b\s*[:=]\s*[\"']?[A-Za-z0-9\-._]{12,}",
        "疑似凭据赋值",
    ),
]

VALID_STATUS = {"active", "paused", "completed", "archived"}
VALID_EVIDENCE_STATE = {
    "planned", "changed", "ran", "test-passed", "independently-verified",
    "unknown",
}
VALID_SOURCE = {
    "user-explicit", "file-observed", "test-run", "derived", "legacy-summary",
}

# 声称已达到这些状态时，正文必须能指向证据
NEEDS_EVIDENCE = {"test-passed", "independently-verified"}

# 旧资料里已知会出现的失效引用，出现即报错
KNOWN_STALE = [
    r"Desktop[/\\]DeepSeek-管辖区",
    r"DEEPSEEK-管辖区",
]

REQUIRED_STATE_FIELDS = ["project", "title", "status", "updated_at", "source_of_truth"]

# 常驻上下文预算（每次新对话必读的文件）
# 见 INDEX.md 的「常驻预算」：只有 AGENTS.md 与本文件属于常驻。
RESIDENT_BUDGET_BYTES = 10 * 1024

# 可接受的 evidence 指向写法（接受两种，避免误报）：
#   evidence: D:\...        （独立一行）
#   `evidence:`             （行内代码引用）
EVIDENCE_MARKER = re.compile(r"evidence\s*:|evidence:", re.I)


STALE_AFTER_DAYS = 120

SKIP_DIRS = {"backup", "__pycache__", ".git"}
TEXT_EXT = {".md", ".txt", ".json", ".yml", ".yaml", ".csv"}


class Report:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, level: str, check: str, message: str, path: str = "") -> None:
        self.items.append({"level": level, "check": check, "message": message, "path": path})

    def error(self, check: str, message: str, path: str = "") -> None:
        self.add("ERROR", check, message, path)

    def warn(self, check: str, message: str, path: str = "") -> None:
        self.add("WARN", check, message, path)

    def ok(self, check: str, message: str) -> None:
        self.add("OK", check, message)

    @property
    def errors(self) -> int:
        return sum(1 for i in self.items if i["level"] == "ERROR")

    @property
    def warns(self) -> int:
        return sum(1 for i in self.items if i["level"] == "WARN")


# ---------------------------------------------------------------- 工具

def walk_text_files(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if os.path.splitext(name)[1].lower() in TEXT_EXT:
                yield os.path.join(dirpath, name)


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def parse_frontmatter(text: str) -> dict | None:
    """解析文件开头的 YAML frontmatter（只支持扁平 key: value）。"""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    block = text[3:end]
    data: dict[str, str] = {}
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        data[key.strip()] = value.strip().strip("\"'")
    return data


def rel(root: str, path: str) -> str:
    try:
        return os.path.relpath(path, root)
    except ValueError:
        return path


# ---------------------------------------------------------------- 检查项

def check_pii(root: str, rep: Report) -> None:
    """秘密扫描。"""
    hits = 0
    for path in walk_text_files(root):
        text = read_text(path)
        for pattern, label in SECRET_PATTERNS:
            for m in re.finditer(pattern, text):
                hits += 1
                line_no = text[: m.start()].count("\n") + 1
                rep.error("secrets", f"{label} 命中（第 {line_no} 行）", rel(root, path))
    if hits == 0:
        rep.ok("secrets", "未发现任何疑似凭据")


def check_imports_untouched(root: str, rep: Report) -> None:
    """确保 import/ 目录没有被加上整理注记而破坏完整性。"""
    import_dir = os.path.join(root, "import")
    if not os.path.isdir(import_dir):
        rep.warn("import-integrity", "找不到 import/ 目录")
        return
    # 交接包自带 manifest：直接复验
    manifest = None
    for dirpath, _dirs, files in os.walk(import_dir):
        if "15_MANIFEST_SHA256.md" in files:
            manifest = os.path.join(dirpath, "15_MANIFEST_SHA256.md")
            break
    if manifest is None:
        # 没有 import 资料（或资料没带清单）是正常情况，不是缺陷
        rep.ok("import-integrity", "无带清单的 import 资料，跳过（正常）")
        return

    import hashlib

    base = os.path.dirname(manifest)
    ok = bad = miss = 0
    for line in read_text(manifest).splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) != 3:
            continue
        relpath, size, digest = parts
        if not (relpath.startswith("`") and relpath.endswith("`")):
            continue
        relpath = relpath.strip("`")
        digest = digest.strip("`").upper()
        if len(digest) != 64:
            continue
        target = os.path.join(base, relpath.replace("/", os.sep))
        if not os.path.isfile(target):
            miss += 1
            rep.error("import-integrity", f"manifest 列出的文件不存在: {relpath}")
            continue
        h = hashlib.sha256()
        with open(target, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        if h.hexdigest().upper() == digest and os.path.getsize(target) == int(size):
            ok += 1
        else:
            bad += 1
            rep.error(
                "import-integrity",
                f"与 manifest 不符（可能被整理注记污染）: {relpath}",
            )
    if bad == 0 and miss == 0 and ok:
        rep.ok("import-integrity", f"交接包 {ok}/{ok} 项哈希与大小全部匹配")


def check_stale_refs(root: str, rep: Report) -> None:
    """检查是否还有失效的旧路径引用。

    豁免范围：
      - import/            历史资料，保留原样是正确的
      - README.md          可能说明这些引用已失效
      - CONSOLIDATION-NOTES.md / ARCHITECTURE.md
                           这两个文件本身就是在**记录**这些失效引用与教训
    """
    exempt_prefixes = (os.path.join(root, "import"),)
    exempt_names = {"CONSOLIDATION-NOTES.md", "ARCHITECTURE.md", "README.md"}
    hits = 0
    for path in walk_text_files(root):
        if path.startswith(exempt_prefixes):
            continue
        if os.path.basename(path) in exempt_names:
            continue
        text = read_text(path)
        for pattern in KNOWN_STALE:
            if re.search(pattern, text):
                hits += 1
                rep.error(
                    "stale-paths",
                    f"发现失效引用 {pattern}",
                    rel(root, path),
                )
    if hits == 0:
        rep.ok("stale-paths", "元数据层无失效路径引用")


def strip_inline_code(text: str) -> str:
    """去掉行内代码（`...`）与代码块，避免把“引用示例”当成真实标记。

    例如变更记录里写「原文写作 `[status: derived | source: derived]`」
    是在**描述**一个错误，不是在犯这个错误。
    """
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"`[^`\n]*`", "``", text)
    return text


def check_project_states(root: str, rep: Report) -> None:
    """校验每个项目的 STATE.md。"""
    projects_dir = os.path.join(root, "projects")
    if not os.path.isdir(projects_dir):
        rep.warn("project-state", "尚无 projects/ 目录")
        return

    found = 0
    for slug in sorted(os.listdir(projects_dir)):
        # 下划线开头是模板/占位，不是真实项目，跳过校验
        if slug.startswith("_"):
            continue
        if slug.startswith("."):
            continue
        state = os.path.join(projects_dir, slug, "STATE.md")
        if not os.path.isfile(state):
            rep.warn("project-state", f"{slug}/ 下没有 STATE.md")
            continue
        found += 1
        raw_text = read_text(state)
        rpath = rel(root, state)

        # frontmatter 与结构性检查用原文
        text = raw_text
        # 标记校验用去代码后的文本
        marker_text = strip_inline_code(raw_text)

        fm = parse_frontmatter(text)
        if fm is None:
            rep.error("project-state", "缺少 frontmatter", rpath)
        else:
            for field in REQUIRED_STATE_FIELDS:
                if not fm.get(field):
                    rep.error("project-state", f"frontmatter 缺字段 `{field}`", rpath)
            if fm.get("status") and fm["status"] not in VALID_STATUS:
                rep.error(
                    "project-state",
                    f"status `{fm['status']}` 不合法，应为 {sorted(VALID_STATUS)}",
                    rpath,
                )
            updated = fm.get("updated_at", "")
            m = re.match(r"(\d{4})-(\d{2})-(\d{2})", updated)
            if m:
                try:
                    dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                    age = (datetime.now() - dt).days
                    if age > STALE_AFTER_DAYS:
                        rep.warn(
                            "freshness",
                            f"updated_at 距今 {age} 天，可能已过期",
                            rpath,
                        )
                except ValueError:
                    rep.error("project-state", f"updated_at 日期非法: {updated}", rpath)
            elif updated:
                rep.error("project-state", f"updated_at 格式无法解析: {updated}", rpath)

        # 每条带状态标记的声明，校验状态词与来源
        # 支持两种写法：
        #   合并式  [status: ran | source: test-run]
        #   分离式  [status: ran]  [source: test-run]   <- 推荐
        combined = re.findall(
            r"\[status:\s*([a-z\-]+)\s*\|\s*source:\s*([a-z\-]+)\s*\]", marker_text
        )
        lone_status = re.findall(r"\[status:\s*([a-z\-]+)\s*\]", marker_text)
        lone_source = re.findall(r"\[source:\s*([a-z\-]+)\s*\]", marker_text)

        # 位置错配检测：分离式写法下把来源词写进 status，或反之
        for word in lone_status:
            if word in VALID_SOURCE and word not in VALID_EVIDENCE_STATE:
                rep.error(
                    "evidence-ladder",
                    f"分离式：`[status: {word}]` — `{word}` 是**来源词**，"
                    f"不能放 status 位置；应为 `[status: 某状态]` `[source: {word}]`",
                    rpath,
                )
        for word in lone_source:
            if word in VALID_EVIDENCE_STATE and word not in VALID_SOURCE:
                rep.error(
                    "evidence-ladder",
                    f"分离式：`[source: {word}]` — `{word}` 是**状态词**，"
                    f"不能放 source 位置；应为 `[status: {word}]` `[source: 某来源]`",
                    rpath,
                )

        # 数量配平：分离式写法下，状态与来源应成对出现
        n_status = len(lone_status)
        n_source = len(lone_source)
        n_combined = len(combined)
        if (n_status or n_source) and n_status != n_source:
            rep.error(
                "evidence-ladder",
                f"`[status:]` 有 {n_status} 个、`[source:]` 有 {n_source} 个，"
                f"数量不配对（{n_combined} 条用的是合并式）— 每条声明都该同时有状态和来源",
                rpath,
            )

        markers = combined + list(zip(lone_status, lone_source))
        for state_word, source_word in markers:
            # 位置错配（合并式写法同样会犯）
            if state_word in VALID_SOURCE and state_word not in VALID_EVIDENCE_STATE:
                rep.error(
                    "evidence-ladder",
                    f"合并式：`[status: {state_word} | source: ...]` — `{state_word}` 是"
                    f"**来源词**，被写进了 status 位置。应为 "
                    f"`[status: 某状态 | source: {state_word}]`",
                    rpath,
                )
                continue
            if source_word in VALID_EVIDENCE_STATE and source_word not in VALID_SOURCE:
                rep.error(
                    "evidence-ladder",
                    f"合并式：`[status: ... | source: {source_word}]` — `{source_word}` 是"
                    f"**状态词**，被写进了 source 位置。应为 "
                    f"`[status: {source_word} | source: 某来源]`",
                    rpath,
                )
                continue
            if state_word not in VALID_EVIDENCE_STATE:
                rep.error(
                    "evidence-ladder",
                    f"状态词 `{state_word}` 不在允许集合内 {sorted(VALID_EVIDENCE_STATE)}",
                    rpath,
                )
            if source_word not in VALID_SOURCE:
                rep.error(
                    "evidence-ladder",
                    f"来源词 `{source_word}` 不在允许集合内 {sorted(VALID_SOURCE)}",
                    rpath,
                )
            # 关键规则：声称测试通过/独立验证，必须能指向证据
            # 接受两种写法：独立一行 `evidence:` 或行内代码 `evidence:`
            if state_word in NEEDS_EVIDENCE and not EVIDENCE_MARKER.search(text):
                rep.error(
                    "evidence-ladder",
                    f"声称 `{state_word}` 但全文找不到任何 `evidence:` 指向",
                    rpath,
                )

        # 数值型断言必须标来源（防止"测试通过"式空口声明）
        if re.search(r"\d+\s*(项|个)?\s*(通过|passed)", marker_text, re.I):
            if not EVIDENCE_MARKER.search(text):
                rep.warn(
                    "unsourced-claim",
                    "文中出现“通过”类断言但无 evidence 指向",
                    rpath,
                )

        if "## 待核验" not in text and "待核验" not in text:
            rep.warn("honesty", "没有“待核验”区块，可能过度自信", rpath)

    if found:
        rep.ok("project-state", f"校验了 {found} 个项目 STATE.md")


def check_root_docs(root: str, rep: Report) -> None:
    for name in ("INDEX.md", "SCHEMA.md"):
        p = os.path.join(root, name)
        if not os.path.isfile(p):
            rep.error("structure", f"缺少核心文件 {name}")
    # 按需文件：缺了不影响可用性，但要提醒
    for name in ("GLOBAL_RULES.md", "ARCHITECTURE.md"):
        if not os.path.isfile(os.path.join(root, name)):
            rep.warn("structure", f"缺少按需文件 {name}")
    if not os.path.isdir(os.path.join(root, "events")):
        rep.warn("structure", "尚无 events/ 目录（决策与冲突日志）")
    for sub, name in (("events", "README.md"), ("import", "README.md")):
        if not os.path.isfile(os.path.join(root, sub, name)):
            rep.warn("structure", f"缺少 {sub}/{name}（增长/保留策略）")
    rep.ok("structure", "核心文件齐备")


def check_resident_budget(root: str, rep: Report) -> None:
    """常驻上下文预算：只有 AGENTS.md + INDEX.md 属于每次必读。

    超过预算就报警——提醒把长内容搬到按需文件，
    而不是让它悄悄膨胀（这正是本系统要防的那件事）。
    """
    workspace = os.path.dirname(os.path.abspath(root))
    resident = [
        os.path.join(workspace, "AGENTS.md"),
        os.path.join(root, "INDEX.md"),
    ]
    total = 0
    detail = []
    for p in resident:
        if os.path.isfile(p):
            n = os.path.getsize(p)
            total += n
            detail.append(f"{os.path.basename(p)} {n:,}B")

    if total == 0:
        rep.error("resident-budget", "找不到任何常驻文件")
        return

    pct = 100 * total / RESIDENT_BUDGET_BYTES
    if total > RESIDENT_BUDGET_BYTES:
        rep.warn(
            "resident-budget",
            f"常驻上下文 {total:,} B ≈ {pct:.0f}% 预算（上限 {RESIDENT_BUDGET_BYTES:,} B）"
            f" — 已超支，请把长内容搬到按需文件（SCHEMA/ARCHITECTURE/GLOBAL_RULES/projects）。"
            f" 明细：{'，'.join(detail)}",
        )
    else:
        rep.ok(
            "resident-budget",
            f"常驻上下文 {total:,} B ≈ {pct:.0f}% 预算（{'，'.join(detail)}）",
        )


def check_agents_entry(root: str, rep: Report) -> None:
    """确认自动入口存在，且指向真实的记忆根目录。"""
    workspace = os.path.dirname(os.path.abspath(root))
    agents = os.path.join(workspace, "AGENTS.md")
    if not os.path.isfile(agents):
        rep.error("entry-point", f"找不到自动入口 {agents} — AI 不会自动读到记忆")
        return
    text = read_text(agents)
    if os.path.abspath(root) not in text and "memory" not in text:
        rep.error("entry-point", "AGENTS.md 没有指向记忆根目录", rel(workspace, agents))
        return
    rep.ok("entry-point", "自动入口 AGENTS.md 存在并指向记忆系统")


def check_secrets_and_stale(root: str, rep: Report) -> None:
    check_pii(root, rep)
    check_stale_refs(root, rep)


# ---------------------------------------------------------------- 主流程

def main() -> int:
    ap = argparse.ArgumentParser(description="记忆系统自检")
    ap.add_argument(
        "--root",
        default=None,
        help="记忆根目录。省略时依次看 $MEMORY_ROOT、.memory-root 文件、./memory",
    )
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    root = resolve_root(args.root)
    if not os.path.isdir(root):
        print(f"记忆根目录不存在: {root}\n  来源: {describe_root(root)}", file=sys.stderr)
        print("  用 --root、$MEMORY_ROOT 或 .memory-root 指定记忆库位置。", file=sys.stderr)
        return 1

    rep = Report()
    check_root_docs(root, rep)
    check_resident_budget(root, rep)
    check_agents_entry(root, rep)
    check_secrets_and_stale(root, rep)
    check_project_states(root, rep)
    check_imports_untouched(root, rep)

    if args.json:
        print(json.dumps(
            {"root": root, "errors": rep.errors, "warns": rep.warns, "items": rep.items},
            ensure_ascii=False, indent=2))
    else:
        order = {"ERROR": 0, "WARN": 1, "OK": 2}
        for item in sorted(rep.items, key=lambda i: order[i["level"]]):
            tag = {"ERROR": "ERROR", "WARN": " WARN", "OK": "   OK"}[item["level"]]
            loc = f"  [{item['path']}]" if item["path"] else ""
            print(f"{tag}  {item['check']:<16} {item['message']}{loc}")
        print()
        print(f"ERROR: {rep.errors}   WARN: {rep.warns}")

    if rep.errors:
        return 1
    if rep.warns:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
