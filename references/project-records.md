# Minimal, localized project records

Read this before modifying the target project's records. The skill package is
English; **generated human-facing project records follow the user's language**.
Explicit per-document language requests take precedence. Preserve existing
unrelated prose, canonical filenames, machine-readable keys, and license text.

## When to persist

For a reusable team or a meaningful handoff, confirm the project root and current
execution scope, then reuse the project's existing equivalents where possible.
Do not initialize team records during a discussion-only request, for every small
edit, or merely because the skill was mentioned. A request to set up the team and
its records authorizes the relevant local scaffold, not unrelated configuration.

| Record | Contents | Writer |
| --- | --- | --- |
| `AGENTS.md` | A short stable pointer and collaboration rules, scoped to commander-managed work. | Commander, preserving unrelated instructions. |
| `docs/commander.md` | Current goal, level, non-goals, acceptance, decisions, role ownership, artifact evidence and next step. | Commander; workers report rather than overwrite shared state. |
| `.codex/commander.local.md` (only if needed) | Verified thread/host bindings and active task/attempt/delivery state. | Commander; excluded from Git before use. |

The local file is not mandatory for solo work. Keep its state compact, and do not
store credentials or entire conversations. Keep public project records portable:
no private chat links, personal host paths or unrelated task titles. Local runtime
identifiers are not portable project memory.

## Safe bootstrap helper

The optional Python 3.10+ helper produces the first two records. It has no network
access and does not create tasks. It defaults to a **read-only preview**:

```sh
python3 <skill-dir>/scripts/project_records.py \
  --root /absolute/path/to/project \
  --language zh-CN \
  --level maintainable \
  --goal '制作一个长期自用的本地工具'
```

After reviewing the paths and having authority to initialize records, repeat
with `--apply`. Pass argument values literally; do not interpolate untrusted
text into executable shell syntax. `en`, `zh-CN` and `zh-TW` are supported. For
other languages, write equivalent records using the host's safe editing tools;
do not silently fall back to English.

The helper:

- Requires an explicit existing root; refuses filesystem, home, and config roots and
  its own skill directory, symlinked output paths, and a root `AGENTS.override.md`.
- Adds or updates only its delimited section in `AGENTS.md`; content outside the
  section is preserved byte-for-byte. Duplicate/malformed markers cause a refusal.
- Creates `docs/commander.md` only when absent. Existing content is never replaced;
  reconcile the live plan and language manually within the authorized scope.
- Checks all intended targets before applying and uses per-file safe writes. On
  macOS/Linux, apply operations are anchored to opened directory handles and
  directory entries are synced after publication and cleanup. Platforms without
  the required Python directory-relative APIs (including Windows) can preview but
  apply is refused rather than silently using weaker path-based writes.
- Serializes **cooperating writers that use this helper**. It is not a transactional
  database and does not provide atomic compare-and-swap against external programs
  that ignore its lock. On supported systems the helper takes a kernel advisory
  lock on its opened project-root directory; it creates no shared lock path, and
  the kernel releases the lock when the descriptor closes or the process exits.
  After a filesystem failure, inspect the reported partial state before rerunning.

Crash-residue cleanup is deliberately narrow. On a rerun, the helper automatically
removes only its versioned temporary carriers that match the current plan's
exact target and content and whose type, owner, link count, inode, and content
prefix remain stable through the anchored checks. The creation time in the carrier
name must predate the current apply; filesystem mtime/ctime are not corroborating
evidence because their clock and precision can differ. Legacy `.commander-<uuid>`
files, carriers from a different goal/language/level plan, and anything with
uncertain origin, name time, type, path, metadata, or content are left untouched.
Inspect those items and remove them manually only after confirming that they are
disposable.
The advisory lock coordinates helper users only: a non-cooperating process with
write access to the same directory can race the final check and deletion, so the
automatic cleanup is not an atomic guarantee against malicious or external writers.

For files the helper rewrites, its preservation promise is limited to ordinary
POSIX permission bits (mode bits) where the platform and operation support them.
Extended attributes, ACLs, filesystem flags, uid, gid, ownership inheritance,
and platform-specific metadata are outside that promise and must be reviewed
separately when they matter.

Read the generated record and replace pending information with actual decisions
as work progresses. A seeded file is not a completed plan or a finished task.

If the project has equivalent instruction/plan documents, integrate into those
instead of running the helper and producing duplicates. Respect more specific
instructions and override files; do not create an override to bypass them.

## Runtime state and recovery

When a team actually needs saved bindings, exclude `.codex/commander.local.md`
using the repository's existing ignore convention (for example a targeted
`.gitignore` entry). Verify it is not already tracked. If tracked, stop before
writing private values and choose an untracked location with the user; an ignore
entry alone does not untrack a file. Do not initialize Git or change global Git
settings just for this step. In a non-Git directory, keep local-only state clearly
separate and disclose the export boundary.

Use ordinary localized tables. Record only the verified commander/worker
bindings, task IDs and current attempts, input version, state, and evidence needed
to resume. Keep the verified project binding and execution location separate
from sidebar section state; default team placement is under that project.
Only record a custom-section override when the user requested it. Put private
project/section IDs in local state, not public project documents. Saved bindings
are aids to a manual, verified restart, not an automatic-recovery mechanism:
after interruption, re-check the project, task state, acceptance, and available
tools before resuming. They do not establish unattended execution or delivery.
Do not duplicate a full task log in several files. On restart, verify
the target project, worker availability, and latest accepted artifact before
dispatch; do not assume persisted IDs are still valid.

Workers do not edit shared commander records or each other's files unless that
ownership was assigned. When scope, language, or an important rule changes,
update the authoritative record and explicitly inform affected active workers.
Changing `AGENTS.md` does not prove that already-running tasks reloaded it.

## Minimal contents, not mandatory bureaucracy

The active record should answer: What are we delivering? What are we not doing?
What engineering level and languages apply? Who owns current outputs? What was
accepted, on what evidence, and what happens next? Keep important decision reasons
when they prevent rediscovery. Do not add ADRs, tickets, dashboards or one file per
agent unless the project actually needs them.
