# agent-memory — 给 AI Agent 的证据分级长期记忆

> 一句话题目：**别的记忆系统存"内容"，这套存"内容 + 凭什么"。**

一个给 AI coding agent 用的跨会话长期记忆骨架。基于 `AGENTS.md` 自动注入，
用 Markdown + 索引 + 自检脚本，**不需要数据库、不需要向量库、不需要云服务**。

---

## 问题

AI 每次开新对话就失忆。更糟的不是"忘了"，而是**它会把不确定的东西说得很确定**：

- 把「打算做」说成「已经做了」
- 把「代码改了」说成「测试通过了」
- 把旧摘要里的路径、版本、完成状态**当成当前事实**
- 发现新旧矛盾时，**悄悄合并成一个看起来合理的说法**

前三个问题是上下文断裂，**第四个是编造**。

## 现有方案的缺口

调研了 GitHub 上主要的内存/记忆项目后的结论（2026-10）：

| 项目 | 存储与检索 | 证据分级 | 冲突检测 |
|---|---|---|---|
| claude-mem（98.9k★） | ✅ SQLite+FTS5+向量 | ❌ | ❌ |
| MemOS（11.8k★） | ✅ SQLite+FTS5+向量 | ❌ | ❌ |
| Graphiti（31.6k★） | ✅ 双时间轴图谱 | 🟡 有计划/失效时间 | ❌ 无级联 |
| Basic Memory（4.1k★） | ✅ Markdown+SQLite | ❌ | ❌ |
| remembrane（13★） | ✅ 单文件 SQLite | ❌ | ✅ **拒绝静默消解** |

**没有已发布系统区分** `planned / changed / ran / test-passed / independently-verified`。
最接近的是三篇 2026 年论文（[PACMI](https://arxiv.org/abs/2610.05732)、
[TierMem](https://arxiv.org/abs/2602.17913)、ZoneClaw）——**都还没有可用代码**。

**这个仓库补的就是这块。**

## 它怎么工作

```
你的工作区/
  AGENTS.md          ← DSH / Claude Code 等会自动注入它（唯一的自动化入口）
  memory/
    INDEX.md         ← 常驻：读取顺序 + 项目速查 + 权威层级
    SCHEMA.md        ← 按需：写记忆前必读
    GLOBAL_RULES.md  ← 按需：你的长期偏好与硬约束
    ARCHITECTURE.md  ← 按需：设计与踩坑教训
    projects/<项目>/STATE.md
    events/          ← 有界增长（活动区+按年归档）
    tools/
      memory-check.py   自检：秘密扫描 / 证据校验 / 完整性复验 / 常驻预算
      cost.py           开销报告：常驻 vs 按需 vs 磁盘
      baseline.py       哈希基线（无 git 时的版本证据）
      config.py         插拔式根目录解析
```

### 1. 三层常驻-按需分离

**每次新对话只读两个文件**（`AGENTS.md` + `INDEX.md`，约 7 KB）。
项目状态只读**当前那一个**。历史和规则细节按需加载。

→ **每次对话的 token 开销与记忆库总量无关。** 加到 100 个项目，每次开销不变。

### 2. 五态证据阶梯

每条"做完了什么"必须标其一：

| 标签 | 含义 |
|---|---|
| `planned` | 只打算做 |
| `changed` | 文件真改了 |
| `ran` | 真跑了 |
| `test-passed` | 测试真通过 |
| `independently-verified` | 执行者之外的第三方验证过 |
| `unknown` | 不知道（**也是一个合法答案**） |

**硬规则**：没有 `evidence:` 指向，**不许**标 `test-passed` 或 `independently-verified`。
**跑过 ≠ 通过；改过 ≠ 能跑。** 不许用"我读了代码，逻辑是对的"冒充 `test-passed`。

### 3. 机械自检，而不是靠自觉

```bash
python memory/tools/memory-check.py
```

它检查：混入的凭据 · 非法的状态/来源词 · 声称 `test-passed` 却无证据 ·
常驻上下文是否超预算 · 历史资料的完整性清单 · 已知失效路径。

**它的价值在于会报错。** 本仓库用故意做坏的文件验证过它能抓到：
假 API key、空口声称测试通过、非法状态词（如把来源词 `derived` 写进状态位）。
一个从不报错的检查器等于没有。

### 4. 冲突处理：永不静默覆盖

发现新旧矛盾 → 保留两边、标来源与时间、报告用户裁决。
**明确禁止**把两个矛盾说法"合并"成一个看似合理的版本。

## 安装

```bash
git clone <this-repo> agent-memory
cd agent-memory

# 1. 告诉工具记忆库在哪（三选一）
cp .memory-root.example .memory-root   # 然后按需改里面的路径
#   或
export MEMORY_ROOT=/path/to/memory     # Windows: set MEMORY_ROOT=D:\notes\memory
#   或
python memory/tools/memory-check.py --root /path/to/memory

# 2. 让 agent 自动读到（关键一步）
#    把 AGENTS.md 放到你的工作区根目录，并把里面的 <工作区名> 改成实际名字

# 3. 自检能不能跑
python memory/tools/memory-check.py     # 期望退出码 0
```

**没有 `AGENTS.md`，这套东西不会自动生效** —— 这是唯一被 agent 自动注入的入口。

### 换机器 / 换目录

所有路径都通过 `.memory-root`、`$MEMORY_ROOT` 或 `--root` 解析，**不写死在代码里**。
改一行配置即可，不用改 Python。

## 用法

开新对话时，只说：

```
继续 <项目名>
```

agent 应当：读到 `INDEX.md` → 定位项目 → 只读那一个 `STATE.md` → 给出回执，
**并明确列出哪些是未核验的**。

## 验证方法（重要）

**"文件建好了"不算数。** 本仓库用可证伪的方法验收：

1. **冷启动测试**：开一个无任何历史的新会话，只说一句"继续 X 项目"，
   看它能否自主恢复目标/进度/约束/未核验项。答案卡**先写、后测**。
2. **写入持久化测试**：写完后用**独立命令**回读，确认真的写进去了。
3. **冲突测试**：人为制造新旧矛盾，看它是否报告而非静默覆盖。
4. **秘密测试**：故意放一个假 key，确认被拦。
5. **自检工具本身的自测**：故意做坏文件，确认工具会报错。

见 `tests/cold-start-test.md` 的协议与答案卡。

## 诚实说明（当前状态）

- **这是早期项目，不是成品。** 截至目前只在 1 台机器、1 个真实项目上跑过
  1 次冷启动验收 + 1 次瘦身后回归（均通过）。
- **没有外部用户。** 兼容性未经验证。
- **平台耦合**：目前主要在 Windows + DeepSeek Harness 上验证过。
  概念与工具是跨平台的，但自动注入入口依赖宿主是否支持 `AGENTS.md`。
- **`AGENTS.md` 是唯一自动入口**，且它只能"命令 agent 去读"，
  不能**强制** agent 去读。这是宿主机制的限制，不是本项目的选择。
- **做不到的**：会话结束自动归档、压缩前自动出交接包——
  这两个时机的钩子在许多宿主里不存在，需要写宿主原生插件。

## 目录协议

| 路径 | 是否常驻 | 说明 |
|---|---|---|
| `AGENTS.md` | ✅ 每次 | 工作区指令，agent 自动注入 |
| `memory/INDEX.md` | ✅ 每次 | 入口 |
| `memory/SCHEMA.md` | 按需 | 写记忆前 |
| `memory/GLOBAL_RULES.md` | 按需 | 偏好细节 |
| `memory/ARCHITECTURE.md` | 按需 | 设计史与教训 |
| `memory/projects/<项目>/STATE.md` | 只读当前一个 | 项目现状 |
| `memory/events/` | 按需 | 事件与决策，有界增长 |
| `memory/import/` | 冷藏 | 历史资料，不参与检索 |

**常驻预算上限 10 KB**，超了自检会报警并提示往哪个文件搬。

## 贡献

最想要的是**反例**：

- 你的 agent 把 `planned` 说成 `test-passed` 了吗？
- 自检漏掉了什么该抓的错误？
- 五态阶梯有没有多余的档、或缺了哪一档？
- 在你那个 host（Claude Code / Codex / Cursor / 其他）上，
  `AGENTS.md` 注入是否可靠？

**提 issue 比提 PR 更有用**——尤其是有具体复现步骤的失败案例。

## License

MIT
