"""Negative tests for the package's read-only structural checker."""

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT / "scripts"))
import check_package as checker


class CheckPackageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="package-check-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "codex-commander"
        shutil.copytree(
            PACKAGE_ROOT,
            self.root,
            ignore=shutil.ignore_patterns(".git", "__pycache__", ".local-evaluation", "dist"),
        )

    def errors(self):
        return checker.check(self.root)

    def write_cases(self, cases):
        (self.root / "tests/behavioral-cases.json").write_text(
            json.dumps(cases, ensure_ascii=False), encoding="utf-8"
        )

    def valid_case(self, **changes):
        case = {"id": "valid-case", "user": "Do the bounded task.", "context": "No external access."}
        case.update(changes)
        return case

    def test_current_package_has_no_non_manifest_errors(self):
        errors = checker.check(PACKAGE_ROOT)
        self.assertTrue(all(error.startswith("Release checksum mismatch:") for error in errors), errors)

    def test_malformed_openai_yaml_is_rejected(self):
        (self.root / "agents/openai.yaml").write_text(
            'interface:\n  display_name: "unterminated\n  short_description: "Valid description"\n',
            encoding="utf-8",
        )
        self.assertIn("Invalid quoted string in agents/openai.yaml: display_name", self.errors())

    def test_non_utf8_skill_is_reported_without_crashing(self):
        (self.root / "SKILL.md").write_bytes(b"\xff\xfe")
        self.assertIn("SKILL.md must be UTF-8", self.errors())

    def test_wrong_openai_yaml_shapes_are_rejected(self):
        invalid = (
            'interface: []\n',
            'interface:\n  display_name: "Codex Commander"\n',
            'interface:\n  display_name: ["Codex Commander"]\n  short_description: "Description"\n',
            'name: "Codex Commander"\n',
        )
        for text in invalid:
            with self.subTest(text=text):
                (self.root / "agents/openai.yaml").write_text(text, encoding="utf-8")
                self.assertTrue(any("agents/openai.yaml" in error for error in self.errors()))

    def test_noncanonical_versions_are_rejected(self):
        for version in ("v0.1.3\n", "01.1.3\n", "0.1\n", "0.1.3-beta\n", "0.1.3\nextra\n"):
            with self.subTest(version=version):
                (self.root / "VERSION").write_text(version, encoding="utf-8")
                self.assertIn("VERSION must be a canonical three-part numeric version", self.errors())

    def test_validation_version_must_match(self):
        (self.root / "VERSION").write_text("0.2.1\n", encoding="utf-8")
        self.assertIn("Version mismatch: VERSION is 0.2.1, VALIDATION.md is 0.2.0", self.errors())

    def test_validation_version_declaration_is_required(self):
        validation = self.root / "VALIDATION.md"
        validation.write_text(validation.read_text(encoding="utf-8").replace("Version: 0.2.0.", "Release 0.2.0."), encoding="utf-8")
        self.assertIn("VALIDATION.md must declare its package version", self.errors())

    def test_release_notes_version_and_tag_must_match(self):
        notes = self.root / "RELEASE_NOTES.md"
        notes.write_text(
            notes.read_text(encoding="utf-8")
            .replace("Version: 0.2.0", "Version: 0.2.1")
            .replace("Intended tag: v0.2.0", "Intended tag: v0.2.1"),
            encoding="utf-8",
        )
        errors = self.errors()
        self.assertIn("Release-notes mismatch: VERSION is 0.2.0, RELEASE_NOTES.md is 0.2.1", errors)
        self.assertIn("Tag mismatch: expected v0.2.0, RELEASE_NOTES.md is v0.2.1", errors)

    def test_release_checksum_tampering_is_rejected(self):
        readme = self.root / "README.md"
        readme.write_text(readme.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        self.assertIn("Release checksum mismatch: README.md", self.errors())

        manifest = self.root / "RELEASE_CHECKSUMS.txt"
        original = manifest.read_text(encoding="utf-8")
        lines = original.splitlines()
        entry = next(line for line in lines if line.endswith("  README.md"))

        with self.subTest(case="missing"):
            manifest.write_text(original.replace(entry + "\n", ""), encoding="utf-8")
            self.assertTrue(
                any(error.startswith("Missing release checksum entries:") for error in self.errors())
            )
        with self.subTest(case="extra"):
            manifest.write_text(original + "0" * 64 + "  not-packaged.txt\n", encoding="utf-8")
            self.assertIn(
                "Unexpected release checksum entries: not-packaged.txt", self.errors()
            )
        with self.subTest(case="duplicate"):
            manifest.write_text(original + entry + "\n", encoding="utf-8")
            self.assertIn("Duplicate release checksum entry: README.md", self.errors())
        with self.subTest(case="invalid"):
            manifest.write_text(original + "not-a-checksum-line\n", encoding="utf-8")
            self.assertTrue(
                any(error.startswith("Invalid RELEASE_CHECKSUMS.txt line:") for error in self.errors())
            )

    def test_common_machine_specific_paths_are_rejected(self):
        examples = (
            "/opt" + "/homebrew/bin/python3",
            "/Users" + "/example/project",
            "C:" + r"\Users\example\project",
            "\\" * 2 + "host" + "\\" + "Users" + "\\example\\project",
        )
        readme = self.root / "README.md"
        original = readme.read_text(encoding="utf-8")
        for example in examples:
            with self.subTest(example=example):
                readme.write_text(original + "\n" + example + "\n", encoding="utf-8")
                self.assertIn("Machine-specific path: README.md", self.errors())

    def test_behavioral_cases_must_be_a_nonempty_array(self):
        for cases in ({"id": "not-an-array"}, []):
            with self.subTest(cases=cases):
                self.write_cases(cases)
                self.assertIn("tests/behavioral-cases.json must be a nonempty array", self.errors())

    def test_behavioral_case_must_be_an_object(self):
        self.write_cases(["not-an-object"])
        self.assertIn("Behavioral case 0 must be an object", self.errors())

    def test_behavioral_case_requires_all_fields(self):
        for field in ("id", "user", "context"):
            with self.subTest(field=field):
                case = self.valid_case()
                del case[field]
                self.write_cases([case])
                self.assertTrue(any("missing required fields" in error and field in error for error in self.errors()))

    def test_behavioral_case_field_types_are_checked(self):
        invalid = ({"id": 7}, {"user": []}, {"context": None})
        for change in invalid:
            with self.subTest(change=change):
                self.write_cases([self.valid_case(**change)])
                self.assertTrue(any(next(iter(change)) in error for error in self.errors()))

    def test_behavioral_case_ids_must_be_unique(self):
        self.write_cases([self.valid_case(), self.valid_case(user="A different prompt")])
        self.assertIn("Duplicate behavioral case id: valid-case", self.errors())


if __name__ == "__main__":
    unittest.main()
