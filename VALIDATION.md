# Validation status

Version: 0.2.0. Date: 2026-09-06.

## Historical automated-check snapshot (pre-integration)

This table is a preserved pre-integration snapshot, not evidence for the
integrated candidate documented below. Its 61-test count and clean package
check applied to that earlier source snapshot only.

| Check | Observed result |
| --- | --- |
| `python3.11 -B -m unittest discover -s tests -v` | 61 tests passed on macOS. |
| `python3.12 -B -m unittest discover -s tests -v` | 61 tests passed on macOS. |
| `python3 -B scripts/check_package.py` | Passed: required resources, local links, Python/JSON syntax, and the package's narrow portability checks. |
| Codex `skill-creator` bundled `quick_validate.py` | Passed: `Skill is valid!` |
| `agents/openai.yaml` | Unchanged from the parsed and length-checked 0.1.1 version. |
| Retained upstream MIT notice | Unchanged from 0.1.1, which was byte-identical to the reviewed upstream license. |

The unit tests use isolated temporary directories and cover release metadata,
checksums, new records,
English/Simplified/Traditional Chinese, all engineering levels, idempotency,
byte preservation, existing plans, malformed markers, unsafe roots, symlinks,
changed files, mode-bit preservation, and partial failure reporting. They do not
preserve or verify xattrs, ACLs, filesystem flags, uid, gid, or their inheritance.
The 0.1.1 regression additionally checks that replacing legacy managed rules
preserves the existing plan and unrelated instruction bytes, then becomes a
no-op on a repeated run.

The package's own tests and helpers use only the standard library. The separate
bundled Codex validator needed PyYAML, which was supplied in an isolated tool
environment rather than added as a runtime dependency of this skill.

## Historical v0.2.0 local-candidate snapshot

The following checks were run locally on macOS on 2026-09-06 and describe an
earlier local-candidate snapshot, before later integrated changes. Its 61-test
count and clean package check are historical only. `Intended tag: v0.2.0` labels
a local candidate only; it is not evidence of a local or remote Git tag. A
remote tag and a GitHub Release must be verified separately.

| Check | Observed result |
| --- | --- |
| `python3.11 -B -m unittest discover -s tests -v` | 61 tests passed. |
| `python3.11 -B scripts/check_package.py` | Passed. |
| `python3.12 -B -m unittest discover -s tests -v` | 61 tests passed. |
| `python3.12 -B scripts/check_package.py` | Passed. |
| `.github/workflows/ci.yml` | Configures Ubuntu and macOS targets for Python 3.10–3.13. No GitHub-hosted workflow execution was observed or is claimed. |

Python 3.10–3.13 are configured targets. This historical record contains local
evidence only for 3.11 and 3.12. Python 3.9 is not a supported version even if
an invocation happens to run. See the README compatibility matrix for the
distinction between declared support, configured CI, and observed local evidence.

## Version 0.2.0: automated quality and safe record writes

This release candidate adds a GitHub Actions matrix, a 13-case behavioral
runner with machine-readable results, stricter structural validation, and
negative tests for malformed package metadata. Project-record apply operations
now use directory-relative file descriptors, durable directory synchronization,
and a kernel advisory lock on supported macOS/Linux systems. Preview remains
available on platforms without the required primitives, including Windows,
while apply safely refuses there.

Crash-recovery tests cover the intentionally fail-closed residue boundary: only
newer carriers for the exact current plan with stable metadata are eligible for
automatic cleanup. Legacy and different-plan carriers remain for user-confirmed
manual handling. The kernel lock coordinates helper invocations; it does not make
the final check-and-delete sequence atomic against non-cooperating writers that
can modify the same directory.

The bilingual documentation now distinguishes documented support, configured
CI, and observed local evidence; it also documents local upgrade and
maintenance boundaries. `RELEASE_NOTES.md` declares version `0.2.0` and the
intended tag `v0.2.0`. `RELEASE_CHECKSUMS.txt` records SHA-256 values for every
release-payload file except the checksum manifest itself. The package checker
verifies only internal version, file-set, and hash consistency; it does not prove
source provenance, a local or remote Git tag, a GitHub Release, or resistance to
malicious tampering.

## Integrated-candidate verification

This verification was run locally on macOS on 2026-09-06 against the later
integrated candidate. Its 71-test count supersedes the earlier 61-test snapshots
above for this candidate. It is local evidence, not a hosted CI run, a
remote-tag check, or a GitHub Release check.

| Check | Observed result |
| --- | --- |
| `python3.11 -B -m unittest discover -s tests -v` | 71 tests passed. |
| `python3.12 -B -m unittest discover -s tests -v` | 71 tests passed. |
| Runner `--list` and `--dry-run` | Listed 13 packaged cases; dry-run planned 13 and completed none. |
| `scripts/check_package.py` | Reported only `RELEASE_CHECKSUMS.txt` hash mismatches for integrated candidate files. |
| `SKILL.md` byte comparison | Unchanged from the integrated-candidate input commit. |

`RELEASE_CHECKSUMS.txt` was intentionally not updated at this intermediate
stage. The final candidate gate recomputed it from the reviewed candidate; until
then, the package checker correctly reported manifest drift rather than a clean
package result.

## Historical pre-COD-38 final local-candidate gate

This historical local gate was run on macOS on 2026-09-06 before COD-38, after
integrating the then-current candidate and regenerating `RELEASE_CHECKSUMS.txt`
from its release payload. Its 135-test count is not the current test count. This
is local candidate evidence only. It does not substitute for the
required hosted Ubuntu/macOS and Python 3.10–3.13 matrix, independent review,
remote-tag verification, or GitHub Release verification. Any later integration
that changes a packaged file requires the release coordinator to rebuild this
checksum manifest before the final gate is repeated.

| Check | Observed result |
| --- | --- |
| `python3.11 -B -m unittest discover -s tests -v` | 135 tests passed. |
| `python3.12 -B -m unittest discover -s tests -v` | 135 tests passed. |
| `python3.11 -B scripts/check_package.py` | Passed with no structural or manifest errors. |
| `python3.12 -B scripts/check_package.py` | Passed with no structural or manifest errors. |
| Runner `--list` and `--dry-run` | Listed 13 packaged cases; dry-run planned 13 and completed none. |
| `.github/workflows/ci.yml` | Parsed locally and configures eight Ubuntu/macOS and Python 3.10–3.13 jobs; hosted results remain a release gate. |
| Git candidate state | `VERSION` was `0.2.0`, the checksum manifest matched that historical release payload, and the reviewed worktree was clean. |

The checksum result establishes internal file-set, version, and hash
consistency only. The provenance and publication limitations stated above still
apply.

## COD-38 v0.5 detection-contract local gate (attempt 3)

The v0.5 path-detection contract was implemented and checked locally on macOS
on 2026-09-07. This evidence is limited to the current working tree: no hosted
CI, tag, release, push, or remote service was used.

| Check | Observed result |
| --- | --- |
| Frozen contract formal copy | The repository copy has pinned SHA-256 `263ef806c44c9c0fc2c526528fe8871c6bdc1ce57e8b00e6cb8a2832d38f52d0`; the regression test reads only this repository copy and has no temporary-host-file dependency. |
| Independent v0.5 fixture | 60 cases passed through public scanner entry points, covering clauses 2–8, strict UTF-8, POSIX/Windows/UNC paths (including a leafless dual-placeholder UNC), URL components/boundaries and empty ports, arbitrary-length ASCII numeric entities, bounded mixed decoding, source lines, windows, token limits, report priority, and a manifest-listed symbolic link. |
| Manifest symbolic-link structure check | A checksum-listed symbolic link is rejected before target resolution by both `scan_release_paths()` and `check()`, even when its target is valid UTF-8 and the manifest hash matches the target bytes. |
| `python3.11 -B -m unittest discover -s tests` | 141 tests passed locally in 136.71 seconds (`time -p` real). |
| `python3.12 -B -m unittest discover -s tests` | 141 tests passed locally in 135.70 seconds (`time -p` real). |
| Work counters at 131,072 and 262,144 characters | Work was 1,731,600 and 3,519,060 characters (ratio 2.0323); maximum states 3, depth 2, and window 16,384. |
| Package and supporting local gates | The package check, fixture JSON parse, runner list/dry-run, checksum verification, and local skill validation passed. |

The checksum manifest is the complete scan set for the release payload, not an
inventory of every repository review artifact. The frozen contract document is
retained verbatim as required review evidence outside that payload because it
necessarily contains literal reject examples. The independently executable JSON
fixture is part of the release payload and checksum set; its encoded source
spelling prevents fixture data from masquerading as an accidental machine-path
leak while JSON decoding restores the exact runtime inputs. The package's
file-set check explicitly asserts this one review-evidence boundary.

Attempt 2 also evaluated replacing the historical
`contains_machine_specific_path` implementation with a direct `scan_text`
compatibility adapter. The old implementation and its supporting parser occupy
755 source lines (lines 38–792 in this snapshot); direct substitution produced
970 failing subtests across 48 legacy test methods because that API deliberately
implements pre-v0.5 wrapper/residual rules, including out-of-scope behavior.
Removing it safely therefore requires a separate migration: classify the legacy
cases against v0.5, move any still-required public behavior into the independent
fixture, update callers, and then delete the old parser and its private-helper
tests as one reviewed change. COD-38 keeps the legacy API unchanged rather than
silently changing those callers.

The historical pre-COD-38 package checker treated an ambiguous wrapped URL
followed by bounded, interleaved residual tokens and structural separators that
lead to `token=machine-path` as unsafe and fails closed. This is a deliberate
safety boundary: network paths that would otherwise be ambiguous should use an
explicit Markdown link or autolink form. Residual scanning applies separate
64-character bounds to token and separator characters and a source window
derived from the three-layer percent-decoding limit; truncation, incomplete
tokens, invalid escapes, and exhausted decode depth also fail closed.

That historical scanner gate additionally covered repeated and alternating wrapper
closers, wrapper openers, paired punctuation, braces, and bounded HTML entities
as grammar-derived document evidence in both raw and percent-decoded residuals.
The historical regression suite exercises those cross-category combinations as
part of the 135-test pre-COD-38 snapshot reported above, together with explicit-link and benign URI
token controls. Its maximum/overflow and linear-work assertions are also part of
that reproducible candidate suite.

## COD-45 raw-URL prescan linearization (attempt 1)

The v0.5 raw-URL region prescan was repaired and checked locally on macOS on
2026-09-07. The frozen contract, fixture, decoding and scan scope were unchanged;
no hosted CI, push, pull request, tag, release, or external review was used.

| Check | Observed result |
| --- | --- |
| Independent adversarial regression | A deterministic 131,072/262,144-character fixture combines an 8,192-character prefix with dense HTTP(S) starts. The pre-fix URL and no-URL controls both reported 761,856/1,548,288 work (zero classifier delta), exposing the accounting gap. |
| Counted linear work after repair | URL work was 1,254,270 and 2,557,205 characters; the ratio was 2.0388. The corresponding absolute limits were 8,912,896 and 17,301,504. No-URL control work was 1,015,808 and 2,064,384, so raw URL classifier deltas were 238,462 and 492,821. |
| Detection compatibility | All 60 frozen fixture cases passed, and 5,000 deterministic adversarial inputs produced identical structured reports before and after the prescan change. |
| Full local suite | All 156 tests passed, comprising the previous 155 behaviors plus the new adversarial regression. |
| Package and supporting local gates | The package check, checksum verification, runner list, runner dry-run to a temporary output path, and diff whitespace check passed. |

## Version 0.1.3: bilingual publication preparation

Added a complete Simplified Chinese README with reciprocal language links.
Both versions cover the same workflow, familiar sidebar-agent terminology,
installation, project placement, permissions, limitations, validation and
attribution. The package checker now requires both README files. The skill's
runtime instructions, record-writing helper and localized templates are unchanged
from 0.1.2. The 31 file-operation tests, structural checker and bundled skill
validator were rerun successfully; no new live-agent evaluation is claimed.

The publication candidate was reviewed as an explicit allowlist of 18 regular
text files. Source and Git-index checks found no recognized credential formats,
credential assignments, personal host paths or private runtime thread IDs.
Credential-related wording was reviewed as safety guidance, not actual values.
The only packaged agent configuration is UI metadata containing a display name
and short description; it contains no authentication or provider settings.

No environment files, private-key files, credential configuration, local task
bindings, media, cached bytecode or old distribution archives are staged.
Environment-file ignore rules supplement the explicit file selection; ignoring
a file is not treated as proof that an already tracked file is safe.

This is scoped source/index review and signature checking, not a guarantee that
every possible secret format can be detected or a comprehensive security audit.
The repository starts with a new history containing only the reviewed files.

## Version 0.1.2: terminology clarification with the familiar name retained

The skill and public documentation retain **sidebar agent / 侧边栏代理 /
側邊欄代理** as supported user-facing names and pair them with independent task
threads on first explanation. Cross-task collaboration and cross-thread
orchestration describe the workflow, not an official feature or agent type.
Native subagents can also use threads; the distinction is the verified task
operations, not screen position or an assumed parent/child hierarchy.

This is an instruction/documentation-only revision. Executable helpers, generated
record templates, UI metadata, resource paths, and the project-placement policy
remain unchanged. Comparison against the previous archive found no unrelated
source changes. Both earlier release archives are retained.

The 31 existing file-operation tests, package structural checker, and bundled
skill validator were rerun successfully. The bundled validator ran through
`uv run --no-project --with PyYAML python -B`; plain Python did not have PyYAML.
The skill itself still has no new runtime dependency.

Two raw behavioral scenarios were added: a terminology-only Chinese discussion,
and an explicit request to create project-scoped sidebar agents when both task
and native-subagent tools exist. Their review criteria cover retaining the name,
avoiding unrequested setup, and selecting independent tasks without a custom
section. These new scenarios have not been run in independent agent contexts or
against a live app; adding them is not a behavioral pass claim. The older probe
results below remain historical results for their stated versions.

## Version 0.1.1: project-placement correction

Real use of 0.1.0 exposed a routing failure: tasks were bound to the correct
saved project, but an unsolicited custom sidebar section was also created and
passed to the delegated commander as the desired team location. A review of
the reported conversation established the extra section-creation and regrouping
calls; the same conversation later corrected its team placement. No existing
team or project was mutated during this skill update.

The correction separates project membership, execution location, and sidebar
organization. Project teams now default to the verified project's normal
grouping, including a newly delegated commander. Explicit custom-section
requests remain supported. Missing saved-project registration is a prerequisite,
not a reason to create projectless tasks or a substitute section. The English,
Simplified Chinese, and Traditional Chinese record templates carry the policy.

Three new raw cases cover default project placement, an explicitly requested
custom section, and an unregistered current directory. Each was evaluated in a
fresh agent context with only the skill and that case, not the review rubric or
prior conclusions. The integrator read all three reports and intended calls:

- Default: used the verified project/local creation target, carried the
  project/default-placement policy into the new commander's prompt, and made no
  section/pin/move calls. The whole project's existing section was preserved.
- Explicit section: used the verified project/worktree target and moved only
  the two new task IDs to the section returned by the requested creation; no
  project move or unrelated-task change was proposed.
- Missing project: surfaced the missing saved-project binding without creating
  projectless tasks, using an unrelated project, or inventing a section fallback.

All three met these placement-specific checks in simulation. Runtime IDs and
unobserved placement remained unresolved rather than being reported as success.
No real sidebar creation or reorganization was part of this regression run;
this does not establish live task delivery or automatic resumption.

## Version 0.1.0: independent behavioral probes

Eight raw cases were initially exercised in two separate agent contexts. This
was exploratory batching, not eight fully independent conversations. Three
targeted single-case probes then used fresh contexts: per-artifact language,
worker mode, and pending sidebar creation. Evaluators received the skill and raw
scenario inputs, not the evaluation rubric or suggested answers. The integrator
read the resulting responses and intended calls.

Observed decision boundaries included:

- Chinese planning stayed in Chinese and did not create files or tasks.
- An English README request did not change the Chinese language of conversation
  and team records; the fresh probe kept unknown product requirements unresolved.
- Missing sidebar tools were disclosed without invoking native subagents as a
  silent substitute.
- Pending creation IDs were not used as thread addresses; defaults/worktree
  selection were preserved, and the fresh probe respected the supplied wait cap.
- A stale task/attempt report did not authorize acceptance, redispatch, or public
  deployment.
- Worker mode stayed within the assigned document scope rather than repeating
  the project interview or recruiting a team.
- A small production UI change was planned as a narrow solo change, not a team
  or architecture expansion.

One case performed real filesystem work in a disposable fixture: it appended a
Chinese Commander section and created a Chinese project record. The original
English instruction bytes were independently checked and preserved. Only the
two authorized files existed afterward; a subsequent helper preview reported
both as unchanged. No live project was used.

Review prompted two coordination clarifications: a prematurely opened dependent
worker gets a setup-only assignment and stops on its missing dependency; a
native wait's default duration must not override the caller's blocking cap.
The pending-creation fresh probe used those clarified instructions.

These are reviewed samples of decisions, not a numerical success-rate estimate
or end-to-end agent execution. The probes did not execute the full dependency
resume/attempt-rollover or missing-dispatch-record recovery sequence. Artifact
creation, message delivery, identity recovery, and resumption still need real
host tests before unattended use. Raw local probe outputs are not distributed.

## Not established

- Live sidebar creation and callback delivery for this skill version.
- Reliable wake-up after app shutdown, quota exhaustion, or interruption.
- Exactly-once delivery, crash-safe transactions, or external/non-cooperating
  record writers that do not follow the helper's kernel advisory lock.
- Lower token cost, faster completion, or universally improved output quality.
- Windows/Linux execution testing or exhaustive support for other languages.

See [the evaluation procedure](tests/behavioral-evaluation.md) for the distinction
between file-operation tests and agent/runtime validation.
