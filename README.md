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
The optional project-record helper and automated tests support Python 3.10–3.13.

## Python compatibility, local upgrades, and maintenance

This skill has no runtime dependency beyond the standard library. We separate a
documented support baseline, configured CI targets, and local evidence so that a
configuration file is not mistaken for a completed hosted run:

| Python | Documented support | Configured CI target | Current local evidence |
| --- | --- | --- | --- |
| 3.9 | Not supported, even if a local invocation happens to run. | Not targeted. | None. |
| 3.10 | Minimum supported version. | Ubuntu and macOS. | Not recorded for this working tree. |
| 3.11 | Included in the supported range. | Ubuntu and macOS. | Local evidence is recorded in VALIDATION.md. |
| 3.12 | Included in the supported range. | Ubuntu and macOS. | Local evidence is recorded in VALIDATION.md. |
| 3.13 | Included in the supported range. | Ubuntu and macOS. | Not recorded for this working tree. |
| Future minor versions | Not declared until reviewed. | None until added deliberately. | None. |

The repository's GitHub Actions workflow is configured for the listed CI
targets. Historical hosted evidence exists for the earlier candidate
`46437a7074ba6febb4ddb85a06259f17119bf988`: GitHub Actions run `34072191750`
completed all eight Ubuntu/macOS × Python 3.10–3.13 jobs successfully. A
configured matrix is not itself execution evidence, and that run does not
establish results for a later candidate. The candidate produced by this
documentation update still needs a hosted run for its own pushed SHA; verify
that result in GitHub PR/Actions and the external Taskboard record. See
[VALIDATION.md](VALIDATION.md) for the exact local commands and historical
results.

Ubuntu has this same-SHA automated evidence. Windows execution, real-model
behavior, and complete sidebar recovery remain unestablished; they must not be
inferred from local checks, the hosted matrix, or packaged behavioral cases.

Local copies and symbolic links are intentionally review-first, not an automatic
update channel. To upgrade, inspect the actual supported skills-directory entry
and whether it is a directory or link; prepare and compare a candidate source in
a separate location; run the package check and tests there; then explicitly
choose whether to repoint a link or replace a copied directory. Keep the current
copy until the candidate has been reviewed and validated. Do not overlay an
existing installation with a recursive copy or force-replace a link, and refresh
the client only after the chosen change is complete.

Maintainers update `VERSION`, the support matrix, and `VALIDATION.md` together.
When changing compatibility, test the affected Python and operating-system
combinations and record which results are local evidence versus completed hosted
CI. When changing delegation or other behavior, update the behavioral cases and
record only the runtime evidence actually obtained. A release is not implied by
these maintenance steps.

The current source may be reviewed as a **v0.2.0 local candidate**. `Intended tag`
in [RELEASE_NOTES.md](RELEASE_NOTES.md) names that candidate; it does not establish
a local or remote Git tag. A remote tag and a GitHub Release are separate facts
that must each be verified in their respective services. [RELEASE_CHECKSUMS.txt](RELEASE_CHECKSUMS.txt)
checks only the candidate's internal file-set, version, and hash consistency; it
does not prove source provenance, a real tag, or resistance to malicious tampering.

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

## Relationship to upstream `grill-me` and `grilling`

The names below describe each repository's own mechanism; they are not official
cross-project standards. At the upstream commit reviewed by this project,
[`grill-me`](https://github.com/mattpocock/skills/blob/6654f6b60cd9d5be8b54c6fafe44346dabeb3b76/skills/productivity/grill-me/SKILL.md)
delegates to
[`grilling`](https://github.com/mattpocock/skills/blob/6654f6b60cd9d5be8b54c6fafe44346dabeb3b76/skills/productivity/grilling/SKILL.md).
Codex Commander is self-contained and adapts the interview idea as follows:

| Topic | Reviewed upstream mechanism | Codex Commander mechanism |
| --- | --- | --- |
| Frontier and stopping rule | `grilling` models a design tree. Its **frontier** is every decision whose prerequisites are settled; the session ends when that frontier is empty after every branch has been visited. | Codex Commander does not require an explicit design tree or exhaustive frontier. It stops when the current goal, boundaries, significant risks and acceptance criteria are sufficient for the next authorized step; the user may stop sooner, with unresolved risks disclosed. |
| Question cadence | `grilling` asks the whole current frontier in a numbered round, then waits and recomputes it from the answers. | Codex Commander asks a consequential question first and groups independent questions only when the group remains easy to answer. A clear small change may require no additional questions. |
| `Prototype` | Upstream's separate [`prototype` skill](https://github.com/mattpocock/skills/blob/6654f6b60cd9d5be8b54c6fafe44346dabeb3b76/skills/engineering/prototype/SKILL.md) uses the word for throwaway code that answers a design question. | **Prototype (轻量验证)** is this project's delivery-level label: validate one complete, narrow path with appropriate safeguards. It does not imply throwaway code, and it is separate from team size. |

These are scope and workflow differences, not claims that either approach is
faster, more capable, or generally better. See [NOTICE.md](NOTICE.md) for the
reviewed upstream version and attribution.

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
On rerun it removes only newer temporary residue that exactly matches the current
plan and passes stable metadata checks. Legacy, different-plan, or uncertain residue
is preserved for user-confirmed manual handling; its advisory lock and cleanup are
not atomic against non-cooperating writers with access to the same directory.

## Validate

```sh
python3 -m unittest discover -s tests -v
python3 scripts/check_package.py
python3 scripts/run_behavioral_cases.py --list
python3 scripts/run_behavioral_cases.py --dry-run --output /tmp/codex-commander-behavioral-results.json
```

The tests and package check use temporary directories and do not call task tools
or external services. The Runner commands only list or plan packaged cases; they
do not establish live task creation, sidebar placement, automatic recovery, or
unattended delivery. Structural checks do not prove the quality of an interview. See
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
