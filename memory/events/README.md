# events/ — 事件与决策日志（有界增长策略）

> **按需读取。** 平时不必读本文件；**要往 `events/` 写东西时读一遍**。

---

## 为什么需要策略

`events/` 是**追加式**日志——这本身是对的（历史不可篡改）。
但它默认会**无限增长**，而在意"记忆库不要无限扩增"。

**解法不是删除，而是分层：让写入无限、让读取有界。**

## 目录结构

```
events/
  README.md                 ← 本文件（策略，按需读）
  *.json                    ← 活动区：最近一个季度的事件（会被读取）
  archive/
    YYYY.jsonl              ← 归档区：每年一个文件（永不删除，默认不读）
```

## 规则

| 规则 | 说明 |
|---|---|
| **活动区只保留最近 1 个季度** | 更早的移到 `archive\<年>.jsonl` |
| **归档永不删除** | 归档是历史证据，删了就无法追溯 |
| **默认不读归档** | 需要追溯时才 `grep archive\` |
| **一年最多一个归档文件** | 避免归档区自身碎片化膨胀 |
| **单个事件文件保持小** | 一条事件一个文件，便于独立追溯 |

## 什么时候归档

**任一条件满足就归档**（不必等）：

- 活动区文件数 > 20
- 活动区总大小 > 200 KB
- 距上次归档 > 3 个月

## 归档怎么做

把活动区里**超出最近一个季度**的 `.json` 追加进 `archive\<年>.jsonl`，每行一个 JSON 对象，
然后从活动区移走原文件（**不是删除**）。

归档后**必须**跑自检：`python memory/tools\memory-check.py`

## 写事件的格式

```json
{
  "date": "2026-10-10",
  "type": "decision | conflict-detected | incident | verification",
  "project": "<项目 slug 或 memory-system>",
  "title": "一句话说清",
  "detail": "依据、来源、影响",
  "sources": [ {"ref": "…", "claim": "…", "source": "file-observed|user-explicit|legacy-summary|…"} ],
  "resolution": "已解决 / 待用户裁决 / 未解决",
  "supersedes": null
}
```

**文件名**：`YYYY-MM-DD-<type>-<slug>.json`

## 当前活动区内容

用 `ls events/*.json` 看。不在此处列举——避免这份策略文件随事件增长而膨胀
（它自己也在常驻之外的按需区，但没必要时时更新）。
