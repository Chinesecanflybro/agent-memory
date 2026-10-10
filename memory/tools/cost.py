#!/usr/bin/env python3
"""cost.py - 报告记忆库的上下文开销与磁盘占用。

存在的理由：这个记忆系统的核心目标是**节省 token**。
但常驻文件很容易不知不觉膨胀（我自己就这么干过一次，26 KB）。
所以把"算大小"变成一条命令，而不是靠自觉。

用法:
    python cost.py                 # 默认根目录 D:\\DSH\\memory
    python cost.py            # 或 --root <记忆库目录>

退出码: 0 = 常驻在预算内   2 = 常驻超预算
"""
from __future__ import annotations

import argparse
import os
import sys

from config import describe_root, resolve_root  # 同目录，支持插拔式根目录解析

BUDGET_BYTES = 10 * 1024

# 常驻：每次新对话必读
RESIDENT = ["{ws}/AGENTS.md", "{root}/INDEX.md"]
# 按需：用到才读，不计入常驻预算
ON_DEMAND = [
    "{root}/SCHEMA.md",
    "{root}/GLOBAL_RULES.md",
    "{root}/ARCHITECTURE.md",
]


def size(p: str) -> int:
    return os.path.getsize(p) if os.path.isfile(p) else 0


def approx_tokens(p: str) -> int:
    """中文为主，粗略按字符数估 token（CJK 约 1 字 1 token）。"""
    if not os.path.isfile(p):
        return 0
    with open(p, encoding="utf-8", errors="replace") as f:
        return len(f.read())


def dir_size(p: str) -> tuple[int, int]:
    total = 0
    count = 0
    for dirpath, _dirs, files in os.walk(p):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(dirpath, name))
                count += 1
            except OSError:
                pass
    return total, count


def main() -> int:
    ap = argparse.ArgumentParser(description="记忆库开销报告")
    ap.add_argument(
        "--root",
        default=None,
        help="记忆根目录。省略时依次看 $MEMORY_ROOT、.memory-root 文件、./memory",
    )
    args = ap.parse_args()

    root = resolve_root(args.root)
    workspace = os.path.dirname(root)
    ctx = {"ws": workspace, "root": root}

    print("=" * 66)
    print("常驻上下文（每次新对话必读）")
    print("=" * 66)
    total = 0
    toks = 0
    for tpl in RESIDENT:
        p = tpl.format(**ctx)
        n = size(p)
        t = approx_tokens(p)
        total += n
        toks += t
        mark = "" if n else "  (缺失!)"
        print(f"  {os.path.basename(p):<22} {n:>7,} B   约 {t:>6,} token{mark}")
    pct = 100 * total / BUDGET_BYTES
    flag = "✅ 在预算内" if total <= BUDGET_BYTES else "⚠️ 超预算"
    print(f"  {'合计':<22} {total:>7,} B   约 {toks:>6,} token")
    print(f"  {'预算':<22} {BUDGET_BYTES:>7,} B   使用 {pct:.0f}%   {flag}")

    print()
    print("=" * 66)
    print("按需读取（不计入常驻预算）")
    print("=" * 66)
    for tpl in ON_DEMAND:
        p = tpl.format(**ctx)
        n = size(p)
        print(f"  {os.path.basename(p):<22} {n:>7,} B   约 {approx_tokens(p):>6,} token")

    proj_dir = os.path.join(root, "projects")
    if os.path.isdir(proj_dir):
        files = []
        for d in sorted(os.listdir(proj_dir)):
            s = os.path.join(proj_dir, d, "STATE.md")
            if os.path.isfile(s):
                files.append((d, os.path.getsize(s)))
        print(f"  {'projects/<项目>/STATE.md':<22} {len(files)} 个，平均 "
              f"{sum(n for _, n in files)//max(1,len(files)):,} B（只读当前那一个）")

    print()
    print("=" * 66)
    print("磁盘占用")
    print("=" * 66)
    authored = 0
    authored_n = 0
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ("import", "backup")]
        for name in files:
            try:
                authored += os.path.getsize(os.path.join(dirpath, name))
                authored_n += 1
            except OSError:
                pass
    print(f"  记忆本体（不含 import/backup）  {authored:>10,} B   {authored_n} 个文件")
    for sub in ("import", "backup", "evidence"):
        p = os.path.join(root, sub)
        if os.path.isdir(p):
            n, c = dir_size(p)
            print(f"  {sub + '/':<32} {n:>10,} B   {c} 个文件")

    print()
    print("提示：常驻超预算时，把长表格/清单/推导搬到 SCHEMA.md、ARCHITECTURE.md 或 projects/。")
    return 0 if total <= BUDGET_BYTES else 2


if __name__ == "__main__":
    sys.exit(main())
