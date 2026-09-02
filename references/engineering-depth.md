# Engineering depth without speculative architecture

Use these levels as conversations about delivery, not mandatory technology
stacks or quality rankings. Fit the change to the existing codebase and its
standards. Re-evaluate when intended use or risk changes; a tiny follow-up does
not require the entire interview again.

| Level | Keep | Do not add without a current need |
| --- | --- | --- |
| Prototype | A complete narrow path; checks that show it works; clear limits; safeguards against relevant harm or data loss. | Generic frameworks, production infrastructure, future extension systems. |
| Maintainable | Understandable boundaries, useful automated regression tests, practical failure handling, reproducible use instructions. | Speculative services, plugin APIs, multi-tenancy, elaborate configuration systems. |
| Production | The specific availability, security, data integrity, deployment/recovery and observability commitments required by actual users. | An enterprise checklist unrelated to the actual product, traffic, or risk. |

No level requires a fixed number of agents, files, tests, or abstraction layers.
A simple monolith can be production-ready for its intended use. A personal script
that changes irreplaceable files still needs protection against data loss.

## Interview for consequences

Prefer a question such as: “Is this a quick experiment, something you will keep
using, or a service other people will depend on?” Localize it. Explain your
recommendation in terms of what gets retained, omitted, and verified.

When “quick and simple” conflicts with real risk, describe the conflict. Offer a
smaller safe scope or isolated demonstration rather than silently increasing
the project or skipping necessary safeguards. Do not equate “public on GitHub”
with “requires a hosted platform.”

Resolve only decisions that change the current delivery. Future ideas may be
recorded as non-goals; their presence is not permission to implement them.

## A complexity check, not an architecture committee

Before a meaningful new dependency, service, abstraction, storage layer, or
process, be able to explain:

- Which current requirement or demonstrated problem needs it?
- Why is the existing or simpler approach insufficient?
- What maintenance/integration cost does it introduce?

Do not produce a separate document for every ordinary implementation choice.
Escalate only material scope, cost, compatibility, or operational changes.
Do not force artificial code/file-count ceilings that reward unreadable code.

In review, check both missing requirements and unrequested behavior. Remove
speculative generality when it has no current value, but do not delete necessary
tests, error handling, or useful structure just to look smaller. Existing project
standards and real requirements take precedence over generic smell heuristics.

## Right-size the team

Ask whether another worker provides an independently checkable deliverable,
needed isolation of context, or valuable independent verification. Account for
briefing, shared state, and integration costs. Time saved in parallel does not
automatically mean fewer tokens or lower cost.

Start with the work that exists. Reuse suitable workers before creating more.
Keep tightly coupled changes with one owner. A single implementation owner can
still receive a focused review when risk warrants it. There is no required
architect, project manager, security department, or “simplicity agent.”

## Examples

- Rename a button: implement and check the affected UI; no team bootstrap.
- One-off photo renaming: preview names, detect collisions, protect originals;
  no cloud backend or plugin system.
- A regularly used local tool: add meaningful regression coverage and clear
  setup instructions without prebuilding a SaaS architecture.
- A narrow change to critical data handling: high assurance can be required even
  with one implementation owner.
- A prototype with independent code and illustration work: a small team can be
  useful without elevating every artifact to production engineering.
