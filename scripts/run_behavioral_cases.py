#!/usr/bin/env python3
"""Run behavioral cases through an explicitly supplied evaluator command."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
from typing import Any, Callable, Sequence
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "tests/behavioral-cases.json"
SKILL_SOURCE = ROOT / "SKILL.md"
SKILL_REQUEST_PATH = Path("SKILL.md")
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]*\]\((?P<target><[^>]+>|[^\s)]+)")
RESULT_SCHEMA_VERSION = 1
REQUEST_SCHEMA_VERSION = 1
EXIT_SUCCESS = 0
EXIT_CASE_FAILURE = 1
EXIT_RUNNER_FAILURE = 2
EXIT_INTERRUPTED = 130
TIMEOUT_TERMINATION_SCOPE = "process-group" if os.name == "posix" else "evaluator-process"


class RunnerError(Exception):
    """A user-facing configuration or input error."""


def load_cases(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RunnerError(f"cannot read cases: {exc}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RunnerError(f"cases must be valid UTF-8 JSON: {exc}") from exc

    if not isinstance(data, list) or not data:
        raise RunnerError("cases must be a nonempty JSON array")
    seen: set[str] = set()
    for index, case in enumerate(data):
        if not isinstance(case, dict):
            raise RunnerError(f"case {index} must be an object")
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise RunnerError(f"case {index} id must be a nonempty string")
        if case_id in seen:
            raise RunnerError(f"duplicate case id: {case_id}")
        seen.add(case_id)
        if not isinstance(case.get("user"), str) or not case["user"].strip():
            raise RunnerError(f"case {case_id} user must be a nonempty string")
        if not isinstance(case.get("context"), (str, dict)):
            raise RunnerError(f"case {case_id} context must be a string or object")
    return data


def select_cases(cases: list[dict[str, Any]], selected: Sequence[str]) -> list[dict[str, Any]]:
    if not selected:
        return cases
    wanted = set(selected)
    available = {case["id"] for case in cases}
    missing = sorted(wanted - available)
    if missing:
        raise RunnerError(f"unknown case id(s): {', '.join(missing)}")
    return [case for case in cases if case["id"] in wanted]


def request_for(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": REQUEST_SCHEMA_VERSION,
        "skill": str(SKILL_REQUEST_PATH),
        "freshContextRequired": True,
        "case": {
            "id": case["id"],
            "user": case["user"],
            "context": case["context"],
        },
    }


def dry_run(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"id": case["id"], "status": "planned", "request": request_for(case)}
        for case in cases
    ]


def skill_snapshot_sources() -> list[tuple[Path, Path]]:
    """Return the smallest package-root-local closure of Markdown references."""
    package_root = SKILL_SOURCE.parent.resolve()
    pending = [SKILL_SOURCE]
    sources: list[tuple[Path, Path]] = []
    seen: set[Path] = set()

    while pending:
        candidate = pending.pop(0)
        try:
            source = candidate.resolve(strict=True)
            relative = source.relative_to(package_root)
        except (OSError, ValueError) as exc:
            raise RunnerError(f"invalid skill package reference: {candidate}") from exc
        if source in seen:
            continue
        if not source.is_file():
            raise RunnerError(f"skill package reference is not a file: {relative}")

        seen.add(source)
        sources.append((source, relative))
        if source.suffix.lower() != ".md":
            continue
        try:
            content = source.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise RunnerError(f"cannot read skill package file {relative}: {exc}") from exc
        for match in MARKDOWN_LINK.finditer(content):
            target = match.group("target").strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            linked = source.parent / unquote(parsed.path)
            if linked.suffix.lower() == ".md":
                pending.append(linked)

    return sources


def stage_skill_snapshot(workdir: Path) -> None:
    for source, relative in skill_snapshot_sources():
        destination = workdir / relative
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
            destination.chmod(0o444)
        except OSError as exc:
            raise RunnerError(f"cannot stage skill package file {relative}: {exc}") from exc


def evaluator_environment(workdir: Path) -> dict[str, str]:
    package_root = str(SKILL_SOURCE.parent.resolve())
    environment = {
        name: value for name, value in os.environ.items() if package_root not in value
    }
    environment.pop("OLDPWD", None)
    environment["PWD"] = str(workdir.resolve())
    return environment


def _terminate_evaluator(process: subprocess.Popen[str]) -> None:
    """Stop the evaluator boundary without leaving POSIX descendants running."""
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
            return
        except ProcessLookupError:
            return
        except OSError:
            pass
    try:
        process.kill()
    except ProcessLookupError:
        pass


def _drain_evaluator(process: subprocess.Popen[str]) -> tuple[str, str]:
    try:
        return process.communicate(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return "", ""


def run_case(
    case: dict[str, Any], command: Sequence[str], timeout: float
) -> dict[str, Any]:
    request = request_for(case)
    input_text = json.dumps(request, ensure_ascii=False) + "\n"

    # A fresh writable directory is the complete filesystem boundary we can
    # provide portably. Supply the skill's local Markdown reference closure as a
    # read-only snapshot so relative links resolve without passing the repository
    # path to the evaluator. POSIX additionally gets a fresh process group so a
    # timeout or interrupt can terminate descendants.
    with tempfile.TemporaryDirectory(prefix="behavioral-evaluator-") as workdir:
        evaluator_cwd = Path(workdir).resolve()
        stage_skill_snapshot(evaluator_cwd)

        popen_options: dict[str, Any] = {
            "cwd": evaluator_cwd,
            "env": evaluator_environment(evaluator_cwd),
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
        }
        if os.name == "posix":
            popen_options["start_new_session"] = True
        elif hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
            popen_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        try:
            process = subprocess.Popen(list(command), **popen_options)
        except OSError as exc:
            return {
                "id": case["id"],
                "status": "failed",
                "request": request,
                "error": {"kind": "launch", "message": str(exc)},
            }

        try:
            stdout, stderr = process.communicate(input=input_text, timeout=timeout)
        except subprocess.TimeoutExpired:
            _terminate_evaluator(process)
            stdout, stderr = _drain_evaluator(process)
            result: dict[str, Any] = {
                "id": case["id"],
                "status": "failed",
                "request": request,
                "error": {
                    "kind": "timeout",
                    "message": f"evaluator exceeded {timeout:g} seconds",
                    "terminationScope": TIMEOUT_TERMINATION_SCOPE,
                },
            }
            stdout = captured_text(stdout)
            stderr = captured_text(stderr)
            if stdout:
                result["response"] = stdout
            if stderr:
                result["stderr"] = stderr
            return result
        except BaseException:
            _terminate_evaluator(process)
            _drain_evaluator(process)
            raise

    stdout = captured_text(stdout)
    stderr = captured_text(stderr)
    if process.returncode == 0:
        result = {
            "id": case["id"],
            "status": "completed",
            "request": request,
            "response": stdout,
        }
        if stderr:
            result["stderr"] = stderr
        return result

    result = {
        "id": case["id"],
        "status": "failed",
        "request": request,
        "error": {
            "kind": "exit",
            "message": f"evaluator exited with status {process.returncode}",
            "exitCode": process.returncode,
        },
    }
    if stdout:
        result["response"] = stdout
    if stderr:
        result["stderr"] = stderr
    return result


def run_cases(
    cases: list[dict[str, Any]],
    command: Sequence[str],
    timeout: float,
    on_result: Callable[[list[dict[str, Any]]], None] | None = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for case in cases:
        results.append(run_case(case, command, timeout))
        if on_result is not None:
            on_result(results)
    return results


def captured_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return value.rstrip("\n")


def build_record(mode: str, source: Path, results: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"planned": 0, "completed": 0, "failed": 0}
    for result in results:
        counts[result["status"]] += 1
    try:
        source_label = str(source.resolve().relative_to(ROOT))
    except ValueError:
        source_label = str(source.resolve())
    return {
        "schemaVersion": RESULT_SCHEMA_VERSION,
        "mode": mode,
        "source": source_label,
        "summary": {"total": len(results), **counts},
        "results": results,
    }


def write_record(path: Path, record: dict[str, Any]) -> None:
    output = Path(os.path.abspath(path))
    if output.is_symlink():
        raise RunnerError(f"refusing symlinked result path: {output}")
    parent = output.parent
    temporary: Path | None = None
    try:
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=parent, prefix=f".{path.name}.", delete=False
        ) as handle:
            temporary = Path(handle.name)
            json.dump(record, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if output.is_symlink():
            raise RunnerError(f"refusing symlinked result path: {output}")
        temporary.replace(output)
        temporary = None
    except OSError as exc:
        raise RunnerError(f"cannot write result: {exc}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    result.add_argument("--case", action="append", default=[], help="run only this case id; repeatable")
    mode = result.add_mutually_exclusive_group(required=True)
    mode.add_argument("--list", action="store_true", help="print case ids without writing a result")
    mode.add_argument("--dry-run", action="store_true", help="record requests without launching an evaluator")
    mode.add_argument("--run", action="store_true", help="launch the evaluator once per selected case")
    result.add_argument("--output", type=Path, help="result JSON path; required for dry-run and run")
    result.add_argument("--timeout", type=float, default=300.0, help="per-case evaluator timeout in seconds")
    result.add_argument(
        "--command",
        nargs=argparse.REMAINDER,
        help="evaluator executable and arguments; required with --run and never invoked by --dry-run",
    )
    return result


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        cases = select_cases(load_cases(arguments.cases), arguments.case)
        if arguments.list:
            if arguments.output or arguments.command:
                raise RunnerError("--list does not accept --output or --command")
            print(json.dumps({"schemaVersion": 1, "cases": [case["id"] for case in cases]}, ensure_ascii=False))
            return EXIT_SUCCESS
        if arguments.output is None:
            raise RunnerError("--output is required with --dry-run and --run")
        if arguments.timeout <= 0:
            raise RunnerError("--timeout must be greater than zero")
        if arguments.dry_run:
            if arguments.command:
                raise RunnerError("--dry-run never accepts or launches --command")
            results = dry_run(cases)
            mode = "dry-run"
        else:
            if not arguments.command:
                raise RunnerError("--command is required with --run")
            mode = "run"
            results = []
            write_record(arguments.output, build_record(mode, arguments.cases, results))
            results = run_cases(
                cases,
                arguments.command,
                arguments.timeout,
                on_result=lambda current: write_record(
                    arguments.output, build_record(mode, arguments.cases, current)
                ),
            )
        record = build_record(mode, arguments.cases, results)
        if mode == "dry-run":
            write_record(arguments.output, record)
        print(json.dumps(record["summary"], ensure_ascii=False))
        return EXIT_CASE_FAILURE if record["summary"]["failed"] else EXIT_SUCCESS
    except KeyboardInterrupt:
        print(json.dumps({"error": "interrupted; completed results were preserved"}), file=sys.stderr)
        return EXIT_INTERRUPTED
    except RunnerError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return EXIT_RUNNER_FAILURE
    except Exception as exc:
        print(
            json.dumps(
                {"error": f"runner failure: {type(exc).__name__}: {exc}"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return EXIT_RUNNER_FAILURE


if __name__ == "__main__":
    sys.exit(main())
