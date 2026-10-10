---
project: <slug>
title: <项目显示名>
status: active
updated_at: 2026-01-01T00:00:00+08:00
root: null
source_of_truth: <哪个文件或命令是权威依据>
---

# <项目显示名> — 项目现状

> 复制本目录改名使用，并在 `INDEX.md` 的项目速查里登记一行。
> 每条事实按 `SCHEMA.md` 标注 `[status: …]` `[source: …]`。**两个都要有。**

---

## 1. 目标

- <一句话目标> `[status: planned]` `[source: user-explicit]`

## 2. 已知困难 / 约束

- <...> `[status: unknown]` `[source: legacy-summary]`

## 3. 硬约束（用户明确要求，优先遵守）

- <...> `[status: planned]` `[source: user-explicit]`

## 4. 已完成

> ⚠️ 标 `test-passed` 或 `independently-verified` 时**必须**给出 `evidence:` 指向。

- <...> `[status: ran]` `[source: test-run]`
  evidence: <日志文件路径 或 命令与退出码>

## 5. 未完成 / 阻塞

- <...> `[status: planned]`

## 6. 已尝试但失败的方法

> 记这个是为了**避免重复踩坑**，也是最有价值的一节。

- <方法> → 失败原因：<...>

## 7. 待核验（重要 — 不要跳过本节）

| # | 待核验事项 | 为什么重要 |
|---|---|---|
| 1 | | |

**已知缺失的资料**

- <找不到的东西> —— **找不到就说找不到，不要编造**

## 8. 下一步 + 验收标准

**下一步**

1.

**验收标准**

- <可证伪的判据，不是"看起来好了">

## 9. 变更记录

- 2026-01-01：建立本文件。
