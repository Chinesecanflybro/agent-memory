# LAUNCH — 探市场的行动清单

> 目的：看有没有人对"证据分级记忆"这个方向感兴趣。
> 状态截至 2026-10-10。**做完了就勾掉，别在聊天记录里翻。**

---

## 当前状态（实测）

| 项 | 值 |
|---|---|
| 可见性 | ✅ **Public** |
| 描述 | ✅ 已填 |
| License | ✅ MIT |
| Topics | ❌ **空 —— 搜索搜不到** |
| Discussions | ❌ 未开启 |
| Stars / Forks | 0 / 0 |

---

## ⏱ 第 1 步（15 分钟，你自己做，收益最大）

**加 topic 标签** —— 没有它，别人在 GitHub 搜索里根本找不到你。

1. 打开 https://github.com/Chinesecanflybro/agent-memory
2. 右侧 About 区域，点 **⚙️**（齿轮）
3. **Topics** 框里粘贴（GitHub 会自动分词）：
   ```
   ai-agent ai-memory long-term-memory agents-md claude-code context-engineering memory-bank evidence-tracking
   ```
4. 顺手把 **Website** 留空、**Include in the home page** 保持勾选 → **Save changes**

**做完的标志**：仓库标题下方出现一排蓝色标签。

---

## ⏱ 第 2 步（10 分钟）去 claude-mem 的 issue 留言

**为什么这条价值最高**：维护者**刚处理完和你一模一样的问题**
（[issue #3162](https://github.com/thedotmack/claude-mem/issues/3162)：*agent 在没有任何写操作证据时断言工作已完成*）。
**看这个 issue 的人全都是你的目标用户。**

打开 → 拉到最下面回复框 → 粘贴下面这段（**建议改成你自己的话，照抄容易显得像广告**）：

> Ran into the same class of bug and went a different route — instead of gating at the observer layer, I made the *claim* carry its state. Every progress statement in the memory files has to be tagged `planned | changed | ran | test-passed | independently-verified`, and a check script fails if something claims `test-passed` without a pointer to evidence.
>
> It's markdown-only and zero-dependency, so it's weaker than what you're doing — no integrity guarantees. But it catches the specific failure where the agent paraphrases its own intent back as accomplished work. Curious whether you considered enforcing this at the claim level rather than at the ingest gate?
>
> https://github.com/Chinesecanflybro/agent-memory

**注意**：结尾那个问题是**故意的**。它把话题从"看我项目"变成"问你个技术问题"，
回复率完全不同。**别删掉它。**

---

## ⏱ 第 3 步（15 分钟）去 HN 已有讨论里回复

**不要新开 Show HN**（原因见第 5 步）。去这个 19 天前的帖子：

https://news.ycombinator.com/item?id=49786419
（*Show HN: Lossless-memory – a personal AI memory that never summarizes*，67 分 / 40 条评论）

**那 40 条评论里有人在说你的卖点**，你可以顺着回：

- `firstline-dev`：摘要的失败模式是丢掉"重启所需的那点细节"
- `cemaluresin`：索引必修硬性限长、只放指针不放内容，**一旦允许模型写进去它就塞满废话**
- `syndiary`：AI 的派生记忆变化时，用户怎么检查原始来源
- `0xbadcafebee`：人们说的 memory 其实是 10 件不同的事

草稿：

> Same problem, different angle. The failure I kept hitting wasn't lossy summarization — it was the agent asserting *completed* work that only existed as a plan. So I made the memory carry the state of each claim: `planned / changed / ran / test-passed / independently-verified`, and a script fails the build if something claims `test-passed` with no evidence pointer.
>
> Turns out this isn't unexplored — AEP does per-claim reliability state with sha256 provenance, and claude-mem just shipped an evidence gate for the same bug. I'm the lightweight end: plain markdown, no deps, readable without tooling.
>
> Question for the thread: everyone caps the index and refuses to let the model write to it (I ended up there too). Has anyone found a way to let the agent *propose* memory writes without it filling up with things that look important and aren't?

⚠️ **HN 规矩**：帖子里**不要**连续推自己项目。回一条就够，有人问再答。

---

## 🚫 不要做的事

| 别做 | 为什么 |
|---|---|
| **现在发 Show HN** | 仓库只有几个提交、几小时前建的。HN 的人**会翻 commit 历史**。等有真实使用痕迹再发 |
| 到处复制粘贴同一段话 | 会被识别为 spam，账号可能被限 |
| 夸大"第一个做证据状态" | 已经有人做了（AEP、claude-mem），**说错会当场被打脸** |
| 删掉 README 里的更正记录 | 那是**可信度资产**，不是污点 |

---

## 📅 第 4 步（延后 1–2 周）发 Show HN

**前提**：仓库有真实使用痕迹（多几个提交、有 issue、README 有迭代历史）。

**标题建议**（一句话说清"凭什么不一样"）：

```
Show HN: Agent memory that stores why it believes something, not just what
```

**正文要点**（HN 喜欢简短 + 承认局限）：

1. 问题：agent 会把"打算做"说成"做完了"
2. 做法：给每条进度声明加证据状态，无证据不许升级
3. **诚实**：这不是新想法，AEP 和 claude-mem 都在做；我是最轻的那一端
4. 局限：防不了伪造，只防"不小心把不确定当确定"
5. 结尾提问（同第 2、3 步的设计）

---

## 📅 第 5 步（可选）其他渠道

| 渠道 | 说明 |
|---|---|
| **Reddit** r/LocalLLaMA / r/ClaudeAI | 调研时**漏掉了 Reddit**，那里可能有目标用户 |
| **agents.md 仓库** | 它的 issue 区讨论跨工具指令标准，和你的定位相邻 |
| **给 AEP 提 issue** | 问"能不能共存/互补" —— 这是**协作姿态**，比竞争更容易获得关注 |

---

## ✅ 进度

- [ ] 加 topic 标签
- [ ] claude-mem issue #3162 留言
- [ ] HN 49786419 回复
- [ ] （延后）Show HN
- [ ] （可选）Reddit / agents.md / AEP

---

## 记录反馈的地方

有人回复、star、提 issue 时，**把原始反馈记到记忆库**（`memory/events/`），
不要只凭印象说"反响不错"。**这也是这套东西自己的规矩。**
