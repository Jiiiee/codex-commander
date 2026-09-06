"""Filesystem behavior tests; no network, real tasks, or project mutations."""

import contextlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import threading
import time
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

    def test_real_crash_during_first_write_keeps_restricted_original_and_temporary(self):
        agents = self.root / "AGENTS.md"
        original = b"Existing restricted rules\n"
        agents.write_bytes(original)
        agents.chmod(0o600)
        (self.root / "docs").mkdir()
        (self.root / "docs/commander.md").write_bytes(b"# Existing plan\n")
        marker = self.root.parent / f"{self.root.name}-first-write"
        self.addCleanup(marker.unlink, missing_ok=True)
        child = r'''
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, sys.argv[1])
import project_records as records

root = Path(sys.argv[2])
marker = Path(sys.argv[3])
os.umask(0o022)
real_fdopen = os.fdopen

class PausingWriter:
    def __init__(self, *args, **kwargs):
        self.handle = real_fdopen(*args, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return self.handle.__exit__(*args)

    def __getattr__(self, name):
        return getattr(self.handle, name)

    def write(self, content):
        written = self.handle.write(content)
        self.handle.flush()
        marker.write_text("ready")
        while True:
            time.sleep(1)
        return written

records.os.fdopen = PausingWriter
plan = records.plan_records(root, "en", "maintainable", "A local tool")
records.apply_plan(plan)
'''
        process = subprocess.Popen(
            [sys.executable, "-c", child, str(Path(records.__file__).parent), str(self.root), str(marker)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        temporary_paths = []
        temporary_mode = None
        try:
            deadline = time.monotonic() + 5
            while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.01)
            if not marker.exists():
                stderr = process.communicate(timeout=1)[1] if process.poll() is not None else "child did not reach first write"
                self.fail(stderr)
            temporary_paths = list(self.root.glob(".commander-*"))
            self.assertEqual(len(temporary_paths), 1)
            temporary_mode = stat.S_IMODE(temporary_paths[0].stat().st_mode)
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            process.stderr.close()

        self.assertEqual(process.returncode, -9)
        self.assertEqual(agents.read_bytes(), original)
        self.assertEqual(stat.S_IMODE(agents.stat().st_mode), 0o600)
        self.assertTrue(temporary_paths[0].exists())
        self.assertNotEqual(temporary_paths[0].read_bytes(), b"")
        self.assertEqual(stat.S_IMODE(temporary_paths[0].stat().st_mode), temporary_mode)
        self.assertEqual(temporary_mode & ~0o600, 0)

    def test_new_temporary_files_are_private_before_first_write(self):
        observed_modes = []
        real_fdopen = os.fdopen

        class InspectingWriter:
            def __init__(self, *args, **kwargs):
                self.handle = real_fdopen(*args, **kwargs)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return self.handle.__exit__(*args)

            def __getattr__(self, name):
                return getattr(self.handle, name)

            def write(self, content):
                observed_modes.append(stat.S_IMODE(os.fstat(self.handle.fileno()).st_mode))
                return self.handle.write(content)

        previous_umask = os.umask(0o022)
        try:
            with mock.patch.object(records.os, "fdopen", InspectingWriter):
                self.apply()
        finally:
            os.umask(previous_umask)

        self.assertEqual(observed_modes, [0o600, 0o600])

    def test_new_files_use_normal_creation_permissions(self):
        reference = self.root / "reference"
        reference.write_bytes(b"")
        expected = stat.S_IMODE(reference.stat().st_mode)
        self.apply()
        self.assertEqual(stat.S_IMODE((self.root / "AGENTS.md").stat().st_mode), expected)
        self.assertEqual(stat.S_IMODE((self.root / "docs/commander.md").stat().st_mode), expected)

    def test_two_roots_restore_process_umask_and_create_with_the_original_mode(self):
        other_temporary = tempfile.TemporaryDirectory(prefix="commander-other-root-")
        self.addCleanup(other_temporary.cleanup)
        roots = (self.root, Path(other_temporary.name).resolve())
        plans = []
        for root in roots:
            (root / "docs").mkdir()
            (root / "docs/commander.md").write_bytes(b"# Existing plan\n")
            plans.append(records.plan_records(root, "en", "maintainable", "A local tool"))

        real_umask = os.umask
        first_set = threading.Event()
        second_set = threading.Event()
        first_restored = threading.Event()
        bookkeeping_lock = threading.Lock()
        roles = {}
        calls = {}
        next_role = 0

        def interleave_umask(value):
            nonlocal next_role
            identity = threading.get_ident()
            with bookkeeping_lock:
                calls[identity] = calls.get(identity, 0) + 1
                if calls[identity] == 1:
                    next_role += 1
                    roles[identity] = next_role
                role = roles[identity]
                call = calls[identity]
            previous = real_umask(value)
            if call == 1 and role == 1:
                first_set.set()
                second_set.wait(timeout=0.25)
            elif call == 1:
                second_set.set()
                first_restored.wait(timeout=0.25)
            elif role == 1:
                first_restored.set()
            return previous

        errors = []

        def apply(plan):
            try:
                records.apply_plan(plan)
            except Exception as exc:  # pragma: no cover - asserted below
                errors.append(exc)

        original_umask = real_umask(0o022)
        try:
            with mock.patch.object(records.os, "umask", side_effect=interleave_umask):
                first = threading.Thread(target=apply, args=(plans[0],))
                second = threading.Thread(target=apply, args=(plans[1],))
                first.start()
                self.assertTrue(first_set.wait(timeout=2))
                second.start()
                first.join(timeout=5)
                second.join(timeout=5)
            final_umask = real_umask(0o022)
        finally:
            real_umask(original_umask)

        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(final_umask, 0o022)
        self.assertEqual(
            [stat.S_IMODE((root / "AGENTS.md").stat().st_mode) for root in roots],
            [0o644, 0o644],
        )

    def test_partial_failure_is_reported_and_rerun_is_safe(self):
        original_write = records.write_change

        def fail_on_agents(root_fd, root, change):
            if change.path.name == "AGENTS.md":
                raise OSError("Injected test failure")
            return original_write(root_fd, root, change)

        with mock.patch.object(records, "write_change", side_effect=fail_on_agents):
            with self.assertRaisesRegex(records.RecordError, "docs/commander.md"):
                self.apply()
        original_record = (self.root / "docs/commander.md").read_bytes()
        self.apply()
        self.assertEqual((self.root / "docs/commander.md").read_bytes(), original_record)

    def test_two_writers_cannot_apply_different_plans_from_same_snapshot(self):
        english = self.plan(language="en")
        chinese = self.plan(language="zh-CN")
        entered = threading.Event()
        release = threading.Event()
        original_write = records.write_change

        def pause_first_writer(root_fd, root, change):
            if threading.current_thread().name == "english-writer" and not entered.is_set():
                entered.set()
                self.assertTrue(release.wait(timeout=5))
            return original_write(root_fd, root, change)

        outcome = []

        def apply_english():
            try:
                outcome.append(records.apply_plan(english))
            except Exception as exc:  # pragma: no cover - asserted below
                outcome.append(exc)

        with mock.patch.object(records, "write_change", side_effect=pause_first_writer):
            writer = threading.Thread(target=apply_english, name="english-writer")
            writer.start()
            self.assertTrue(entered.wait(timeout=5))
            with self.assertRaisesRegex(records.RecordError, "Another apply may be running"):
                records.apply_plan(chinese)
            release.set()
            writer.join(timeout=5)

        self.assertFalse(writer.is_alive())
        self.assertEqual(outcome, [["docs/commander.md", "AGENTS.md"]])
        self.assertIn("# Commander project record", (self.root / "docs/commander.md").read_text())
        self.assertIn("Codex Commander working agreement", (self.root / "AGENTS.md").read_text())

    def test_interrupted_create_never_publishes_a_partial_target(self):
        plan = self.plan()
        real_link = os.link

        def interrupt_publish(source, target, **kwargs):
            if target == "commander.md":
                raise OSError("Injected interruption before publish")
            return real_link(source, target, **kwargs)

        with mock.patch.object(records.os, "link", side_effect=interrupt_publish):
            with self.assertRaisesRegex(records.RecordError, "Injected interruption"):
                records.apply_plan(plan)

        self.assertFalse((self.root / "docs/commander.md").exists())
        self.assertEqual(list(self.root.glob(".codex-commander*")), [])
        self.assertEqual(list((self.root / "docs").glob(".commander-*")), [])
        self.assertEqual(records.apply_plan(plan), ["docs/commander.md", "AGENTS.md"])

    def test_cooperating_writer_is_rejected_during_replace_window(self):
        agents = self.root / "AGENTS.md"
        agents.write_text("Existing rules\n")
        first = self.plan(language="en")
        second = self.plan(language="zh-CN")
        checked = threading.Event()
        release = threading.Event()
        real_rename = os.rename

        def pause_before_replace(source, target, **kwargs):
            if threading.current_thread().name == "first-writer" and target == agents.name:
                checked.set()
                self.assertTrue(release.wait(timeout=5))
            return real_rename(source, target, **kwargs)

        outcome = []

        def apply_first():
            try:
                outcome.append(records.apply_plan(first))
            except Exception as exc:  # pragma: no cover - asserted below
                outcome.append(exc)

        with mock.patch.object(records.os, "rename", side_effect=pause_before_replace):
            writer = threading.Thread(target=apply_first, name="first-writer")
            writer.start()
            self.assertTrue(checked.wait(timeout=5))
            with self.assertRaisesRegex(records.RecordError, "Another apply may be running"):
                records.apply_plan(second)
            release.set()
            writer.join(timeout=5)

        self.assertFalse(writer.is_alive())
        self.assertEqual(outcome, [["docs/commander.md", "AGENTS.md"]])
        self.assertIn("Codex Commander working agreement", agents.read_text())
        self.assertNotIn("Codex Commander 协作约定", agents.read_text())

    def test_create_and_cleanup_each_sync_the_parent_directory(self):
        change = self.plan().changes[0]
        events = []
        real_fsync, real_link, real_unlink = os.fsync, os.link, os.unlink

        def record_fsync(descriptor):
            if stat.S_ISDIR(os.fstat(descriptor).st_mode):
                events.append("fsync-directory")
            return real_fsync(descriptor)

        def record_link(source, target, **kwargs):
            events.append("link")
            return real_link(source, target, **kwargs)

        def record_unlink(path, **kwargs):
            events.append("unlink")
            return real_unlink(path, **kwargs)

        with records.open_root_directory(self.root) as root_fd:
            with mock.patch.object(records.os, "fsync", side_effect=record_fsync), \
                    mock.patch.object(records.os, "link", side_effect=record_link), \
                    mock.patch.object(records.os, "unlink", side_effect=record_unlink):
                records.write_change(root_fd, self.root, change)

        self.assertEqual(
            [event for event in events if event in {"link", "unlink", "fsync-directory"}],
            ["fsync-directory", "link", "fsync-directory", "unlink", "fsync-directory"],
        )

    def test_replace_syncs_the_parent_directory_after_publish(self):
        agents = self.root / "AGENTS.md"
        agents.write_text("Existing rules\n")
        change = self.plan().changes[1]
        events = []
        real_fsync, real_rename = os.fsync, os.rename

        def record_fsync(descriptor):
            if stat.S_ISDIR(os.fstat(descriptor).st_mode):
                events.append("fsync-directory")
            return real_fsync(descriptor)

        def record_rename(source, target, **kwargs):
            events.append("rename")
            return real_rename(source, target, **kwargs)

        with records.open_root_directory(self.root) as root_fd:
            with mock.patch.object(records.os, "fsync", side_effect=record_fsync), \
                    mock.patch.object(records.os, "rename", side_effect=record_rename):
                records.write_change(root_fd, self.root, change)

        self.assertEqual(events, ["rename", "fsync-directory"])

    def test_kernel_lock_has_no_release_path_and_blocks_two_followers(self):
        with records.open_root_directory(self.root) as first_fd:
            with records.exclusive_apply(first_fd, self.root):
                self.assertEqual(list(self.root.iterdir()), [])
                for follower in ("second", "third"):
                    with self.subTest(follower=follower):
                        with records.open_root_directory(self.root) as follower_fd:
                            with self.assertRaisesRegex(records.RecordError, "Another apply"):
                                with records.exclusive_apply(follower_fd, self.root):
                                    self.fail("follower entered while the first writer held the lock")
            with records.open_root_directory(self.root) as successor_fd:
                with records.exclusive_apply(successor_fd, self.root):
                    self.assertEqual(list(self.root.iterdir()), [])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_parent_replacement_cannot_redirect_temporary_write(self):
        change = self.plan().changes[0]
        outside = self.root / "outside"
        outside.mkdir()
        original_parent = self.root / "docs-original"
        original_write = records.write_temporary

        def replace_parent(parent_fd, path, content, mode):
            temporary = original_write(parent_fd, path, content, mode)
            path.parent.rename(original_parent)
            path.parent.symlink_to(outside, target_is_directory=True)
            return temporary

        with records.open_root_directory(self.root) as root_fd:
            with mock.patch.object(records, "write_temporary", side_effect=replace_parent):
                with self.assertRaisesRegex(records.RecordError, "Output parent changed"):
                    records.write_change(root_fd, self.root, change)

        self.assertEqual(list(outside.iterdir()), [])
        self.assertEqual(list(original_parent.iterdir()), [])

    def test_apply_refuses_when_directory_relative_writes_are_unavailable(self):
        plan = self.plan()
        with mock.patch.object(records, "ANCHORED_WRITES_SUPPORTED", False):
            with self.assertRaisesRegex(records.RecordError, "preview remains available"):
                records.apply_plan(plan)
        self.assertEqual(list(self.root.iterdir()), [])

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
