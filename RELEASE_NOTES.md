# Codex Commander v0.2.0

Version: 0.2.0
Intended tag: v0.2.0
Status: release candidate; no tag or release has been created.

## Highlights

- Adds GitHub Actions coverage for Python 3.10, 3.12, and 3.13 on Ubuntu and
  macOS. The workflow is configured but no hosted run is claimed.
- Adds a 13-case behavioral runner with list, dry-run, selected-case, and
  machine-readable result modes.
- Hardens project-record writes with directory-relative file descriptors,
  durable directory synchronization, symlink defenses, and a kernel advisory
  lock for cooperating writers.
- Adds deterministic concurrency, crash, package-metadata, and behavioral-runner
  regressions.
- Expands English and Simplified Chinese compatibility, maintenance, upgrade,
  terminology, attribution, and evidence documentation.

## Compatibility and boundaries

- The skill itself remains instruction-first and has no runtime dependency
  beyond the Python standard library used by its optional helpers and tests.
- Python 3.10–3.13 is the documented range. Local verification covers Python
  3.11 and 3.12 on macOS; configured CI targets are not reported as completed.
- Project-record preview is portable. Apply requires the directory-relative and
  advisory-lock primitives available on supported macOS/Linux systems and
  safely refuses on Windows or other platforms without them.
- The advisory lock serializes cooperating helper writers. External programs
  that ignore the lock do not receive an atomic compare-and-swap guarantee.

## Verification

- Python 3.11: 61 unit tests and the package check pass locally.
- Python 3.12: 61 unit tests and the package check pass locally.
- The behavioral runner lists 13 packaged cases; dry-run records all 13 without
  launching case commands.
- `git diff --check` passes.
- [RELEASE_CHECKSUMS.txt](RELEASE_CHECKSUMS.txt) is the SHA-256 manifest for the
  exact candidate source tree, excluding the manifest itself.

## Maintainer release sequence

After human acceptance, create the annotated tag `v0.2.0` from the reviewed
commit, verify the tag resolves to that commit, generate any distribution
archive from the tag, and publish these notes with the resulting archive
checksum. None of those release actions are part of this candidate preparation.
