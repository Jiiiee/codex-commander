# Codex Commander

[English](README.md) | 简体中文

一个帮助 Codex 问清目标、确定合适的工程化程度，并通过独立任务协调最小有效团队的技能。

**需要时先追问，值得时才组队，交付后要验收。**

Codex Commander 将有边界的 `grill-me` 式需求追问与任务委派结合起来。
它以技能指令定义工作流程，不是 Agent 服务器、自动调度服务，也不承诺 Agent 越多效果越好。

## 它能做什么

- 问清当前要完成的目标，不为了所有可能的未来功能无限追问。
- 区分 **Prototype（轻量验证）**、**Maintainable（实用维护）** 和
  **Production（正式交付）**，不把工程化程度与团队人数、模型思考强度混为一谈。
- 根据需要选择独立完成、复用合适的执行者，或在用户明确授权后，
  在目标项目下创建由独立任务组成的**侧边栏代理团队**，不自行新建侧边栏分区。
- 为委派任务规定范围、产物和验收条件；要求完成或真实阻塞时回报，并检查实际交付物。
- 保留精简的项目协作记录，不替换已有项目规则。
- 跟随用户语言。用户用中文交流时，对话、新增项目文档与工作回报也使用中文，
  并尊重简体、繁体以及单独指定的产物语言。

仓库默认展示英文 README，本文件提供内容对应的简体中文版；技能指令和维护参考文档
继续使用英文。这不会决定用户项目的语言。例如，“用中文和我交流，但 README 写英文”
这样的要求也可以分别处理。

## 术语：侧边栏代理与跨任务协作

我们保留**侧边栏代理**（sidebar agent）这个直观叫法：它指运行在一个
**独立 Codex 任务／会话**中的 Agent，你可以从应用的任务列表里单独打开它。
多个这样的独立任务可以组成侧边栏代理团队，日常交流和教程中可以继续使用这个名称。

**跨任务协作**（cross-task collaboration）描述团队的工作方式；
**跨线程编排**（cross-thread orchestration）描述如何协调它们；
**跨线程通信**（cross-thread communication）描述任务之间的消息往返。
这些是工作流描述，不是官方 OpenAI 功能名称，也不是新增的内置代理类型。

不能仅凭界面位置判断工作机制。原生子代理也有自己的 Agent 线程；本工作流的区别在于
使用独立任务的创建、检查和发消息操作，而不在于 Agent 显示在屏幕哪一侧。
可参考官方的[子代理文档](https://learn.chatgpt.com/docs/agent-configuration/subagents)。
“总指挥”和“成员”是分工角色，不代表必须存在系统层面的父子线程关系。
这里的“线程”指会话线程，不是操作系统线程。

可以这样介绍：

> 侧边栏代理，是运行在独立任务／会话中的 Agent；它们通过跨线程通信，组成协作团队。

解释清楚后，就可以继续简称“侧边栏代理”，不需要反复改口。

## 本地安装

克隆仓库，或从 GitHub 下载源码 ZIP：

```sh
git clone https://github.com/sanshao85/codex-commander.git
cd codex-commander
```

将整个目录以 `codex-commander` 为名放进当前客户端支持的技能目录，也可以使用下面的
符号链接方式。当前官方 Codex 文档使用 `~/.agents/skills/` 作为用户技能目录；
部分本地安装也使用 `~/.codex/skills/`。请以自己客户端支持和配置的路径为准。
如果已有同名技能，先检查内容，不要直接覆盖。

在 macOS／Linux 上，**进入刚克隆的仓库目录后**执行：

```sh
mkdir -p ~/.agents/skills
ln -s "$PWD" ~/.agents/skills/codex-commander
```

这样源代码目录与已安装技能保持同步。如果目标路径已经存在，先检查，不要加 `--force`。
在 Windows 上，可以将完整目录复制到客户端支持的技能位置，或使用适用的目录链接。
如果技能没有出现，刷新技能列表或重启客户端。

使用本技能本身不需要额外的 API Key、安装依赖包或安装上游 `grill-me`。
可选的项目记录辅助脚本和自动化测试支持 Python 3.10–3.13。

## Python 兼容性、本地升级与维护

本技能除标准库外没有运行时依赖。为避免把配置文件误当作已完成的托管运行，文档会明确
区分声明的支持基线、已配置的 CI 目标和本机证据：

| Python | 声明的支持 | 已配置的 CI 目标 | 当前本机证据 |
| --- | --- | --- | --- |
| 3.9 | 不受支持；即使本机恰好能够运行，也不改变此结论。 | 不作为目标。 | 无。 |
| 3.10 | 最低支持版本。 | Ubuntu 与 macOS。 | 本工作树尚未记录。 |
| 3.11 | 属于当前支持范围。 | Ubuntu 与 macOS。 | 本机证据见 VALIDATION.md。 |
| 3.12 | 属于当前支持范围。 | Ubuntu 与 macOS。 | 本机证据见 VALIDATION.md。 |
| 3.13 | 属于当前支持范围。 | Ubuntu 与 macOS。 | 本工作树尚未记录。 |
| 后续小版本 | 未审阅前不声明支持。 | 未明确加入前不配置。 | 无。 |

仓库中的 GitHub Actions 工作流已为表中的 CI 目标配置，但此处不宣称它已经在 GitHub
托管环境运行。配置矩阵不是运行证据；确切本机命令和历史结果见
[VALIDATION.md](VALIDATION.md)。

本地复制安装和符号链接安装都采用“先审阅、后变更”的方式，不是自动更新渠道。升级时，
先检查实际使用的技能目录入口以及它是目录还是链接；在独立位置准备并比较候选源码；
在那里运行包检查和测试；随后才明确决定是重定向链接，还是替换复制安装的目录。候选版本
完成审阅和验证前，保留现有副本。不要用递归复制覆盖现有安装，也不要强制替换链接；
选定变更完成后再刷新客户端。

维护者应同步更新 `VERSION`、支持矩阵和 `VALIDATION.md`。兼容性改变时，测试受影响的
Python 与操作系统组合，并分别记录本机证据和已经完成的托管 CI。委派或其他行为改变时，
更新行为用例，并只记录实际取得的运行时证据。这些维护步骤不代表已经发布新版本。

当前源码可作为 **v0.2.0 本地候选** 审阅。[RELEASE_NOTES.md](RELEASE_NOTES.md)
中的“拟用 Tag”只标识该候选，不证明本地或远端 Git Tag 存在；远端 Tag 和 GitHub
Release 是两项独立事实，分别需要在对应服务中核实。[RELEASE_CHECKSUMS.txt](RELEASE_CHECKSUMS.txt)
仅检查候选内文件集合、版本字符串和哈希的内部一致性，不证明来源、真实 Tag，也不能防御恶意篡改。

## 使用方法

```text
用 $codex-commander 帮我做一个长期自用的小工具。先问清需求和工程化程度，
判断有没有必要组队。对话和生成的项目文档都用中文。
```

```text
Use $codex-commander to help me define a small local photo organizer.
Ask about important tradeoffs, recommend an engineering level, and explain
whether a team is worthwhile. Do not start implementation yet.
```

当目标、范围和具体分工已确定，如果选择团队路线，需要明确授权创建独立任务
（侧边栏代理）。仅提及技能，或询问这些术语的含义，不等于授权启动团队或修改项目规则。

默认由当前会话担任总指挥；只有你要求单独创建总指挥任务时，才另外创建。
小而明确的请求不需要长时间访谈，也不一定需要团队。

团队任务默认归属当前项目或你指定的项目，并保留正常的项目下展示。
**项目归属、实际工作的目录／worktree、侧边栏分区**是不同的事情。
“创建侧边栏代理团队”不等于“创建新分区”。如果你明确要求自定义分区，
可以在保持正确项目绑定的前提下使用；技能不会自行调整已有项目的置顶或分区。

## 与上游 `grill-me` 和 `grilling` 的关系

下列名称只描述各自仓库中的机制，并不是跨项目通用的官方标准。在本项目审阅的上游
提交中，[`grill-me`](https://github.com/mattpocock/skills/blob/6654f6b60cd9d5be8b54c6fafe44346dabeb3b76/skills/productivity/grill-me/SKILL.md)
会转交给
[`grilling`](https://github.com/mattpocock/skills/blob/6654f6b60cd9d5be8b54c6fafe44346dabeb3b76/skills/productivity/grilling/SKILL.md)。
Codex Commander 无需安装上游技能，并对其追问思路作了以下独立改编：

| 主题 | 审阅版本中的上游机制 | Codex Commander 的机制 |
| --- | --- | --- |
| Frontier 与停止条件 | `grilling` 用 design tree（设计树）组织决策。**Frontier** 是前置条件均已确定的全部决策；遍历所有分支、frontier 为空时结束。 | Codex Commander 不要求显式建立设计树，也不要求穷尽 frontier。当当前目标、边界、重大风险和验收条件已足以支持下一步获授权工作时即可停止；用户也可以提前叫停，此时需披露未决风险。 |
| 提问节奏 | `grilling` 在一轮中提出当前整个 frontier 的编号问题，等待回答后再重新计算 frontier。 | Codex Commander 先问一个会影响交付的重要问题；只有相互独立且合并后仍容易回答时才成组提问。小而明确的改动可以不再追加问题。 |
| `Prototype` | 上游另有 [`prototype` 技能](https://github.com/mattpocock/skills/blob/6654f6b60cd9d5be8b54c6fafe44346dabeb3b76/skills/engineering/prototype/SKILL.md)，用这个词表示为回答设计问题而编写的可丢弃代码。 | **Prototype（轻量验证）**是本项目自己的交付深度标签：在适当保护措施下验证一条完整而狭窄的路径。它不表示代码必须丢弃，也与团队人数无关。 |

这些是范围和工作流机制的差异，不表示任何一方必然更快、能力更强或普遍更好。
审阅的上游版本与致谢信息见 [NOTICE.md](NOTICE.md)。

## 兼容性与限制

| 环境 | 支持的行为 |
| --- | --- |
| Codex 提供可发现的独立任务创建、消息与检查工具 | 根据实际工具能力和权限执行跨任务协作，也就是侧边栏代理团队工作流。 |
| Codex 不提供这些工具 | 可以追问需求、确定工程化程度、独立完成工作和维护项目记录，但不能执行独立任务协作。 |
| 只有原生子代理 | 经用户明确同意后可以作为替代方案，但不等同于独立任务／侧边栏代理团队。 |

本技能不会安装缺失的任务工具或提升权限。默认使用已配置的模型；只有获得允许且当前
工具支持时才使用明确指定的覆盖配置。工具名称和可选模型在运行时检查，不在技能中写死。
多个执行者可能消耗更多 token，不能保证节省费用。

回报通过任务与执行轮次标识区分，避免误用过期结果；这不是“消息恰好投递一次”的协议。
应用暂停、执行者中断、工具缺失或额度耗尽，都可能影响回报送达。
依赖无人值守运行前，需要在实际客户端验证完成回报和唤醒行为。

## 项目协作记录

对于已授权建立的可复用团队，默认只需要精简的 `AGENTS.md` 协作区块和
`docs/commander.md` 项目记录。确有需要时，私有运行时绑定保留在不跟踪的本地文件中。
优先复用已有等价记录，避免重复建文档；一次性的小任务不要求建立整套记录。

下面的可选辅助命令只预览，不写入文件：

```sh
python3 scripts/project_records.py --root /absolute/path/to/project \
  --language zh-CN --level maintainable --goal '一个长期自用的本地工具'
```

请将示例中的绝对路径替换成真实项目路径。确认预览和目标已获授权后，才加上 `--apply`
执行写入。英文记录使用 `--language en`，繁体中文使用 `--language zh-TW`。
脚本本身不会识别对话语言，由 Agent 根据对话选择参数。
脚本保留已有计划文档，并在输出路径不安全或含糊时拒绝操作。

## 验证

```sh
python3 -m unittest discover -s tests -v
python3 scripts/check_package.py
python3 scripts/run_behavioral_cases.py --list
python3 scripts/run_behavioral_cases.py --dry-run --output /tmp/codex-commander-behavioral-results.json
```

测试和包检查使用临时目录，不调用真实任务工具或外部服务。Runner 命令只列出或规划
内置用例，不能证明真实任务创建、侧边栏归属、自动恢复或无人值守送达。
结构检查通过不代表需求追问或团队协调一定正确。
实际验证范围和仍依赖客户端的能力，见[行为评估说明](tests/behavioral-evaluation.md)
与[验证记录](VALIDATION.md)。

## 参与贡献

修改公开使用方法或限制时，请同步中英文 README。
保持技能入口简洁，仅在需要时引导读取详细参考文件。
修改权限、语言、委派或回报处理时，补充真实的行为场景。
不要加入固定团队编制、尚无需求的基础设施，或无关工作流规则。
涉及写文件的改动，应在临时项目中测试，并检查既有内容和安全拒绝行为是否保留。
不要在 PR 中提交私有任务 ID、本机路径、凭据或第三方视频字幕全文。

## 许可证与致谢

采用 MIT 许可证，见 [LICENSE](LICENSE) 与 [NOTICE.md](NOTICE.md)。

这是独立社区项目，不是 OpenAI 官方产品，也不代表获得 OpenAI 或 Matt Pocock 的背书。
需求澄清思路受到 `grill-me` 启发；有边界的追问停止条件，以及面向侧边栏代理的
跨线程协调工作流，是本项目的独立改编。

官方参考：[技能构建](https://learn.chatgpt.com/docs/build-skills)、
[AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)、
[子代理](https://learn.chatgpt.com/docs/agent-configuration/subagents)。
项目上下文和界面组织方式可参考[项目与会话](https://learn.chatgpt.com/docs/projects)。
