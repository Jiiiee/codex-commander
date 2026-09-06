#!/usr/bin/env python3
"""Run behavioral cases through an explicitly supplied evaluator command."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "tests/behavioral-cases.json"
RESULT_SCHEMA_VERSION = 1
REQUEST_SCHEMA_VERSION = 1


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
        "skill": "SKILL.md",
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


def run_cases(
    cases: list[dict[str, Any]], command: Sequence[str], timeout: float
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for case in cases:
        request = request_for(case)
        try:
            completed = subprocess.run(
                list(command),
                cwd=ROOT,
                input=json.dumps(request, ensure_ascii=False) + "\n",
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            result = {
                "id": case["id"],
                "status": "failed",
                "request": request,
                "error": {
                    "kind": "timeout",
                    "message": f"evaluator exceeded {timeout:g} seconds",
                },
            }
            stdout = captured_text(exc.output)
            stderr = captured_text(exc.stderr)
            if stdout:
                result["response"] = stdout
            if stderr:
                result["stderr"] = stderr
            results.append(result)
            continue
        except OSError as exc:
            results.append(
                {
                    "id": case["id"],
                    "status": "failed",
                    "request": request,
                    "error": {"kind": "launch", "message": str(exc)},
                }
            )
            continue

        stdout = completed.stdout.rstrip("\n")
        stderr = completed.stderr.rstrip("\n")
        if completed.returncode == 0:
            result: dict[str, Any] = {
                "id": case["id"],
                "status": "completed",
                "request": request,
                "response": stdout,
            }
            if stderr:
                result["stderr"] = stderr
        else:
            result = {
                "id": case["id"],
                "status": "failed",
                "request": request,
                "error": {
                    "kind": "exit",
                    "message": f"evaluator exited with status {completed.returncode}",
                    "exitCode": completed.returncode,
                },
            }
            if stdout:
                result["response"] = stdout
            if stderr:
                result["stderr"] = stderr
        results.append(result)
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
    try:
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=parent, prefix=f".{path.name}.", delete=False
        ) as handle:
            temporary = Path(handle.name)
            json.dump(record, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        if output.is_symlink():
            raise RunnerError(f"refusing symlinked result path: {output}")
        temporary.replace(output)
    except OSError as exc:
        if "temporary" in locals():
            temporary.unlink(missing_ok=True)
        raise RunnerError(f"cannot write result: {exc}") from exc


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
            return 0
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
            results = run_cases(cases, arguments.command, arguments.timeout)
            mode = "run"
        record = build_record(mode, arguments.cases, results)
        write_record(arguments.output, record)
        print(json.dumps(record["summary"], ensure_ascii=False))
        return 1 if record["summary"]["failed"] else 0
    except RunnerError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
