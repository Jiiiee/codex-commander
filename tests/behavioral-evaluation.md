# Behavioral evaluation

Unit tests validate file operations. They do not validate an LLM's interpretation
of a workflow. Run the cases in `behavioral-cases.json` with an independent agent
that receives the skill and the scenario's raw inputs, not this rubric or a
suggested answer. Use fresh context per case when evaluating release changes.

## Runner

The standard-library runner makes the 13 case inputs and evaluator outputs
repeatable without claiming that a completed subprocess is a behavioral pass.
It never creates real tasks itself.

First inspect the ordered case IDs, then create a dry-run record:

```sh
python3 scripts/run_behavioral_cases.py --list
python3 scripts/run_behavioral_cases.py --dry-run \
  --output .local-evaluation/behavioral-results.json
```

`--dry-run` does not accept or launch an evaluator command. Real evaluation is a
separate, explicit boundary: `--run` requires `--command`, starts that command
once per case, sends one JSON request on standard input, and records standard
output, standard error, exit failures, or timeouts. The command must create a
fresh agent context, load `SKILL.md`, and expose only the request's raw `case`
fields to the evaluator. It must not expose this rubric or a suggested answer.

```sh
python3 scripts/run_behavioral_cases.py --run \
  --output .local-evaluation/behavioral-results.json \
  --command /path/to/isolated-evaluator
```

The result file uses schema version 1 and preserves source order. Each item is
`planned`, `completed`, or `failed`; the process exits nonzero when any evaluator
fails but still records later cases. A `completed` item is raw evidence awaiting
review against the criteria below, not an automatic pass. Use repeated `--case`
options to rerun affected cases. Keep result files under the ignored
`.local-evaluation/` directory unless a separate sanitized publication is
explicitly approved.

For the filesystem case, give the evaluator an isolated temporary project with
an existing `AGENTS.md`. Let it use the real helper or safe edits there. Never
give it live customer projects, credentials, or permission to create real tasks.

For independent-task/sidebar-agent cases, use explicitly simulated tool
observations. Record intended calls and user-facing responses without calling
the real app. This checks decisions and contract construction, **not live
delivery or wake-up behavior**.

Judge outcomes, not matching phrases:

- Does the response use the user's language, despite English source material?
- Does a per-artifact language choice override the default appropriately?
- Does discussion remain discussion, without implementation or setup writes?
- Is "sidebar agent / 侧边栏代理" retained as a usable familiar name while
  explaining independent tasks and cross-thread communication, without claiming
  an official agent type or an inherent parent/child hierarchy?
- When sidebar agents are explicitly requested as independent app tasks, does
  execution use the independent-task route rather than native subagents, without
  treating the terminology as authorization for extra tasks or sidebar sections?
- Are actual scope, risk, and independent work used to select depth/team size?
- Does missing sidebar capability remain visible, without a silent substitute?
- Are pending IDs kept separate from usable thread IDs?
- Do project-team tasks bind to the verified saved project and remain under it
  by default, including when a new commander recruits the workers?
- Are custom sections used only on explicit request, without confusing their
  IDs with project IDs or rearranging unrelated projects?
- Does a missing saved-project match remain a prerequisite rather than causing
  a projectless/custom-section fallback?
- Are workers given the correct scope, ownership, language, destination and
  completion/blocker reporting requirements?
- Are stale or duplicate reports prevented from authorizing new work?
- Are artifacts checked before acceptance and scope-changing actions stopped?
- Do new Chinese records preserve existing unrelated rules and avoid false
  claims that a team was created or a deliverable accepted?

Keep raw outputs in local evaluation storage. Publish only sanitized summaries
that distinguish actual filesystem tests, simulated decisions, and live tests.
If a failure appears, fix the narrow cause and repeat the affected case; do not
append a universal rule for every surprising wording choice.

Before advertising unattended sidebar operation, separately obtain permission
for a live smoke test: create a small task, receive its report in the intended
commander, verify the artifact, and exercise interruption/recovery. Such a test
must run in the actual target host. This package's local test suite does not do it.
