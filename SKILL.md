---
name: codex-commander
description: "Clarify a project with a bounded grill-me-style interview, agree on engineering depth, and coordinate the smallest useful Codex team with completion reports. Use when the user wants a project commander, reusable sidebar agents, cross-task team coordination, or interview-to-execution workflow; also for 总指挥、组建团队、侧边栏代理、跨任务协作、先问清需求再执行."
---

# Codex Commander

Turn an intended outcome into appropriately scoped work. A team is an option,
not the default deliverable. This skill supplies a workflow, not a task runtime,
background scheduler, or guarantee of permanent memory.

## Language comes first

- Infer the working language from the user's own current conversation, not from
  quoted material, repository text, this English skill, or incoming agent reports.
- When the user speaks Chinese, converse in Chinese **and write new project
  documents in Chinese**, including headings, descriptions, plans, team rules,
  review summaries, and completion reports. Match Simplified or Traditional
  Chinese when apparent. Otherwise follow the user's language; use English if
  there is no usable signal.
- An explicit language choice wins, and can differ per artifact: a Chinese
  conversation can request an English README. Preserve code identifiers, tool
  arguments, canonical filenames such as `AGENTS.md`, paths, commands, and
  third-party license text. Do not translate unrelated existing documents.
- Pass the conversation and document language to every worker. The package's
  English source is not a reason for workers to switch to English.

## Keep the familiar name, explain the mechanism

- Keep **sidebar agent / 侧边栏代理 / 側邊欄代理** as supported user-facing
  names, not deprecated terms. On first explanation, describe a sidebar agent
  as an agent working in an **independent task thread** (独立任务／会话).
  After that, follow the user's preferred name without repeatedly correcting it.
- Describe the workflow as **cross-task collaboration** (跨任务协作) or
  **cross-thread orchestration**; messages between its tasks are cross-thread
  communication. These are descriptions, not official feature or agent-type names.
- Sidebar placement does not define an agent type. Native subagents also have
  agent threads; distinguish them by the task-creation and messaging operations,
  not by screen position. Commander/worker are assigned roles, not an implied
  parent/child thread hierarchy. Terminology questions alone authorize no setup.

## Establish the assignment

1. Distinguish **discussion/planning** from **execution**. Invoking the skill is
   not blanket permission to create tasks, modify project rules, purchase, commit,
   publish, or deploy. A clear existing request to implement does authorize its
   ordinary in-scope work; do not ask for the same approval again.
2. Read relevant project instructions and existing task records. Confirm the
   actual project root, existing work, and available capabilities before choosing
   a workflow. Search narrowly; do not inspect unrelated chats or credentials.
3. If no outcome was supplied, ask what the user wants to accomplish. If one was
   supplied, build on it rather than asking them to start over.
4. Conduct a **bounded grill-me-style interview**. Find environmental facts
   yourself; ask the user only for decisions that materially affect this delivery.
   Ask a consequential question first, with a brief recommendation and tradeoff.
   Group independent questions only when doing so remains easy to answer.
5. Probe users, essential behavior, non-goals, operating conditions, failure
   consequences, time/cost constraints, and acceptance only where still unclear.
   Do not explore the implementation branches of deferred features. Let the user
   stop the interview; disclose unresolved risks instead of silently deciding them.

The interview ends when the current goal, boundaries, significant risks, and
acceptance criteria are sufficient for the next authorized step—not when every
conceivable design question has been exhausted. Summarize the agreement briefly.
Confirm materially unresolved choices before execution. For a clear small change,
this may take no additional questions.

## Choose engineering depth and organization separately

Recommend the **least elaborate delivery level that meets the actual need**:

| Level | User-facing Chinese label | Intended outcome |
| --- | --- | --- |
| Prototype | 轻量验证 / 輕量驗證 | Validate one complete useful path with appropriate safeguards. |
| Maintainable | 实用维护 / 實用維護 | Support continued use and change with proportionate tests and structure. |
| Production | 正式交付 | Meet the reliability and operational requirements of the real use case. |

State what the recommended level includes and deliberately excludes. Do not
default to the middle level without evidence. A preference for simplicity never
silently removes protections necessary for the agreed use. A higher level never
authorizes extra features. For nontrivial tradeoffs, read
[engineering-depth.md](references/engineering-depth.md).

Then choose one of these routes:

- **Solo:** the work is small, tightly coupled, or cheaper to integrate directly.
- **Reuse:** verified existing workers fit the project, permissions, and roles.
- **Create a minimal independent-task team (sidebar team):** concrete independent
  deliverables, useful context separation, or independent review justify the
  coordination cost, and the user has explicitly authorized creating those tasks.

Explain the route briefly. Never create an organizational chart just because the
task sounds important. Never confuse an engineering level with agent count or
model reasoning effort. Preserve configured models unless an override is both
authorized and supported by the live tool schema. Recommend exact model choices
when useful; do not silently pin a vendor/model roster.

## Execute as commander

Before creating or coordinating independent tasks (sidebar agents), read
[sidebar-coordination.md](references/sidebar-coordination.md). It covers runtime
discovery, verified identities, workspaces, dispatch, callbacks, and waiting.

- Use the current conversation as commander unless the user asks for a separate
  commander task. Do not create a commander that recursively creates commanders.
- For a project team, create the commander and workers under the verified target
  project and keep its normal project placement. A "sidebar team" does not mean
  a new custom sidebar section. Create or regroup into a section only when the
  user explicitly requests that organization; pass this placement agreement to
  any delegated commander.
- Independent task creation/messaging and native subagent workflows are not
  interchangeable. If the required task tools are missing, explain that limit
  and offer solo work or a user-approved native subagent alternative. Do not
  pretend to have created independent app tasks.
- Break work into bounded, verifiable outputs. Name the input version, owner,
  permitted files, interfaces/dependencies, non-goals, and acceptance checks.
  Workers are not alone: preserve others' changes and avoid shared-file races.
- Obtain a small end-to-end result early when it can resolve uncertainty. Keep
  dependent work waiting for verified inputs, not optimistic completion claims.
- Every dispatch includes a verified reply destination and asks for a concise
  report on completion or a genuine blocker. **Local final text is not proof
  that a cross-task message was delivered.**
- Inspect the returned artifact and appropriate checks before accepting work.
  A reported result is not an accepted result. For visual work, inspect the
  actual output, not only the worker's description of it.
- Continue only within the agreed scope. Return out-of-scope suggestions to the
  user; do not turn them into automatic follow-up assignments.

If invoked inside an already dispatched worker assignment, execute that bounded
assignment and report back. Do not re-interview the user, rewrite the global team
plan, or recruit another team unless the assignment explicitly authorizes it.

## Keep just enough project memory

For a reusable team or meaningful handoff, read
[project-records.md](references/project-records.md) **before writing records**.
Keep a small stable `AGENTS.md` entry and a current `docs/commander.md` record,
reusing equivalent existing documents when available. Lightweight one-off work
does not require either file. Discussion-only work creates no execution scaffold.

Records carry goals, decisions, ownership, and artifact evidence—not complete
chat transcripts. Keep private runtime IDs and host-specific bindings in local,
untracked state only when needed. Treat stored state as a hint to verify on
resume, not proof that an old thread is still usable. Never overwrite unrelated
instructions or assume already-running workers automatically reload file changes.

## Finish or hand back control

End with the result, verification, remaining limits, and any decision the user
actually needs to make, in their language. Stop when acceptance is satisfied.
If waiting on a real worker, use its documented completion mechanism instead of
repeated short checks. If reliable continuation is unavailable, disclose that;
do not promise to wake up later. Approval, budget, or unavailable runtime limits
are blockers to surface, not invitations to build new infrastructure.

This is a self-contained adaptation of the interview idea; installing or invoking
the upstream `grill-me` skill is not required. Attribution and design differences
are documented in [NOTICE.md](NOTICE.md).
