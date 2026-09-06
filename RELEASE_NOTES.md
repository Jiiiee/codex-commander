# Codex Commander v0.2.0

Version: 0.2.0
Intended tag: v0.2.0
Status: local candidate metadata; release state is not inferred by this document.

`Intended tag` labels the local candidate only. It is not evidence of a local or
remote Git tag. A remote tag and a GitHub Release are separate publication facts
and must be verified in their respective services.

## Highlights

- Adds GitHub Actions coverage for Python 3.10–3.13 on Ubuntu and
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
- Keeps `SKILL.md` byte-for-byte unchanged; the core instruction workflow and
  its runtime behavior are unchanged by this release-documentation update.

## Compatibility and boundaries

- The skill itself remains instruction-first and has no runtime dependency
  beyond the Python standard library used by its optional helpers and tests.
- Python 3.10–3.13 is the documented range; Python 3.9 is unsupported even if
  it happens to run locally. Local verification covers Python
  3.11 and 3.12 on macOS; configured CI targets are not reported as completed.
- Project-record preview is portable. Apply requires the directory-relative and
  advisory-lock primitives available on supported macOS/Linux systems and
  safely refuses on Windows or other platforms without them.
- The advisory lock serializes cooperating helper writers. External programs
  that ignore the lock do not receive an atomic compare-and-swap guarantee.

## Verification

- Local verification results are recorded in [VALIDATION.md](VALIDATION.md);
  configured CI targets are not evidence of a completed hosted run.
- The behavioral runner lists 13 packaged cases; dry-run records all 13 without
  launching case commands.
- `git diff --check` passes.
- [RELEASE_CHECKSUMS.txt](RELEASE_CHECKSUMS.txt) checks only the candidate's
  internal file set, version string, and SHA-256 values, excluding the manifest
  itself. It does not prove source provenance, the existence of a Git tag, or
  protection against malicious substitution or tampering.

## Maintainer release sequence

After human acceptance, verify the reviewed local candidate, then create and
verify the annotated remote tag `v0.2.0`, generate any distribution archive from
that verified tag, and separately publish and verify the GitHub Release with its
archive checksum. The local candidate, remote tag, and GitHub Release remain
distinct checkpoints.
