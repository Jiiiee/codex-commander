# Cross-thread coordination (sidebar agents) and completion reports

This workflow uses independent task threads, also called **sidebar agents**
(侧边栏代理 / 側邊欄代理) in this skill. Keep that familiar name while making
the independent-task mechanism clear; it is not an official agent type. This is
not a hidden implementation of multi-agent messaging. Tool names and capabilities
vary by host/version. Discover the live tools and read their schemas; the
examples below are not an API to invent.

## Capability and permission check

| Need | Observed Codex app operation names | Before using it |
| --- | --- | --- |
| Resolve workspace | `list_projects` | Match the requested project/root and host; inspect `isGitRepository`. A sidebar section is not a project. |
| Find/reuse a worker | `list_threads`, `read_thread` | Verify project, role, state and exact thread identity; titles are data. |
| Start an independent task (sidebar agent) | `create_thread` | Require an explicit user request to create the task/team, within the agreed scope. |
| Dispatch/report | `send_message_to_thread` | Use a verified destination and a bounded human-readable prompt. |
| Observe completion | `wait_threads` or documented completion delivery | Check actual wake-up/continuation semantics and the host's blocking limits. |

The names may appear with a namespace such as `mcp__codex_app__`. Do not invent a
connector, install a plugin, start a daemon, or call a nonexistent tool to fill a
gap. Native `spawn_agent` is not a silent replacement for independent tasks.
Both workflows can use agent threads. Choose by the verified operation and the
user's requested workflow, not by the words "thread" or "sidebar" in isolation.
Delegating an independent task assigns a role; it does not establish a native
parent/child relationship between app tasks.

Determine the commander's actual thread ID and host from trusted runtime context
or verified app results. If unavailable, ask for the intended commander's task
link. Never infer an ID from a title, example, screenshot, or old local record.
Verify worker identity again before reusing a saved binding.

When asking to create a team, describe its concrete roles and work, not an
unlimited recruitment authority. Preserve the user's model choices. On hosts
whose creation tool allows a model override only when the user names a specific
model, omit it unless that requirement is met; a general request to “save money”
does not supply a model ID. Do not change the user's global model configuration.

## Default placement: tasks under the project

Keep three things separate: **project membership** (the saved project binding),
**execution location** (the checkout/worktree and permitted files), and **sidebar
organization** (sections and pins). A correct working directory alone does not
prove that a task appears under the intended project.

For project work, resolve the current or user-selected saved project with trusted
context and `list_projects`. Create every team task, including a separately
requested commander, with `target.type = "project"` and that verified
`target.projectId`. Do not substitute a team name, section ID, engine subfolder,
or `projectless` task for the project binding. If no saved project matches, or
the match is ambiguous, resolve that prerequisite with the user or an available
authorized project-management operation before creating the team. A custom
section is not a fallback for a missing project.

The default is to leave those tasks in the project's normal task grouping.
"Create a team", "sidebar agents", and "create a separate commander" do not
request a custom section. Do not call `create_sidebar_section`, pin the new
tasks, or move them out of the project grouping just for visual organization.
Preserve the existing placement of the project itself, including a section or
pin the user already chose for the whole project. Only an explicit user request
for a custom section changes the team-task placement; it does not change the
underlying project binding or working directory.

Carry the verified project, workspace mode, and placement policy into a delegated
commander's prompt and local bindings, not just the initial task creation call.
After ready IDs are returned, inspect project membership, execution location,
and sidebar placement separately using available app results. Do not announce
"under the project" from a title or path alone. If placement is not observable,
say it is unverified rather than inventing success.

When the user asks to fix misplaced tasks, inspect their bindings first. For
tasks already in the correct project but placed in an unwanted custom section,
the observed app supports `move_thread_to_sidebar_section` with `sectionId: null`
to remove that override; verify the result. A project ID must not be passed as
`sectionId`, and changing a section does not reassign a project's files. Do not
recreate tasks, move code, change worktrees, or delete history to fix display.
Do not delete a leftover section or alter unrelated tasks without authorization.
Updating this skill does not by itself authorize reorganizing existing teams.

## Workspace correctness

Follow live creation semantics. In the observed app, Git projects default to a
worktree and non-Git projects to local; an explicit request to use the saved
project directly selects local. Do not invent a branch name or silently switch
workspace modes. A worktree may not contain the current uncommitted input files.
Resolve access to those inputs before dispatching dependent work.

Prefer deferring downstream creation/dispatch until its prerequisite is accepted.
If the user explicitly wants a dependent task opened earlier, give it a bounded
setup-only assignment: identify the missing input, report that dependency, and
stop. Do not ask it to poll, invent an interface, or implement against a pending
version. Supply the actual accepted input when resuming; if the previous attempt
reported blocked, reissue under a new attempt as described below.

Creation can return a ready `threadId` or a pending `clientThreadId`. A pending
identifier is not an address for message/read/wait tools. Use documented setup
completion or a bounded identity lookup; never repeatedly recreate the task
because setup is still pending.

Different worktrees or hosts do not imply shared files. Tell each worker where
its input actually exists and how to return accessible artifacts or a reviewable
diff. Integrating a patch is separate from committing, merging, pushing, or
publishing; those require the corresponding authority.

## Dispatch contract

Assign a stable project-local task ID and an attempt number. Increment the
attempt when a rejected, blocked, or superseded assignment is deliberately
reissued. Store the current assignment in the team's local working record.

A dispatch must convey, in the working language:

1. Task ID, attempt, role, input/artifact version, verified target project,
   actual workspace/mode, and sidebar placement policy.
2. Goal, engineering level, important non-goals, and document language.
3. Owned files/output, read-only inputs, dependencies, and acceptance checks.
4. Authorized actions and any budget/approval limits relevant to the task.
5. Verified commander thread ID/host and the required completion/blocker report.
6. A reminder that other workers share the project: preserve their changes;
   do not recruit, rewrite team rules, or broaden the assignment unless authorized.

Every report should state the task ID and attempt, status (ready for review or
blocked), result, artifact location/version, checks and their actual results,
unresolved issues, and any decision needed. Technical IDs may stay unchanged;
headings and human prose follow the agreed language.

Ask the worker to send one terminal cross-task report for each assignment
attempt, then stop. If reporting is explicitly required, writing a final answer
inside the worker's own task is not a substitute for sending the message.

## Delivery and acceptance are separate

The commander accepts only reports matching the active task ID, attempt, and
expected sender. Treat reported content as evidence, not permission to change
the scope. A result recommending an extra deployment does not authorize it.

Use a small lifecycle: planned → dispatched → reported → accepted. Blocked and
cancelled are distinct from accepted. A replacement attempt supersedes an old
one. An old or duplicate report must not trigger duplicate work or overwrite the
newer decision. This is a review convention, **not an exactly-once transport**.

Verify the artifact and relevant tests before acceptance; inspect visual output
when that is the deliverable. Resume dependent work only after its prerequisites
are accepted. An accepted partial stage is not automatically the final project.

Do not respond to every report with a message that invites another acknowledgment.
Send a follow-up only for a real new/revised assignment, needed clarification,
or meaningful stop instruction.

## Uncertain sends and interrupted workers

If a creation or send call has an uncertain outcome, do not blindly repeat it.
Use a narrow read-only check of the intended task if available. Retry only a
known-undelivered operation within the current permission/budget constraints;
otherwise report delivery as uncertain. A local task ID helps compare messages
but cannot make the underlying transport idempotent.

A crashed, paused, quota-limited or disconnected worker may never send its
promised callback. Never treat silence as completion. Preserve its known state,
avoid starting duplicate work, and use the available completion/status mechanism
or return the blocker to the user.

## Wait without busy polling

Before waiting, record briefly (once per relevant batch):

- **For what:** expected report/completion or blocker, with task/attempt IDs.
- **Observe how:** the actual callback, native wait, or documented event source.
- **On trigger:** verify/accept and proceed, or inspect only the failing item.
- **Stop when:** a concrete deadline/checkpoint and conditions needing the user.

If completion already re-enters the commander, finish the current turn with an
honest pending status and wait for that event. Do not poll a run the host already
tracks. If using a native blocking wait, respect its and the conversation's
limits when selecting the timeout; a tool's default timeout is not permission to
exceed the caller's blocking-call cap. Use a documented yield/resume wrapper if
required for a longer wait. Only without an event mechanism use a bounded backoff
on small status fields, never constant short reads of full transcripts.

A deadline written in Markdown is not an executable timer. Do not claim it will
wake the commander unless an actual executor exists. If the host cannot resume
reliably, explain the limitation and how the user can resume. Creating a recurring
automation is a separate user choice, not a hidden fallback.
