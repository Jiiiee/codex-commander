"""Tests for the offline behavioral-case runner and its evaluator boundary."""

import contextlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
from urllib.parse import unquote, urlsplit


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT / "scripts"))
import run_behavioral_cases as runner


MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\((?P<target><[^>]+>|[^\s)]+)")


def local_markdown_targets(source):
    content = source.read_text(encoding="utf-8")
    for match in MARKDOWN_LINK.finditer(content):
        parsed = urlsplit(match.group("target").strip("<>"))
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        yield source.parent / unquote(parsed.path)


def expected_skill_snapshot():
    package_root = PACKAGE_ROOT.resolve()
    pending = [package_root / "SKILL.md"]
    expected = {}
    while pending:
        source = pending.pop(0).resolve(strict=True)
        relative = source.relative_to(package_root)
        if str(relative) in expected:
            continue
        if not source.is_file():
            raise AssertionError(f"test package link is not a file: {relative}")
        expected[str(relative)] = source.read_bytes().hex()
        if source.suffix.lower() == ".md":
            pending.extend(local_markdown_targets(source))
    return expected


class BehavioralRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="behavioral-runner-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.output = self.root / "results.json"
        self.cases = self.root / "cases.json"

    def write_cases(self, *case_ids):
        self.cases.write_text(
            json.dumps(
                [
                    {"id": case_id, "user": f"用户-{case_id}", "context": {"index": index}}
                    for index, case_id in enumerate(case_ids)
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def run_main(self, *arguments):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = runner.main(list(arguments))
        return status, stdout.getvalue(), stderr.getvalue()

    def run_custom(self, command, *, timeout="3"):
        return self.run_main(
            "--cases", str(self.cases),
            "--run",
            "--output", str(self.output),
            "--timeout", timeout,
            "--command", *command,
        )

    def test_lists_all_thirteen_packaged_cases_in_source_order(self):
        status, stdout, stderr = self.run_main("--list")
        self.assertEqual(status, runner.EXIT_SUCCESS)
        self.assertEqual(stderr, "")
        listed = json.loads(stdout)
        source = json.loads(
            (PACKAGE_ROOT / "tests/behavioral-cases.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(listed["cases"]), 13)
        self.assertEqual(listed["cases"], [case["id"] for case in source])

    @mock.patch.object(runner.subprocess, "Popen")
    def test_dry_run_records_requests_without_launching_evaluator(self, popen):
        status, stdout, stderr = self.run_main("--dry-run", "--output", str(self.output))
        self.assertEqual((status, stderr), (runner.EXIT_SUCCESS, ""))
        popen.assert_not_called()
        record = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(record["schemaVersion"], 1)
        self.assertEqual(record["mode"], "dry-run")
        self.assertEqual(
            record["summary"],
            {"total": 13, "planned": 13, "completed": 0, "failed": 0},
        )
        self.assertEqual(json.loads(stdout), record["summary"])
        self.assertTrue(all(item["status"] == "planned" for item in record["results"]))

    def test_real_evaluator_receives_utf8_stdin_and_uses_disposable_cwd(self):
        self.write_cases("stdin-check")
        evaluator = """
import json
import os
import sys

request = json.load(sys.stdin)
print(json.dumps({"request": request, "cwd": os.getcwd()}, ensure_ascii=False))
"""
        status, _, stderr = self.run_custom([sys.executable, "-c", evaluator])

        self.assertEqual((status, stderr), (runner.EXIT_SUCCESS, ""))
        result = json.loads(self.output.read_text(encoding="utf-8"))["results"][0]
        response = json.loads(result["response"])
        self.assertEqual(response["request"]["case"]["user"], "用户-stdin-check")
        evaluator_cwd = Path(response["cwd"])
        self.assertNotEqual(evaluator_cwd, PACKAGE_ROOT)
        self.assertFalse(evaluator_cwd.exists())

    def test_real_evaluator_reads_complete_isolated_skill_snapshot(self):
        self.write_cases("skill-source")
        required_paths = {
            "SKILL.md",
            "NOTICE.md",
            "references/engineering-depth.md",
            "references/project-records.md",
            "references/sidebar-coordination.md",
            "licenses/mattpocock-skills-MIT.txt",
        }
        expected_content = expected_skill_snapshot()
        self.assertTrue(required_paths <= expected_content.keys())
        forbidden_root = str(PACKAGE_ROOT.resolve())
        evaluator = rf"""
import json
import os
from pathlib import Path
import re
import stat
import sys
from urllib.parse import unquote, urlsplit

request = json.load(sys.stdin)
skill_path = Path(request["skill"])
expected = {expected_content!r}
forbidden_root = {forbidden_root!r}
actual = {{
    str(path.relative_to(Path.cwd())): path.read_bytes().hex()
    for path in Path.cwd().rglob("*")
    if path.is_file()
}}
markdown_link = re.compile(r"!?\[[^\]]*\]\((?P<target><[^>]+>|[^\s)]+)")
checked_links = []
for markdown_path in sorted(Path.cwd().rglob("*.md")):
    content = markdown_path.read_text(encoding="utf-8")
    for match in markdown_link.finditer(content):
        parsed = urlsplit(match.group("target").strip("<>"))
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        target = markdown_path.parent / unquote(parsed.path)
        relative = str(target.resolve(strict=True).relative_to(Path.cwd()))
        assert target.is_file()
        assert target.read_bytes().hex() == expected[relative]
        checked_links.append((str(markdown_path.relative_to(Path.cwd())), relative))
modes = {{
    relative: stat.S_IMODE(Path(relative).stat().st_mode) for relative in actual
}}
request_text = json.dumps(request, ensure_ascii=False)
environment_leaks = [
    name for name, value in os.environ.items() if forbidden_root in value
]
assert skill_path.read_bytes().hex() == expected["SKILL.md"]
assert actual == expected
assert all(mode == 0o444 for mode in modes.values())
assert forbidden_root not in request_text
assert not environment_leaks
assert "OLDPWD" not in os.environ
assert os.environ["PWD"] == os.getcwd()
assert os.environ["BEHAVIORAL_KEEP"] == "preserved"
print(json.dumps({{
    "path": str(skill_path),
    "cwd": os.getcwd(),
    "files": sorted(actual),
    "modes": modes,
    "checkedLinks": checked_links,
    "environmentLeaks": environment_leaks,
}}))
"""
        inherited = {
            "PWD": forbidden_root,
            "OLDPWD": str(PACKAGE_ROOT.parent),
            "BEHAVIORAL_PACKAGE_LEAK": f"prefix:{forbidden_root}:suffix",
            "BEHAVIORAL_KEEP": "preserved",
        }
        with mock.patch.dict(os.environ, inherited, clear=False):
            status, _, stderr = self.run_custom([sys.executable, "-c", evaluator])

        self.assertEqual((status, stderr), (runner.EXIT_SUCCESS, ""))
        result = json.loads(self.output.read_text(encoding="utf-8"))["results"][0]
        response = json.loads(result["response"])
        self.assertEqual(response["path"], "SKILL.md")
        self.assertEqual(set(response["files"]), set(expected_content))
        self.assertTrue(response["checkedLinks"])
        self.assertTrue(all(mode == 0o444 for mode in response["modes"].values()))
        self.assertEqual(response["environmentLeaks"], [])
        evaluator_cwd = Path(response["cwd"])
        self.assertNotEqual(evaluator_cwd, PACKAGE_ROOT)
        self.assertFalse(evaluator_cwd.exists())

    def test_skill_snapshot_follows_local_files_regardless_of_extension(self):
        package = self.root / "package"
        (package / "references").mkdir(parents=True)
        (package / "licenses").mkdir()
        skill = package / "SKILL.md"
        notice = package / "NOTICE.md"
        skill.write_text(
            "[notice](NOTICE.md)\n[reference](references/guide.md)\n",
            encoding="utf-8",
        )
        notice.write_text("[license](licenses/terms.txt)\n", encoding="utf-8")
        (package / "references" / "guide.md").write_text(
            "guide", encoding="utf-8"
        )
        (package / "licenses" / "terms.txt").write_bytes(b"license bytes\x00\xff")

        with mock.patch.object(runner, "SKILL_SOURCE", skill):
            sources = runner.skill_snapshot_sources()

        self.assertEqual(
            {str(relative) for _, relative in sources},
            {
                "SKILL.md",
                "NOTICE.md",
                "references/guide.md",
                "licenses/terms.txt",
            },
        )

    def test_skill_snapshot_rejects_unsafe_local_file_targets(self):
        package = self.root / "package"
        package.mkdir()
        skill = package / "SKILL.md"
        (self.root / "outside.txt").write_text("outside", encoding="utf-8")
        (package / "directory").mkdir()
        cases = {
            "directory": "[bad](directory)",
            "escape": "[bad](../outside.txt)",
            "missing": "[bad](missing.txt)",
            "invalid-percent": "[bad](bad%ZZ.txt)",
            "invalid-utf8": "[bad](bad%FF.txt)",
            "nul-byte": "[bad](bad%00.txt)",
        }

        with mock.patch.object(runner, "SKILL_SOURCE", skill):
            for label, content in cases.items():
                with self.subTest(label=label):
                    skill.write_text(content, encoding="utf-8")
                    with self.assertRaises(runner.RunnerError):
                        runner.skill_snapshot_sources()

    def test_skill_snapshot_ignores_remote_anchor_and_non_file_links(self):
        package = self.root / "package"
        package.mkdir()
        skill = package / "SKILL.md"
        skill.write_text(
            "\n".join(
                [
                    "[remote](https://example.com/file.txt)",
                    "[anchor](#section)",
                    "[mail](mailto:test@example.com)",
                    "[data](data:text/plain,hello)",
                ]
            ),
            encoding="utf-8",
        )

        with mock.patch.object(runner, "SKILL_SOURCE", skill):
            sources = runner.skill_snapshot_sources()

        self.assertEqual(
            [(source.name, str(relative)) for source, relative in sources],
            [("SKILL.md", "SKILL.md")],
        )

    def test_real_nonzero_exit_is_a_case_failure_and_later_case_runs(self):
        self.write_cases("bad", "good")
        evaluator = """
import json
import sys

case_id = json.load(sys.stdin)["case"]["id"]
if case_id == "bad":
    print("partial")
    print("bad input", file=sys.stderr)
    raise SystemExit(7)
print("ok")
"""
        status, _, stderr = self.run_custom([sys.executable, "-c", evaluator])

        self.assertEqual((status, stderr), (runner.EXIT_CASE_FAILURE, ""))
        record = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(
            record["summary"],
            {"total": 2, "planned": 0, "completed": 1, "failed": 1},
        )
        failure, success = record["results"]
        self.assertEqual(failure["error"]["kind"], "exit")
        self.assertEqual(failure["error"]["exitCode"], 7)
        self.assertEqual(failure["response"], "partial")
        self.assertEqual(failure["stderr"], "bad input")
        self.assertEqual(success["response"], "ok")

    def test_invalid_utf8_output_is_safely_replaced_for_one_case(self):
        self.write_cases("invalid-output", "later-case")
        evaluator = """
import json
import os
import sys

case_id = json.load(sys.stdin)["case"]["id"]
if case_id == "invalid-output":
    os.write(1, b"valid\\xfftail\\n")
    os.write(2, b"detail\\xfetail\\n")
else:
    print("later completed")
"""
        status, _, stderr = self.run_custom([sys.executable, "-c", evaluator])

        self.assertEqual((status, stderr), (runner.EXIT_SUCCESS, ""))
        results = json.loads(self.output.read_text(encoding="utf-8"))["results"]
        result = results[0]
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["response"], "valid\ufffdtail")
        self.assertEqual(result["stderr"], "detail\ufffdtail")
        self.assertEqual(results[1]["response"], "later completed")

    def test_real_timeout_is_a_case_failure_with_explicit_scope(self):
        self.write_cases("timeout")
        evaluator = "import sys, time; sys.stdin.buffer.read(); time.sleep(30)"
        started = time.monotonic()

        status, _, stderr = self.run_custom(
            [sys.executable, "-c", evaluator], timeout="0.1"
        )

        self.assertEqual((status, stderr), (runner.EXIT_CASE_FAILURE, ""))
        self.assertLess(time.monotonic() - started, 5)
        result = json.loads(self.output.read_text(encoding="utf-8"))["results"][0]
        self.assertEqual(result["error"]["kind"], "timeout")
        self.assertEqual(
            result["error"]["terminationScope"], runner.TIMEOUT_TERMINATION_SCOPE
        )

    @unittest.skipUnless(os.name == "posix", "POSIX process groups are not available")
    def test_posix_timeout_kills_evaluator_descendants(self):
        self.write_cases("process-group-timeout")
        marker = self.root / "descendant-survived"
        descendant = (
            "import time; from pathlib import Path; "
            f"time.sleep(0.8); Path({str(marker)!r}).write_text('leaked')"
        )
        evaluator = f"""
import subprocess
import sys
import time

sys.stdin.buffer.read()
subprocess.Popen([{sys.executable!r}, "-c", {descendant!r}])
print("spawned", flush=True)
time.sleep(30)
"""

        status, _, _ = self.run_custom(
            [sys.executable, "-c", evaluator], timeout="0.15"
        )
        time.sleep(1)

        self.assertEqual(status, runner.EXIT_CASE_FAILURE)
        self.assertFalse(marker.exists())
        result = json.loads(self.output.read_text(encoding="utf-8"))["results"][0]
        self.assertEqual(result["error"]["terminationScope"], "process-group")

    def test_completed_result_is_saved_before_a_later_runner_failure(self):
        self.write_cases("first", "second")

        def fail_after_first(case, _command, _timeout):
            if case["id"] == "first":
                return {
                    "id": "first",
                    "status": "completed",
                    "request": runner.request_for(case),
                    "response": "kept",
                }
            saved = json.loads(self.output.read_text(encoding="utf-8"))
            self.assertEqual([item["id"] for item in saved["results"]], ["first"])
            raise RuntimeError("runner broke")

        with mock.patch.object(runner, "run_case", side_effect=fail_after_first):
            status, _, stderr = self.run_custom(["evaluator"])

        self.assertEqual(status, runner.EXIT_RUNNER_FAILURE)
        self.assertIn("runner failure", json.loads(stderr)["error"])
        record = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(record["summary"]["completed"], 1)
        self.assertEqual(record["results"][0]["response"], "kept")

    def test_user_interrupt_preserves_completed_results_and_has_distinct_exit(self):
        self.write_cases("first", "second")

        def interrupt_after_first(case, _command, _timeout):
            if case["id"] == "first":
                return {
                    "id": "first",
                    "status": "completed",
                    "request": runner.request_for(case),
                    "response": "kept",
                }
            raise KeyboardInterrupt

        with mock.patch.object(runner, "run_case", side_effect=interrupt_after_first):
            status, _, stderr = self.run_custom(["evaluator"])

        self.assertEqual(status, runner.EXIT_INTERRUPTED)
        self.assertIn("preserved", json.loads(stderr)["error"])
        record = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual([item["id"] for item in record["results"]], ["first"])

    def test_launch_error_is_a_case_failure_not_a_runner_failure(self):
        self.write_cases("missing")
        missing = str(self.root / "missing-evaluator")

        status, _, stderr = self.run_custom([missing])

        self.assertEqual((status, stderr), (runner.EXIT_CASE_FAILURE, ""))
        result = json.loads(self.output.read_text(encoding="utf-8"))["results"][0]
        self.assertEqual(result["error"]["kind"], "launch")

    def test_invalid_runner_input_has_a_distinct_failure_exit(self):
        missing_cases = self.root / "missing-cases.json"

        status, _, stderr = self.run_main(
            "--cases", str(missing_cases), "--dry-run", "--output", str(self.output)
        )

        self.assertEqual(status, runner.EXIT_RUNNER_FAILURE)
        self.assertIn("cannot read cases", json.loads(stderr)["error"])
        self.assertFalse(self.output.exists())

    def test_real_cli_distinguishes_case_and_runner_failure_exit_codes(self):
        self.write_cases("failure")
        script = str(PACKAGE_ROOT / "scripts/run_behavioral_cases.py")
        case_failure = subprocess.run(
            [
                sys.executable,
                script,
                "--cases", str(self.cases),
                "--run",
                "--output", str(self.output),
                "--command", sys.executable, "-c",
                "import sys; sys.stdin.read(); raise SystemExit(9)",
            ],
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        runner_failure = subprocess.run(
            [
                sys.executable,
                script,
                "--cases", str(self.root / "missing.json"),
                "--dry-run",
                "--output", str(self.output),
            ],
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )

        self.assertEqual(case_failure.returncode, runner.EXIT_CASE_FAILURE)
        self.assertEqual(runner_failure.returncode, runner.EXIT_RUNNER_FAILURE)
        self.assertNotEqual(case_failure.returncode, runner_failure.returncode)

    def test_result_path_rejects_symlinks_without_overwriting_target(self):
        target = self.root / "unrelated.txt"
        target.write_text("preserve me", encoding="utf-8")
        linked_output = self.root / "results-link.json"
        linked_output.symlink_to(target)

        status, _, stderr = self.run_main(
            "--dry-run", "--output", str(linked_output)
        )

        self.assertEqual(status, runner.EXIT_RUNNER_FAILURE)
        self.assertIn("refusing symlinked result path", json.loads(stderr)["error"])
        self.assertEqual(target.read_text(encoding="utf-8"), "preserve me")
        self.assertTrue(linked_output.is_symlink())


if __name__ == "__main__":
    unittest.main()
