#!/usr/bin/env python3
"""baseline.py - 为目录建立 SHA-256 基线，并可随时复验。

用途：DSH 工作区外（如 F 盘）的项目没有 git，无法用 commit 追溯版本。
本工具用文件哈希基线代替，但有**两种截然不同的用途，解释方式相反**：

  A. 冻结保护（freeze）
     目录不应再被任何人改动。verify 报任何差异 = **报警**，必须查。
     例：已验收的版本快照。

  B. 变更侦测（change detection）
     目录**正被另一个会话/人并发写入**。verify 报差异 = **正常工作**，
     用来回答"对方改了什么"。
     例：另一对话正在写的代码目录。

⚠️ 建基线前先想清楚是 A 还是 B，并写进对应的项目 STATE.md，
   否则后来的人会把 B 的正常差异误当成 A 的损坏报警。

用法:
    # 建立基线
    python baseline.py build <目录> --out <基线文件>.json

    # 复验（A：一致才算通过；B：列出差异即为目的）
    python baseline.py verify <目录> --baseline <基线文件>.json

⚠️ 改重要目录的 ACL 之前，先确认 `/deny` 不会顶掉继承的读权限——
   见 ARCHITECTURE.md「踩过的坑」第 (3) 条。

退出码: 0 = 一致   1 = 有差异（新增/修改/删除）   2 = 用法或读取错误
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime

from config import describe_root, resolve_root  # 同目录，支持插拔式根目录解析

SKIP_DIRS = {"node_modules", "dist", ".git", "__pycache__", ".cache"}
MAX_BYTES = 64 * 1024 * 1024  # 超过 64MB 的文件只记大小，不记哈希（避免耗时）


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scan(root: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            p = os.path.join(dirpath, name)
            rel = os.path.relpath(p, root)
            try:
                size = os.path.getsize(p)
                mtime = datetime.fromtimestamp(os.path.getmtime(p)).isoformat(timespec="seconds")
                if size <= MAX_BYTES:
                    out[rel] = {"size": size, "sha256": sha256(p), "mtime": mtime}
                else:
                    out[rel] = {"size": size, "sha256": None, "mtime": mtime,
                                "note": "too large; size only"}
            except OSError as e:
                out[rel] = {"error": str(e)}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="目录哈希基线工具")
    ap.add_argument("action", choices=["build", "verify"])
    ap.add_argument("root", nargs="?", default=None,
                    help="要建立/复验基线的目录。省略时用记忆根目录")
    ap.add_argument("--baseline", help="verify 时必填；build 时可用 --out")
    ap.add_argument("--out", help="build 时的输出 json 路径")
    args = ap.parse_args()

    root = resolve_root(args.root)
    if not os.path.isdir(root):
        print(f"目录不存在: {root}\n  来源: {describe_root(root)}", file=sys.stderr)
        return 2

    if args.action == "build":
        files = scan(root)
        data = {
            "root": root,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "file_count": len(files),
            "total_bytes": sum(v.get("size", 0) for v in files.values()),
            "files": files,
        }
        out = args.out or os.path.join(os.path.dirname(root), "_baseline.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        print(f"基线已建立: {out}")
        print(f"  目录      : {root}")
        print(f"  文件数    : {len(files)}")
        print(f"  总字节    : {data['total_bytes']:,}")
        return 0

    # verify
    if not args.baseline:
        print("verify 需要 --baseline", file=sys.stderr)
        return 2
    with open(args.baseline, encoding="utf-8") as f:
        base = json.load(f)
    if os.path.abspath(base["root"]) != root:
        print(f"警告：基线记录的根目录是 {base['root']}，与传入的 {root} 不同。", file=sys.stderr)

    old = base["files"]
    new = scan(root)

    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(
        rel for rel in (set(old) & set(new))
        if old[rel].get("sha256") != new[rel].get("sha256")
        or old[rel].get("size") != new[rel].get("size")
    )

    print(f"基线建立于 : {base['created_at']}  ({base['file_count']} 文件)")
    print(f"当前目录   : {root}  ({len(new)} 文件)")
    print()
    if not (added or removed or changed):
        print("✅ 完全一致 —— 受保护内容未被改动。")
        return 0

    print(f"⚠️ 发现差异：新增 {len(added)} / 修改 {len(changed)} / 删除 {len(removed)}")
    for rel in changed[:40]:
        print(f"  修改  {rel}")
    for rel in added[:40]:
        print(f"  新增  {rel}")
    for rel in removed[:40]:
        print(f"  删除  {rel}")
    if len(changed) + len(added) + len(removed) > 120:
        print("  …（更多差异已省略）")
    return 1


if __name__ == "__main__":
    sys.exit(main())
