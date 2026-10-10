#!/usr/bin/env python3
"""config.py - 解析记忆库根目录，让工具可以插拔式使用。

解析优先级（先命中先用）：
  1. 环境变量 `MEMORY_ROOT`
  2. 命令行 `--root`
  3. 仓库根的 `.memory-root` 文件（一行，存相对或绝对路径）
  4. 默认 `./memory`

这样别人 clone 下来：
  - 不用改代码就能用（放 .memory-root 或设环境变量）
  - 换目录也不用改一行 Python
"""
from __future__ import annotations

import os
import sys

CONFIG_FILENAME = ".memory-root"
ENV_VAR = "MEMORY_ROOT"


def _repo_root() -> str:
    """本文件位于 <repo>/memory/tools/config.py，仓库根要上溯三层。"""
    tools = os.path.dirname(os.path.abspath(__file__))   # <repo>/memory/tools
    mem = os.path.dirname(tools)                          # <repo>/memory
    return os.path.dirname(mem)                           # <repo>


def resolve_root(cli_root: str | None = None) -> str:
    """按优先级解析记忆库根目录，返回绝对路径。"""
    # 1. 环境变量
    env = os.environ.get(ENV_VAR)
    if env and env.strip():
        return os.path.abspath(env.strip())

    # 2. 命令行
    if cli_root and cli_root.strip():
        return os.path.abspath(cli_root.strip())

    # 3. .memory-root 文件
    repo = _repo_root()
    cfg = os.path.join(repo, CONFIG_FILENAME)
    if os.path.isfile(cfg):
        with open(cfg, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if not os.path.isabs(line):
                    line = os.path.join(repo, line)
                return os.path.abspath(line)

    # 4. 默认
    return os.path.abspath(os.path.join(repo, "memory"))


def add_root_argument(parser) -> None:
    """给 argparse 加统一的 --root 参数。"""
    parser.add_argument(
        "--root",
        default=None,
        help=f"记忆库根目录。省略时依次看 ${ENV_VAR}、.memory-root 文件、./memory",
    )


def describe_root(root: str) -> str:
    """给用户看的一行来源说明，便于排查'为什么读的是这个目录'。"""
    if os.environ.get(ENV_VAR):
        return f"来自环境变量 ${ENV_VAR}"
    repo = _repo_root()
    if os.path.isfile(os.path.join(repo, CONFIG_FILENAME)):
        return f"来自 {CONFIG_FILENAME}"
    if os.path.abspath(root) == os.path.abspath(os.path.join(repo, "memory")):
        return "默认 ./memory"
    return "来自 --root"


if __name__ == "__main__":
    r = resolve_root(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"root       : {r}")
    print(f"来源       : {describe_root(r)}")
    print(f"是否存在   : {os.path.isdir(r)}")
