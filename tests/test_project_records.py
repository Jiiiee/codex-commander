"""Filesystem behavior tests; no network, real tasks, or project mutations."""

import contextlib
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import project_records as records


class ProjectRecordsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="commander-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def plan(self, language="en", level="maintainable", goal="A local tool"):
        return records.plan_records(self.root, language, level, goal)

    def apply(self, **kwargs):
        return records.apply_plan(self.plan(**kwargs))

    def snapshot(self):
        return {str(path.relative_to(self.root)): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}

    def test_preview_has_no_filesystem_writes(self):
        plan = self.plan()
        self.assertEqual({change.action for change in plan.changes}, {"create"})
        self.assertEqual(list(self.root.iterdir()), [])

    def test_apply_creates_only_the_two_records(self):
        self.apply()
        self.assertEqual(set(self.snapshot()), {"AGENTS.md", "docs/commander.md"})

    def test_simplified_chinese_goal_headings_and_rules(self):
        self.apply(language="zh-CN", goal="批量整理我的照片")
        document = (self.root / "docs/commander.md").read_text()
        agents = (self.root / "AGENTS.md").read_text()
        self.assertIn("# 总指挥项目记录", document)
        self.assertIn("批量整理我的照片", document)
        self.assertIn("工程化档位：实用维护", document)
        self.assertIn("## 验收条件", document)
        self.assertNotIn("## Acceptance", document)
        self.assertIn("回报完成情况或真实阻塞", agents)

    def test_traditional_chinese_is_preserved(self):
        self.apply(language="zh-TW", level="prototype", goal="整理我的相片")
        document = (self.root / "docs/commander.md").read_text()
        self.assertIn("# 總指揮專案記錄", document)
        self.assertIn("工程化層級：輕量驗證", document)
        self.assertIn("整理我的相片", document)

    def test_english_documents(self):
        self.apply(level="production")
        document = (self.root / "docs/commander.md").read_text()
        self.assertIn("# Commander project record", document)
        self.assertIn("Engineering depth: Production", document)
        self.assertIn("No team creation is recorded", document)

    def test_all_language_and_level_combinations(self):
        for language in records.TEXT:
            for level in records.LEVELS:
                with self.subTest(language=language, level=level):
                    result = records.new_record(language, level, "User goal").decode()
                    self.assertIn(records.TEXT[language]["levels"][level], result)

    def test_repeated_run_is_byte_identical(self):
        self.apply(language="zh-CN")
        before = self.snapshot()
        self.assertEqual(self.apply(language="zh-CN"), [])
        self.assertEqual(self.snapshot(), before)

    def test_existing_instructions_preserved_exactly(self):
        original = b"\xef\xbb\xbf# Existing rules\r\n\r\nKeep this exactly.\r\n"
        (self.root / "AGENTS.md").write_bytes(original)
        self.apply(language="zh-CN")
        result = (self.root / "AGENTS.md").read_bytes()
        self.assertTrue(result.startswith(original))
        self.assertEqual(result.count(records.BEGIN.encode()), 1)

    def test_existing_instructions_without_final_newline(self):
        original = b"Do not remove this"
        (self.root / "AGENTS.md").write_bytes(original)
        self.apply()
        self.assertTrue((self.root / "AGENTS.md").read_bytes().startswith(original + b"\n\n"))

    def test_only_managed_block_changes_on_language_switch(self):
        prefix = "# Existing English\r\nPreserve me\r\n".encode()
        suffix = "\r\n# 尾部规则\r\n不能删除\r\n".encode()
        original = prefix + records.managed_block("en").encode() + suffix
        (self.root / "AGENTS.md").write_bytes(original)
        self.apply(language="zh-CN")
        expected = prefix + records.managed_block("zh-CN").encode() + suffix
        self.assertEqual((self.root / "AGENTS.md").read_bytes(), expected)

    def test_existing_commander_record_not_overwritten(self):
        (self.root / "docs").mkdir()
        original = b"# Approved plan\nDo not translate or replace.\n"
        (self.root / "docs/commander.md").write_bytes(original)
        plan = self.plan(language="zh-CN", goal="A different goal")
        records.apply_plan(plan)
        self.assertEqual((self.root / "docs/commander.md").read_bytes(), original)
        self.assertEqual(len(plan.warnings), 1)
        self.assertIn("已保留", plan.warnings[0])

    def test_upgrade_managed_rules_preserves_existing_plan_and_outer_rules(self):
        prefix = b"# Existing project policy\r\nKeep this section unchanged.\r\n\r\n"
        suffix = "\r\n# 用户补充规则\r\n保留此处的已有组织约定。\r\n".encode()
        legacy = f"{records.BEGIN}\n## Legacy Commander rules\n\n- Old managed content.\n{records.END}".encode()
        (self.root / "AGENTS.md").write_bytes(prefix + legacy + suffix)
        (self.root / "docs").mkdir()
        approved = "# 已批准的项目计划\n现有决定不应被升级覆盖。\n".encode()
        (self.root / "docs/commander.md").write_bytes(approved)
        self.assertEqual(self.apply(language="zh-CN"), ["AGENTS.md"])
        self.assertEqual((self.root / "AGENTS.md").read_bytes(), prefix + records.managed_block("zh-CN").encode() + suffix)
        self.assertEqual((self.root / "docs/commander.md").read_bytes(), approved)
        self.assertEqual(self.apply(language="zh-CN"), [])

    def test_empty_existing_plan_is_still_preserved(self):
        (self.root / "docs").mkdir()
        (self.root / "docs/commander.md").write_bytes(b"")
        self.apply()
        self.assertEqual((self.root / "docs/commander.md").read_bytes(), b"")

    def test_malformed_markers_refuse_before_any_write(self):
        candidates = [records.BEGIN, records.END, records.END + "\n" + records.BEGIN,
                      records.BEGIN + "\n" + records.BEGIN + "\n" + records.END,
                      "prefix " + records.BEGIN + "\n" + records.END]
        for value in candidates:
            with self.subTest(value=value):
                (self.root / "AGENTS.md").write_text(value)
                before = self.snapshot()
                with self.assertRaises(records.RecordError):
                    self.apply()
                self.assertEqual(self.snapshot(), before)

    def test_invalid_encoding_refuses(self):
        (self.root / "AGENTS.md").write_bytes(b"\xff\xfe")
        with self.assertRaises(records.RecordError):
            self.apply()
        self.assertFalse((self.root / "docs").exists())

    def test_override_refuses(self):
        (self.root / "AGENTS.override.md").write_text("Existing effective rules")
        with self.assertRaises(records.RecordError):
            self.apply()
        self.assertFalse((self.root / "AGENTS.md").exists())

    def test_symlinked_agents_refuses(self):
        target = self.root / "original.md"
        target.write_text("Original rules")
        (self.root / "AGENTS.md").symlink_to(target)
        with self.assertRaises(records.RecordError):
            self.apply()
        self.assertEqual(target.read_text(), "Original rules")

    def test_symlinked_docs_refuses(self):
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        (self.root / "docs").symlink_to(elsewhere, target_is_directory=True)
        with self.assertRaises(records.RecordError):
            self.apply()
        self.assertEqual(list(elsewhere.iterdir()), [])

    def test_dangling_output_symlink_refuses(self):
        (self.root / "AGENTS.md").symlink_to(self.root / "missing.md")
        with self.assertRaises(records.RecordError):
            self.apply()

    def test_regular_file_as_docs_parent_refuses(self):
        (self.root / "docs").write_text("Not a directory")
        with self.assertRaises(records.RecordError):
            self.apply()
        self.assertFalse((self.root / "AGENTS.md").exists())

    def test_directory_as_agents_file_refuses(self):
        (self.root / "AGENTS.md").mkdir()
        with self.assertRaises(records.RecordError):
            self.apply()

    def test_unsafe_roots_refuse(self):
        values = [Path(self.root.anchor), Path.home(), Path(__file__).resolve().parents[1]]
        for value in values:
            with self.subTest(root=str(value)), self.assertRaises(records.RecordError):
                records.plan_records(value, "en", "prototype", "A goal")

    def test_configured_codex_home_refuses(self):
        with mock.patch.dict("os.environ", {"CODEX_HOME": str(self.root)}):
            with self.assertRaises(records.RecordError):
                self.plan()

    def test_relative_and_missing_roots_refuse(self):
        for value in (Path("relative-project"), self.root / "absent"):
            with self.subTest(root=str(value)), self.assertRaises(records.RecordError):
                records.plan_records(value, "en", "prototype", "A goal")

    def test_invalid_arguments_refuse(self):
        cases = (("unknown", "prototype", "Goal"), ("en", "unknown", "Goal"), ("en", "prototype", "  "), ("en", "prototype", "A\x00B"))
        for language, level, goal in cases:
            with self.subTest(language=language, level=level, goal=repr(goal)), self.assertRaises(records.RecordError):
                records.plan_records(self.root, language, level, goal)

    def test_file_change_after_plan_is_not_lost(self):
        plan = self.plan()
        (self.root / "AGENTS.md").write_text("Someone else wrote this")
        with self.assertRaises(records.RecordError):
            records.apply_plan(plan)
        self.assertEqual((self.root / "AGENTS.md").read_text(), "Someone else wrote this")
        self.assertFalse((self.root / "docs").exists())

    def test_symlink_introduced_after_plan_refuses(self):
        plan = self.plan()
        target = self.root / "elsewhere"
        target.mkdir()
        (self.root / "docs").symlink_to(target, target_is_directory=True)
        with self.assertRaises(records.RecordError):
            records.apply_plan(plan)
        self.assertFalse((self.root / "AGENTS.md").exists())

    def test_existing_permissions_preserved(self):
        agents = self.root / "AGENTS.md"
        agents.write_text("Existing rules\n")
        agents.chmod(0o640)
        self.apply()
        self.assertEqual(stat.S_IMODE(agents.stat().st_mode), 0o640)

    def test_partial_failure_is_reported_and_rerun_is_safe(self):
        original_write = records.write_change

        def fail_on_agents(root, change):
            if change.path.name == "AGENTS.md":
                raise OSError("Injected test failure")
            return original_write(root, change)

        with mock.patch.object(records, "write_change", side_effect=fail_on_agents):
            with self.assertRaisesRegex(records.RecordError, "docs/commander.md"):
                self.apply()
        original_record = (self.root / "docs/commander.md").read_bytes()
        self.apply()
        self.assertEqual((self.root / "docs/commander.md").read_bytes(), original_record)

    def test_cli_preview_and_apply(self):
        args = ["--root", str(self.root), "--language", "zh-CN", "--level", "prototype", "--goal", "本地任务"]
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(records.main(args), 0)
        self.assertEqual(json.loads(buffer.getvalue())["mode"], "preview")
        self.assertEqual(list(self.root.iterdir()), [])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(records.main(args + ["--apply"]), 0)
        self.assertIn("本地任务", (self.root / "docs/commander.md").read_text())

    def test_cli_failure_is_nonzero_and_no_success_claim(self):
        args = ["--root", str(self.root / "missing"), "--language", "en", "--level", "prototype", "--goal", "Goal", "--apply"]
        error, output = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(error), contextlib.redirect_stdout(output):
            self.assertEqual(records.main(args), 2)
        self.assertIn("error", json.loads(error.getvalue()))
        self.assertEqual(output.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
