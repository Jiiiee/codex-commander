# Codex Commander

English | [简体中文](README.zh-CN.md)

A skill for clarifying the goal, choosing the right engineering depth, and
coordinating the smallest useful Codex team across independent task threads.

**Interview first when needed. Create a team only when justified. Verify delivery.**

Codex Commander combines a bounded, `grill-me`-inspired interview with practical
task delegation. It is an instruction-first skill—not an agent server, autonomous
scheduler, or promise that more agents will perform better.

## What it does

- Clarifies the current outcome without interviewing users about every possible
  future feature.
- Separates **Prototype**, **Maintainable**, and **Production** delivery levels
  from team size and model reasoning settings.
- Works solo, reuses suitable workers, or creates a user-authorized team of
  independent tasks (a **sidebar team**) under the selected project, without
  inventing a separate sidebar section.
- Requires bounded assignments, completion/blocker reports, and artifact review.
- Maintains minimal project records without replacing existing instructions.
- Matches the user's language. Chinese conversations produce Chinese project
  documents and reports, with Simplified/Traditional Chinese respected.

English is the default README language; the [Simplified Chinese version](README.zh-CN.md)
covers the same workflow. Skill instructions and maintainer references remain in
English. That does not set the language of a user's project. Explicit requests
such as “talk to me in Chinese, but write this README in English” are supported.

## Terminology: sidebar agents and cross-task collaboration

We keep **sidebar agent** (**侧边栏代理 / 側邊欄代理**) as a supported,
plain-language name for an agent working in an **independent Codex task thread**
that you can open from the app's task list. A **sidebar team** consists of those
independent tasks; the familiar name remains useful in conversation and tutorials.

**Cross-task collaboration** (跨任务协作) describes how the team works;
**cross-thread orchestration** describes coordinating it, and **cross-thread
communication** describes messages between its tasks. These are workflow
descriptions, not official OpenAI feature names or new built-in agent types.

Sidebar location alone does not identify the mechanism. Native subagents also
work in agent threads; distinguish this workflow by its independent task-creation
and messaging operations, not by which side of the screen displays an agent.
See the official [Subagents documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents).
Commander and worker are assigned roles, not a required parent/child thread
hierarchy. Here, a thread means a conversation, not an operating-system thread.

A concise Chinese introduction is: “侧边栏代理，是运行在独立任务／会话中的
Agent；它们通过跨线程通信，组成协作团队。” Use the familiar name after
explaining it; users do not need to adopt a new label to use the skill.

## Install locally

Clone the repository, or download its source ZIP from GitHub:

```sh
git clone https://github.com/sanshao85/codex-commander.git
cd codex-commander
```

Place this entire folder in a supported local skills directory under the name
`codex-commander`, or link it as shown below. The current official
Codex documentation describes `~/.agents/skills/` for user skills; some local
installations also use `~/.codex/skills/`. Use the location configured by your
host. Do not replace an existing installation without reviewing its changes.

On macOS/Linux, run the following **from the cloned repository directory** to
keep the source checkout and the installed skill in sync:

```sh
mkdir -p ~/.agents/skills
ln -s "$PWD" ~/.agents/skills/codex-commander
```

If the destination exists, inspect it rather than adding `--force`. On Windows,
copy the folder to the host's supported skill location or use an appropriate
directory link. Refresh the skill list or restart the client if it does not appear.

No API key, package install, or upstream `grill-me` installation is required.
The optional project-record helper and automated tests require Python 3.10+.

## Use

```text
Use $codex-commander to help me define a small local photo organizer.
Ask about important tradeoffs, recommend an engineering level, and explain
whether a team is worthwhile. Do not start implementation yet.
```

```text
用 $codex-commander 帮我做一个长期自用的小工具。先问清需求和工程化程度，
判断有没有必要组队。对话和生成的项目文档都用中文。
```

Once the scope and actual team proposal are clear, explicitly authorize creating
the independent tasks (sidebar agents) if that is the route you want. A skill
mention or a question about these terms alone is not permission to launch a team
or change your project rules.

The current conversation remains the commander unless you request a separate
commander task. Small, clear requests need neither a long interview nor a team.

Team tasks normally appear under the current or explicitly selected project.
Project membership, the checkout/worktree used for files, and sidebar sections
are separate concerns. Asking for a sidebar team does not request a new section.
An explicitly requested custom section is supported while retaining the correct
project binding. Existing project pins/sections are not rearranged automatically.

## Compatibility and limits

| Environment | Supported behavior |
| --- | --- |
| Codex with discoverable independent-task creation, messaging and inspection tools | Cross-task coordination (the sidebar-team workflow), subject to live permissions and tool capabilities. |
| Codex without those tools | Interview, delivery-level selection, solo work and project records; independent-task coordination is unavailable. |
| Native subagents only | An explicitly agreed alternative, not an equivalent independent-task/sidebar team. |

The skill does not install missing task tools or elevate permissions. It uses
configured model defaults unless a permitted explicit override is supplied.
Tool names and supported models are discovered at runtime, not pinned in this
package. Multiple workers may consume more tokens; savings are not guaranteed.

Reports use task/attempt identities to avoid acting on stale results. This is
not an exactly-once message protocol. A paused app, interrupted worker, missing
capability or quota limit can prevent delivery. Completion callbacks and wake-up
behavior must be verified in the target host before relying on unattended work.

## Project records

For an authorized reusable team, the default is a concise `AGENTS.md` section and
`docs/commander.md`. Private runtime bindings, if needed, stay in an untracked
local file. Existing equivalent records are preferred over duplicate documents.
One-off work does not require a scaffold.

Preview the optional bootstrap without writing files:

```sh
python3 scripts/project_records.py --root /absolute/path/to/project \
  --language en --level maintainable --goal 'A local tool for repeated use'
```

Inspect the preview and repeat with `--apply` only for an authorized target.
Use `--language zh-CN` or `zh-TW` for Chinese documents. The helper does not
auto-detect conversation language; the agent selects it from the conversation.
It preserves existing plan documents and fails on unsafe/ambiguous output paths.

## Validate

```sh
python3 -m unittest discover -s tests -v
python3 scripts/check_package.py
```

These commands use temporary directories and do not call task tools or external
services. Structural checks do not prove the quality of an interview. See
[the behavioral evaluation guide](tests/behavioral-evaluation.md) and
[validation status](VALIDATION.md) for what was actually exercised and what
remains host-dependent.

## Contributing

Keep the English and Chinese READMEs aligned when changing public usage or limits.
Keep the entrypoint concise and route detailed guidance only when needed. Add a
realistic behavior case for changes to permissions, language, delegation, or
completion handling. Do not add fixed team rosters, speculative infrastructure,
or rules for unrelated workflows. Test file-writing changes in a temporary
project, preserving existing content and refusal behavior. Never include private
task IDs, host paths, credentials, or third-party video transcripts in a PR.

## License and attribution

MIT. See [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md).

This independent community project is not an official OpenAI product and is not
endorsed by OpenAI or Matt Pocock. `grill-me` inspired the clarification approach;
the bounded stopping rule and cross-thread coordination workflow for sidebar
agents are this project's own adaptation.

Official references: [Build skills](https://learn.chatgpt.com/docs/build-skills),
[AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md), and
[Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents).
For project context and display organization, see
[Projects and chats](https://learn.chatgpt.com/docs/projects).
