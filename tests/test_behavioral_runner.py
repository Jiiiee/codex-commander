"""Tests for the offline behavioral-case runner and its evaluator boundary."""

import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT / "scripts"))
import run_behavioral_cases as runner


class BehavioralRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="behavioral-runner-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.output = self.root / "results.json"

    def run_main(self, *arguments):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = runner.main(list(arguments))
        return status, stdout.getvalue(), stderr.getvalue()

    def test_lists_all_thirteen_packaged_cases_in_source_order(self):
        status, stdout, stderr = self.run_main("--list")
        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        listed = json.loads(stdout)
        source = json.loads((PACKAGE_ROOT / "tests/behavioral-cases.json").read_text())
        self.assertEqual(len(listed["cases"]), 13)
        self.assertEqual(listed["cases"], [case["id"] for case in source])

    @mock.patch.object(runner.subprocess, "run")
    def test_dry_run_records_all_requests_without_launching_command(self, run):
        status, stdout, stderr = self.run_main("--dry-run", "--output", str(self.output))
        self.assertEqual((status, stderr), (0, ""))
        run.assert_not_called()
        record = json.loads(self.output.read_text())
        self.assertEqual(record["schemaVersion"], 1)
        self.assertEqual(record["mode"], "dry-run")
        self.assertEqual(
            record["summary"], {"total": 13, "planned": 13, "completed": 0, "failed": 0}
        )
        self.assertEqual(json.loads(stdout), record["summary"])
        self.assertTrue(all(item["status"] == "planned" for item in record["results"]))
        self.assertTrue(all(item["request"]["freshContextRequired"] for item in record["results"]))
        first_bytes = self.output.read_bytes()
        status, _, _ = self.run_main("--dry-run", "--output", str(self.output))
        self.assertEqual(status, 0)
        self.assertEqual(self.output.read_bytes(), first_bytes)

    @mock.patch.object(runner.subprocess, "run")
    def test_run_launches_fresh_process_for_each_case_and_records_output(self, run):
        run.side_effect = [
            subprocess.CompletedProcess(["evaluator"], 0, f"response-{index}\n", "")
            for index in range(13)
        ]
        status, _, stderr = self.run_main(
            "--run", "--output", str(self.output), "--command", "evaluator", "--isolated"
        )
        self.assertEqual((status, stderr), (0, ""))
        self.assertEqual(run.call_count, 13)
        payloads = [json.loads(call.kwargs["input"]) for call in run.call_args_list]
        self.assertEqual([payload["case"]["id"] for payload in payloads], [
            item["id"] for item in json.loads((PACKAGE_ROOT / "tests/behavioral-cases.json").read_text())
        ])
        for call in run.call_args_list:
            self.assertEqual(call.args[0], ["evaluator", "--isolated"])
            self.assertIs(call.kwargs["check"], False)
            self.assertNotIn("shell", call.kwargs)
        record = json.loads(self.output.read_text())
        self.assertEqual(record["summary"]["completed"], 13)
        self.assertEqual(record["results"][0]["response"], "response-0")
        self.assertEqual(record["results"][0]["request"], payloads[0])

    @mock.patch.object(runner.subprocess, "run")
    def test_nonzero_case_is_recorded_and_later_cases_continue(self, run):
        run.side_effect = [
            subprocess.CompletedProcess(["evaluator"], 7, "partial\n", "bad input\n"),
            *[subprocess.CompletedProcess(["evaluator"], 0, "ok\n", "") for _ in range(12)],
        ]
        status, _, _ = self.run_main(
            "--run", "--output", str(self.output), "--command", "evaluator"
        )
        self.assertEqual(status, 1)
        self.assertEqual(run.call_count, 13)
        record = json.loads(self.output.read_text())
        self.assertEqual(record["summary"], {"total": 13, "planned": 0, "completed": 12, "failed": 1})
        failure = record["results"][0]
        self.assertEqual(failure["error"]["kind"], "exit")
        self.assertEqual(failure["error"]["exitCode"], 7)
        self.assertEqual(failure["response"], "partial")
        self.assertEqual(failure["stderr"], "bad input")
        self.assertEqual(record["results"][1]["status"], "completed")

    @mock.patch.object(runner.subprocess, "run")
    def test_timeout_and_launch_errors_have_stable_failure_kinds(self, run):
        run.side_effect = [
            subprocess.TimeoutExpired(
                ["evaluator"], 2, output=b"partial response\n", stderr=b"timeout detail\n"
            ),
            OSError("missing evaluator"),
        ]
        cases = runner.load_cases(runner.DEFAULT_CASES)[:2]
        results = runner.run_cases(cases, ["evaluator"], 2)
        self.assertEqual([result["error"]["kind"] for result in results], ["timeout", "launch"])
        self.assertEqual([result["status"] for result in results], ["failed", "failed"])
        self.assertEqual(results[0]["response"], "partial response")
        self.assertEqual(results[0]["stderr"], "timeout detail")

    def test_result_path_rejects_symlinks_without_overwriting_target(self):
        target = self.root / "unrelated.txt"
        target.write_text("preserve me")
        linked_output = self.root / "results-link.json"
        linked_output.symlink_to(target)

        status, _, stderr = self.run_main("--dry-run", "--output", str(linked_output))

        self.assertEqual(status, 2)
        self.assertIn("refusing symlinked result path", json.loads(stderr)["error"])
        self.assertEqual(target.read_text(), "preserve me")
        self.assertTrue(linked_output.is_symlink())

    def test_single_case_selection_preserves_source_order_and_record_shape(self):
        status, _, _ = self.run_main(
            "--dry-run",
            "--case", "worker-assignment",
            "--case", "discussion-zh",
            "--output", str(self.output),
        )
        self.assertEqual(status, 0)
        record = json.loads(self.output.read_text())
        self.assertEqual([item["id"] for item in record["results"]], ["discussion-zh", "worker-assignment"])
        self.assertEqual(record["summary"]["total"], 2)

    def test_invalid_mode_boundaries_fail_before_writing(self):
        cases = (
            ("--dry-run", "--command", "evaluator"),
            ("--run", "--output", str(self.output)),
            ("--dry-run", "--case", "not-a-case", "--output", str(self.output)),
            ("--dry-run",),
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                self.output.unlink(missing_ok=True)
                status, _, stderr = self.run_main(*arguments)
                self.assertEqual(status, 2)
                self.assertIn("error", json.loads(stderr))
                self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
