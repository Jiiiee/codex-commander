"""Negative tests for the package's read-only structural checker."""

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

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
            "/opt" + "/vendor/bin/tool",
            "/root" + "/private/project",
            "/Users" + "/example/project",
            "/home" + "/example/project",
            "C:" + r"\Users\example\project",
            "\\" * 2 + "host" + "\\" + "Users" + "\\example\\project",
        )
        readme = self.root / "README.md"
        original = readme.read_text(encoding="utf-8")
        for example in examples:
            with self.subTest(example=example):
                readme.write_text(original + "\n" + example + "\n", encoding="utf-8")
                self.assertIn("Machine-specific path: README.md", self.errors())

    def test_machine_path_components_in_http_urls_are_allowed(self):
        examples = (
            "https://example.com/opt/tool",
            "https://example.com/root/guide",
            "https://example.com/Users/example/project",
            "https://[2001:db8::1]/opt/tool",
            "https://[2001:db8::1]:8443/Users/example/project",
            "https://example.com/releases/(stable)/root/guide",
            "https://example.com/releases/(stable)/opt/tool",
            "https://example.com/releases/(stable)/Users/example/project",
            "https://example.com/releases/foo(/Users/example/project",
            "https://user:pass@example.com:443/Users/example/project",
            "https://user%2Dname@[2001:db8::1]:8443/root/guide",
            "[network path](https://example.com/releases/(stable)/Users/example/project)",
            "[network path](https://example.com/releases/foo(/Users/example/project)",
            "See (https://example.com/Users/example/project).",
        )
        readme = self.root / "README.md"
        original = readme.read_text(encoding="utf-8")
        for example in examples:
            with self.subTest(example=example):
                readme.write_text(original + "\n" + example + "\n", encoding="utf-8")
                self.assertNotIn("Machine-specific path: README.md", self.errors())

    def test_machine_paths_in_http_url_query_and_fragment_are_rejected(self):
        examples = (
            "https://example.test/upload?source=/" + "Users/alice/private.txt",
            "https://example.test/upload?source=%" + "2FUsers%2Falice%2Fprivate.txt",
            "https://example.test/docs#/" + "root/private/project",
            "https://example.test/docs#%" + "2Fopt%2Fvendor%2Fbin%2Ftool",
            "https://example.test/docs?source=/" + "home/alice/private.txt",
            r"https://example.test/upload?source=C%" + r"3A%5CUsers%5Calice%5Cprivate.txt",
            "https://[2001:db8::1]/(stable)/opt/tool?source=/" + "Users/alice/private.txt",
            "https://[2001:db8::1]/(stable)/" + "root/guide?source=%" + "2Fopt%2Fvendor%2Ftool",
            r"https://example.test/(stable)/Users/guide#source=C:" + r"\Users\alice\private.txt",
            r"https://example.test/(stable)/" + "root/guide#source=C%" + r"3A%5CUsers%5Calice%5Cprivate.txt",
        )
        readme = self.root / "README.md"
        original = readme.read_text(encoding="utf-8")
        for example in examples:
            with self.subTest(example=example):
                readme.write_text(original + "\n" + example + "\n", encoding="utf-8")
                self.assertIn("Machine-specific path: README.md", self.errors())

    def test_malformed_or_ambiguous_http_urls_fail_closed(self):
        examples = (
            "https://[2001:db8::1/" + "opt/tool",
            "https://[not-an-ipv6]/" + "root/private",
            "https://example.test:invalid/" + "Users/alice/private.txt",
            "https://[2001:db8::1]junk/" + "opt/tool",
            "https://foo[bar]/" + "root/private",
            "https://example.test)foo(/" + "Users/alice/private.txt",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertTrue(checker.contains_machine_specific_path(example))

    def test_ambiguous_http_userinfo_cannot_exempt_machine_paths(self):
        examples = (
            "https://u@x@evil.test/" + "Users/alice/private",
            "https://u@x@evil.test/%" + "2FUsers%2Falice%2Fprivate",
            "https://x\\@evil.test/" + "root/private",
            "https://x\\@evil.test/%" + "2Froot%2Fprivate",
            "https://%ZZ@example.test/" + "opt/vendor/tool",
            "https://%ZZ@example.test/%" + "2Fopt%2Fvendor%2Ftool",
            "https://@example.test/" + "Users/alice/private",
            "https://@example.test/%" + "2FUsers%2Falice%2Fprivate",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertTrue(checker.contains_machine_specific_path(example))

    def test_malformed_urls_with_encoded_machine_paths_fail_closed(self):
        examples = (
            "https://[not-an-ipv6]/%" + "2FUsers%2Falice%2Fprivate.txt",
            "https://example.test:invalid/%" + "2Froot%2Fprivate",
            r"https://foo[bar]/C%" + r"3A%5CUsers%5Calice%5Cprivate.txt",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertTrue(checker.contains_machine_specific_path(example))

    def test_valid_urls_keep_network_paths_exempt_from_machine_path_checks(self):
        examples = (
            "https://[2001:db8::1]/%2FUsers%2Falice%2Fguide",
            "https://[2001:db8::1]:8443/%2Froot%2Fguide",
            "https://example.test:443/releases/(stable)/%2Fopt%2Ftool",
            "https://o'reilly@example.test/Users/alice/guide",
            "https://example.test/release's/Users/alice/guide",
            "https://example.test/o'reilly/opt/tool",
            "https://example.test/releases/%5Bstable%5D/Users/alice/guide",
            "https://example.test/Users/alice,https://example.test/root/guide",
            "See   https://example.test/root/network-guide",
            "See ( https://example.test/releases/foo(/Users/alice/guide)",
            "See ( https://example.test/(stable)/root/network-guide)",
            "See [ https://[2001:db8::1]/Users/alice/guide]",
            "Nested ( [ https://[2001:db8::1]/(stable)/opt/tool])",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertFalse(checker.contains_machine_specific_path(example))

    def test_invalid_percent_escapes_anywhere_in_url_fail_closed(self):
        examples = (
            "https://example.test/%ZZ/%" + "2FUsers%2Falice%2Fprivate",
            "https://example.test/%2/%" + "2Froot%2Fprivate",
            "https://example.test/%GG/%" + "2Fopt%2Fvendor%2Ftool",
            r"https://example.test/%ZZ/C%" + r"3A%5CUsers%5Calice%5Cprivate",
            r"https://example.test/%2/C%" + r"3A%5CUsers%5Calice%5Cprivate",
            r"https://example.test/%GG/C%" + r"3A%5CUsers%5Calice%5Cprivate",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertTrue(checker.contains_machine_specific_path(example))

    def test_invalid_raw_uri_path_characters_fail_closed(self):
        examples = (
            "https://example.test/guide}/" + "Users/alice/private",
            "https://example.test/guide|/" + "root/private",
            "https://example.test/guide^/" + "opt/vendor/tool",
            r"https://example.test/guide\C:" + r"\Users\alice\private",
            r"https://example.test/guide\C%3A" + r"%5CUsers%5Calice%5Cprivate",
            "https://example.test/guide[/" + "Users/alice/private",
            "https://example.test/guide]/" + "root/private",
            "https://example.test/guide\x00/" + "opt/vendor/tool",
            "https://example.test/guide\x7f/" + "Users/alice/private",
            "https://example.test/guide\x85/" + "root/private",
            "https://example.test/releases/[stable]/" + "Users/alice/private",
        )
        for example in examples:
            with self.subTest(example=repr(example)):
                self.assertTrue(checker.contains_machine_specific_path(example))

    def test_c0_c1_and_del_in_uri_paths_fail_closed(self):
        controls = tuple(range(0x20)) + tuple(range(0x7F, 0xA0))
        for codepoint in controls:
            example = (
                "https://example.test/guide"
                + chr(codepoint)
                + "/"
                + "Users/alice/private"
            )
            with self.subTest(codepoint=hex(codepoint)):
                self.assertTrue(checker.contains_machine_specific_path(example))

    def test_percent_encoded_and_rfc_pchar_network_paths_remain_exempt(self):
        examples = (
            "https://example.test/-._~!$&'()*+,;=:@/Users/alice/guide",
            "https://example.test/%7D%7C%5E%5B%5D/" + "root/guide",
            "https://example.test/%00%7F/%2Fopt%2Fvendor%2Fguide",
            "https://example.test/a:b@c/Users/alice/guide?x=!$&'()*+,;=:@#part_*",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertFalse(checker.contains_machine_specific_path(example))

    def test_embedded_or_ambiguous_http_scheme_prefixes_fail_closed(self):
        examples = (
            "nothhttps://example.test/" + "Users/alice/private",
            "xhttps://example.test/" + "root/private",
            "abchttp://example.test/" + "opt/tool",
            "httpshttps://example.test/" + "Users/alice/private",
            "mailto:https://example.test/" + "root/private",
            "foo:/https://example.test/" + "opt/tool",
            "foo://https://example.test/" + "Users/alice/private",
            "token_https://example.test/" + "root/private",
            "token-https://example.test/" + "opt/tool",
            "1https://example.test/" + "Users/alice/private",
            "user@https://example.test/" + "root/private",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertTrue(checker.contains_machine_specific_path(example))

    def test_http_scheme_start_boundaries_keep_network_paths_exempt(self):
        examples = (
            "https://example.test/Users/alice/guide",
            "\nhttps://example.test/" + "root/guide",
            "See https://example.test/opt/tool",
            ",https://example.test/Users/alice/guide",
            ";https://example.test/root/guide",
            "url=https://example.test/opt/tool",
            "[docs](https://example.test/Users/alice/guide)",
            "( https://example.test/(stable)/root/guide)",
            '"https://example.test/opt/tool"',
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertFalse(checker.contains_machine_specific_path(example))

    def test_markdown_or_sentence_closers_cannot_absorb_machine_paths(self):
        examples = (
            "[docs](https://example.test/guide)/" + "Users/alice/private",
            "See (https://example.test/guide)/" + "root/private",
            "[docs](https://example.test/(stable))/" + "opt/vendor/tool",
            "[https://example.test/releases/[stable]]/" + "Users/alice/private",
            "[[docs]]((https://example.test/(stable)))/" + "root/private",
            "See (https://[2001:db8::1]/(stable))/" + "opt/vendor/tool",
            "[docs](https://example.test/guide?next=public#section)/" + "Users/alice/private",
            "[docs](https://example.test/guide),/" + "root/private",
            "See (https://example.test/guide)/" + "Users/alice/private "
            "https://example.test/root/network-guide",
            "See ( https://example.test/guide)/" + "root/private",
            "See [ https://example.test/guide]/" + "Users/alice/private",
            "[docs](  https://example.test/(stable))/" + "opt/vendor/tool",
            "Nested ( [ https://[2001:db8::1]/guide])/" + "root/private",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertTrue(checker.contains_machine_specific_path(example))

    def test_wrapped_url_suffixes_use_bounded_percent_decoding(self):
        examples = (
            "[docs](https://example.test/guide)/%" + "2FUsers%2Falice%2Fprivate",
            "See (https://example.test/guide)/%" + "252Froot%252Fprivate",
            r"[docs](https://example.test/guide)C%" + r"3A%5CUsers%5Calice%5Cprivate",
            r"See (https://example.test/guide)C%" + r"253A%255CUsers%255Calice%255Cprivate",
            "[docs](https://example.test/guide)/%" + "2525252Fopt%2525252Fvendor",
            "See (https://example.test/guide)/%ZZ/%" + "2Fhome%2Falice%2Fprivate",
            "[docs](https://example.test/Users/alice/network-guide)" + "%" + "ZZ",
            "* https://example.test/root/network-guide */" + "%" + "2",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertTrue(checker.contains_machine_specific_path(example))

    def test_common_document_wrappers_cannot_absorb_adjacent_machine_paths(self):
        examples = (
            "'https://example.test/guide'/" + "Users/alice/private",
            '"https://example.test/guide"/%' + "2Froot%2Fprivate",
            "‘https://example.test/guide’/%" + "252Fopt%252Fvendor",
            "“https://example.test/guide”/" + "home/alice/private",
            "*https://example.test/guide*/" + "Users/alice/private",
            "**https://example.test/guide**/%" + "2Froot%2Fprivate",
            "_https://example.test/guide_/" + "opt/vendor/tool",
            "__https://example.test/guide__/%" + "252Fhome%252Falice",
            "`https://example.test/guide`C%" + r"3A%5CUsers%5Calice%5Cprivate",
            "(https://example.test/guide)/%" + "2FUsers%2Falice%2Fprivate",
            "[https://example.test/guide]/" + "root/private",
            "**“'[https://example.test/(stable)]'”**/%" + "2Fopt%2Fvendor%2Ftool",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertTrue(checker.contains_machine_specific_path(example))

    def test_gfm_cjk_and_autolink_wrappers_cannot_absorb_machine_paths(self):
        examples = (
            "~~https://example.test/guide~~/" + "Users/alice/private",
            "（https://example.test/guide）/" + "root/private",
            "「https://example.test/guide」/%" + "2Fopt%2Fvendor%2Ftool",
            "『https://example.test/guide』C%" + r"253A%255CUsers%255Calice%255Cprivate",
            "【https://example.test/guide】/" + "Users/alice/private",
            "〈https://example.test/guide〉/%" + "2Froot%2Fprivate",
            "《https://example.test/guide》/%" + "252Fopt%252Fvendor",
            "<https://example.test/guide>/%" + "252Fhome%252Falice%252Fprivate",
            "~~https://example.test/guide~~=C%" + r"3A%5CUsers%5Calice%5Cprivate",
            "_https://example.test/guide_&amp;amp;path=/" + "root/private",
            "（ < ~~https://example.test/guide~~ > ）&amp;amp;path=%"
            + "2525252FUsers%2525252Falice%2525252Fprivate",
            "https://example.test/root/network-guide and "
            "「https://example.test/guide」&path=/" + "Users/alice/private",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertTrue(checker.contains_machine_specific_path(example))

    def test_wrapper_suffix_variants_all_fail_closed(self):
        examples = (
            "~~https://example.test/guide~~/" + "Users/alice/private",
            "（https://example.test/guide）/%" + "2Froot%2Fprivate",
            "「https://example.test/guide」/%" + "252Fopt%252Fvendor",
            "<https://example.test/guide>/%" + "2525252Fhome%2525252Falice",
            "『https://example.test/guide』/%ZZ/%" + "2FUsers%2Falice",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertTrue(checker.contains_machine_specific_path(example))

    def test_gfm_cjk_and_autolink_wrappers_preserve_valid_urls(self):
        examples = (
            "~~https://example.test/release~notes/Users/alice/guide~~",
            "（https://example.test/release's/root/guide）",
            "「https://[2001:db8::1]:8443/a:b@c/opt/tool」",
            "【https://example.test/release_notes/home/alice/guide】",
            "〈https://example.test/release*notes/opt/tool〉",
            "《https://example.test/release's/Users/alice/guide》",
            "<https://example.test/release*notes/Users/alice/guide?x=one#part_two>",
            "（ < ~~https://o'reilly@example.test/(stable)/root/guide~~ > ）",
            "~~https://example.test/Users/alice/guide~~ and "
            "「https://example.test/root/network-guide」",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertFalse(checker.contains_machine_specific_path(example))

    def test_uri_path_grammar_scan_has_linear_work(self):
        class CountedString(str):
            def __new__(cls, value, counts=None):
                instance = super().__new__(cls, value)
                instance.counts = counts if counts is not None else {"index": 0}
                return instance

            def __getitem__(self, key):
                self.counts["index"] += 1
                value = super().__getitem__(key)
                if isinstance(key, slice):
                    return type(self)(value, self.counts)
                return value

        def grammar_work(segments):
            path = CountedString("/-._~!$&'()*+,;=:@%2F" * segments)
            self.assertTrue(checker._has_valid_uri_path(path))
            return path.counts["index"]

        small_work = grammar_work(256)
        large_work = grammar_work(512)
        self.assertLessEqual(large_work, small_work * 2 + 8)

    def test_rfc_subdelimiters_and_document_wrappers_remain_valid_in_urls(self):
        examples = (
            "https://o'reilly@example.test/Users/alice/guide",
            "https://user!$&'()*+,;=:pass@example.test/root/guide",
            "https://example.test/release's/Users/alice/guide",
            "https://example.test/release*notes/opt/tool",
            "https://example.test/release_notes/home/alice/guide",
            "https://example.test/guide?edition=o'reilly&mark=*#part_*",
            "'https://example.test/release's/Users/alice/guide'",
            "*https://example.test/release*notes/opt/tool*",
            "__https://example.test/release_notes/home/alice/guide__",
            "“https://[2001:db8::1]:8443/(stable)/Users/alice/guide”",
            "**“'[https://example.test/(stable)/root/guide]'”**",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertFalse(checker.contains_machine_specific_path(example))

    def test_spaced_nested_wrappers_and_multiple_urls_keep_suffixes_visible(self):
        examples = (
            "See ** https://example.test/guide **/%" + "2FUsers%2Falice%2Fprivate",
            "‘ https://[2001:db8::1]:8443/guide ’/%" + "252Froot%252Fprivate",
            "( ' [ https://example.test/guide?next=public#part ] ' )C%"
            + r"3A%5CUsers%5Calice%5Cprivate",
            "https://example.test/root/network-guide and "
            "__ https://example.test/guide __/%" + "2Fopt%2Fvendor%2Ftool",
            "* https://[2001:db8::1]/guide?next=public#part */%ZZ/%"
            + "2Fhome%2Falice%2Fprivate",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertTrue(checker.contains_machine_specific_path(example))

    def test_spaced_document_wrappers_allow_network_paths_and_rfc_subdelimiters(self):
        examples = (
            "See ** https://example.test/release*notes/Users/alice/guide **.",
            "‘ https://[2001:db8::1]:8443/root/network-guide ’",
            "( ' [ https://o'reilly@example.test/(stable)/opt/tool ] ' )",
            "https://example.test/Users/alice/guide and "
            "__ https://example.test/release_notes/home/alice/guide __",
            "* https://example.test/release*notes/opt/tool * "
            "https://example.test/Users/alice/guide",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertFalse(checker.contains_machine_specific_path(example))

    def test_markdown_prefixes_do_not_weaken_scheme_start_boundaries(self):
        examples = (
            "token__https://example.test/" + "Users/alice/private__",
            "word*https://example.test/" + "root/private*",
            "name_https://example.test/%" + "2Fopt%2Fvendor",
            "token~https://example.test/" + "opt/vendor",
            "word~~https://example.test/" + "Users/alice/private~~",
            "token~~https://example.test/%" + "2Froot%2Fprivate~~",
            "word~~~https://example.test/" + "root/private~~~",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertTrue(checker.contains_machine_specific_path(example))

    def test_wrapper_closers_before_direct_keys_expose_machine_paths(self):
        examples = (
            "~~https://example.test/guide~~path=/" + "Users/alice/private",
            "'https://example.test/guide'file=%" + "2Froot%2Fprivate",
            "*https://example.test/guide*path=C:" + r"\Users\alice\private",
            "_https://example.test/guide_file=C%" + r"3A%5CUsers%5Calice%5Cprivate",
            "（https://example.test/guide）source=%" + "252Fopt%252Fvendor",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertTrue(checker.contains_machine_specific_path(example))

    def test_wrapper_closer_structural_separators_trigger_safe_scan(self):
        examples = (
            "~~https://example.test/guide~~(path=/" + "Users/alice/private)",
            "~~https://example.test/guide~~foo&amp;path=/" + "opt/vendor/tool",
            "~~https://example.test/guide~~foo'path=/" + "home/alice/private",
            "~~https://example.test/guide~~foo&path=/" + "Users/alice/private",
            "~~https://example.test/guide~~foo*path=/" + "Users/alice/private",
            "~~https://example.test/guide~~foo~path=/" + "root/private",
            "~~https://example.test/guide~~foo`path=/" + "opt/vendor/tool",
            "~~https://example.test/guide~~foo{path=/" + "home/alice/private}",
            "~~https://example.test/guide~~foo[path=/" + "root/private]",
            "~~https://example.test/guide~~foo【path=/" + "home/alice/private】",
            "~~https://example.test/guide~~foo%28path%3D%" + "2Froot%2Fprivate%29",
            "~~https://example.test/guide~~foo%27path%3D%" + "2FUsers%2Falice%2Fprivate",
            "~~https://example.test/guide~~foo%26amp%3Bpath%253D%" + "252Fopt%252Fvendor",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertTrue(checker.contains_machine_specific_path(example))

    def test_consecutive_wrapper_separators_trigger_safe_scan(self):
        examples = (
            "~~https://example.test/guide~~foo''path=/" + "home/alice/private",
            "~~https://example.test/guide~~foo)(path=/" + "Users/alice/private",
            "~~https://example.test/guide~~foo&amp;amp;'path=/" + "opt/vendor/tool",
            "~~https://example.test/guide~~foo%27%28path%3D%" + "2Froot%2Fprivate",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertTrue(checker.contains_machine_specific_path(example))

    def test_interleaved_wrapper_tokens_and_separators_trigger_safe_scan(self):
        examples = (
            "~~https://example.test/guide~~foo'bar'path=/"
            + "home/alice/private",
            "~~https://example.test/guide~~foo&amp;amp;bar'path=/"
            + "opt/vendor/tool",
            "~~https://example.test/guide~~foo&amp;bar'path=/"
            + "opt/vendor/tool",
            "~~https://example.test/guide~~foo%27bar%28path%3D%"
            + "2Froot%2Fprivate",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertTrue(checker.contains_machine_specific_path(example))

    def test_wrapper_closer_uri_component_stops_trigger_safe_scan(self):
        examples = (
            "~~https://example.test/guide~~foo/" + "Users/alice/private",
            "~~https://example.test/guide~~foo%2F" + "Users%2Falice%2Fprivate",
            "~~https://example.test/guide~~foo%23bar/" + "Users/alice/private",
            "~~https://example.test/guide~~foo%3Fbar/" + "opt/vendor/tool",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertTrue(checker.contains_machine_specific_path(example))

    def test_repeated_matching_wrapper_closers_cannot_reset_residual_budget(self):
        examples = (
            "~~https://example.test/guide~~foo~~bar%3Fbaz/"
            + "opt/vendor/tool~~",
            "*https://example.test/guide*foo*bar%3Fbaz/"
            + "opt/vendor/tool*",
            "**https://example.test/guide**foo**bar%3Fbaz/"
            + "opt/vendor/tool**",
            "_https://example.test/guide_foo_bar%3Fbaz/"
            + "opt/vendor/tool_",
            "__https://example.test/guide__foo__bar%3Fbaz/"
            + "opt/vendor/tool__",
            "（~~https://example.test/guide~~foo~~bar%3Fbaz/"
            + "opt/vendor/tool~~）",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertTrue(checker.contains_machine_specific_path(example))

    def test_repeated_closer_matrix_covers_raw_encoded_and_mixed_uri_stops(self):
        def encode_every_byte(value):
            return "".join(f"%{byte:02X}" for byte in value.encode("utf-8"))

        symmetric_wrappers = (
            ("'", "'"),
            ("*", "*"),
            ("**", "**"),
            ("_", "_"),
            ("__", "__"),
            ("~~", "~~"),
        )
        for opener, closer in symmetric_wrappers:
            raw = "foo" + closer + "bar?baz/" + "opt/vendor/tool" + closer
            encoded = (
                "foo"
                + encode_every_byte(closer)
                + "bar%3Fbaz%2F"
                + "opt%2Fvendor%2Ftool"
                + encode_every_byte(closer)
            )
            html_mixed = (
                "foo"
                + closer
                + "bar&amp;qux%3Fbaz/"
                + "opt/vendor/tool"
                + closer
            )
            for encoding, residual in (
                ("raw", raw),
                ("encoded", encoded),
                ("html-mixed", html_mixed),
            ):
                example = opener + "https://example.test/guide" + closer + residual
                with self.subTest(wrapper=opener, encoding=encoding):
                    self.assertTrue(checker.contains_machine_specific_path(example))

        outer_wrappers = (("(", ")"), ("（", "）"), ("「", "」"), ("【", "】"))
        for outer_opener, outer_closer in outer_wrappers:
            example = (
                outer_opener
                + "~~https://example.test/guide~~foo~~bar%3Fbaz/"
                + "opt/vendor/tool~~"
                + outer_closer
            )
            with self.subTest(outer=outer_opener):
                self.assertTrue(checker.contains_machine_specific_path(example))

    def test_single_internal_closer_and_explicit_url_controls_remain_valid(self):
        examples = (
            "'https://example.test/release'notes/" + "opt/tool'",
            "*https://example.test/release*notes/" + "opt/tool*",
            "**https://example.test/release**notes/" + "opt/tool**",
            "_https://example.test/release_notes/" + "opt/tool_",
            "__https://example.test/release__notes/" + "opt/tool__",
            "~~https://example.test/release~~notes/" + "Users/alice/guide~~",
            "[guide](https://example.test/release*notes/" + "opt/tool)",
            "<https://example.test/release*notes/" + "opt/tool>",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertFalse(checker.contains_machine_specific_path(example))

    def test_uri_component_stop_residuals_cross_raw_encoded_and_token_matrix(self):
        def encode_every_byte(value):
            return "".join(f"%{byte:02X}" for byte in value.encode("utf-8"))

        component_stops = ("/", "?", "#")
        short_tokens = ("a", "key", "路径")
        for stop in component_stops:
            for token in short_tokens:
                raw_residual = token + stop + "part/" + "Users/alice/private"
                encoded_residual = (
                    token
                    + encode_every_byte(stop)
                    + "part"
                    + encode_every_byte("/" + "Users/alice/private")
                )
                for encoding, residual in (
                    ("raw", raw_residual),
                    ("encoded", encoded_residual),
                ):
                    example = "~~https://example.test/guide~~" + residual
                    with self.subTest(stop=stop, token=token, encoding=encoding):
                        self.assertTrue(
                            checker.contains_machine_specific_path(example)
                        )

    def test_uri_component_stop_residual_bounds_and_decode_layers_fail_closed(self):
        def encode_every_byte(value):
            return "".join(f"%{byte:02X}" for byte in value.encode("utf-8"))

        maximum = (
            "x" * (checker.MAX_RESIDUAL_TOKEN_CHARACTERS - len("key"))
            + "?key=/"
            + "Users/alice/private"
        )
        overflow = "x" + maximum
        self.assertEqual(
            checker._raw_residual_boundary(maximum, 0),
            (True, False, False),
        )
        self.assertEqual(
            checker._raw_residual_boundary(overflow, 0),
            (False, False, True),
        )

        decoded = "key#part/" + "Users/alice/private"
        decoded_layers = []
        for _ in range(checker.MAX_PERCENT_DECODE_LAYERS):
            decoded = encode_every_byte(decoded)
            decoded_layers.append(decoded)
        rejected = (
            "~~https://example.test/guide~~" + maximum,
            "~~https://example.test/guide~~" + overflow,
            *("~~https://example.test/guide~~" + value for value in decoded_layers),
        )
        for example in rejected:
            with self.subTest(example=example[:120]):
                self.assertTrue(checker.contains_machine_specific_path(example))

    def test_repeated_closer_phase_preserves_raw_and_decoded_residual_limits(self):
        def encode_every_byte(value):
            return "".join(f"%{byte:02X}" for byte in value.encode("utf-8"))

        maximum = "x" * checker.MAX_RESIDUAL_TOKEN_CHARACTERS + "~~"
        overflow = "x" + maximum
        self.assertEqual(
            checker._raw_residual_boundary(maximum, 0, restart_closer="~~"),
            (False, False, False),
        )
        self.assertEqual(
            checker._raw_residual_boundary(overflow, 0, restart_closer="~~"),
            (False, False, True),
        )
        self.assertEqual(
            checker._bounded_boundary_probe(
                encode_every_byte(maximum),
                0,
                allow_token=True,
                restart_closer="~~",
            ),
            (False, False),
        )
        self.assertEqual(
            checker._bounded_boundary_probe(
                encode_every_byte(overflow),
                0,
                allow_token=True,
                restart_closer="~~",
            ),
            (False, True),
        )

        prefix = "~~https://example.test/guide~~"
        for residual in (maximum, overflow):
            repeated = residual + "bar%3Fbaz/" + "opt/vendor/tool~~"
            with self.subTest(length=len(residual)):
                self.assertTrue(
                    checker.contains_machine_specific_path(prefix + repeated)
                )

    def test_uri_component_stop_residual_rule_preserves_explicit_url_forms(self):
        examples = (
            "[guide](https://example.test/release/"
            + "Users/alice/guide?topic=private#section)",
            "<https://example.test/release/"
            + "opt/vendor/tool?topic=private#section>",
            "[guide](https://example.test/release%2F"
            + "Users%2Falice/guide?topic=private#section)",
            "<https://example.test/release%2F"
            + "opt%2Fvendor/tool?topic=private#section>",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertFalse(checker.contains_machine_specific_path(example))

    def test_wrapper_separator_sequences_are_bounded_and_encoding_complete(self):
        def encode_every_byte(value):
            return "".join(f"%{byte:02X}" for byte in value.encode("utf-8"))

        maximum_separators = "'(" * (
            checker.MAX_RESIDUAL_SEPARATOR_CHARACTERS // 2
        )
        maximum_alternating = "a'" * (
            checker.MAX_RESIDUAL_TOKEN_CHARACTERS - len("path")
        )
        maximum_alternating += "path=/" + "Users/alice/private"
        triple_encoded_boundary = "前'" * (
            checker.MAX_RESIDUAL_TOKEN_CHARACTERS - len("路径id")
        )
        triple_encoded_boundary += "路径id=/" + "Users/alice/private"
        for _ in range(checker.MAX_PERCENT_DECODE_LAYERS):
            triple_encoded_boundary = encode_every_byte(triple_encoded_boundary)

        rejected = (
            "~~https://example.test/guide~~foo" + maximum_separators
            + "path=/" + "Users/alice/private",
            "~~https://example.test/guide~~foo"
            + "'" * (checker.MAX_RESIDUAL_SEPARATOR_CHARACTERS + 1)
            + "path=/" + "root/private",
            "~~https://example.test/guide~~foo&amp;amp;amp;amp;path=/"
            + "opt/vendor/tool",
            "~~https://example.test/guide~~foo&amp;%27%28path%253D%"
            + "252Fhome%252Falice%252Fprivate",
            "~~https://example.test/guide~~" + maximum_alternating,
            "~~https://example.test/guide~~"
            + "a'" * (checker.MAX_RESIDUAL_TOKEN_CHARACTERS - len("path") + 1)
            + "path=/" + "root/private",
            "~~https://example.test/guide~~" + triple_encoded_boundary,
        )
        allowed = (
            "[network path](https://example.test/release%27%28path=/"
            + "Users/alice/guide)",
            "<https://example.test/release%26amp%3B%27path=/"
            + "root/network-guide>",
            "[network path](https://example.test/release%27bar%28path=/"
            + "Users/alice/guide)",
            "<https://example.test/release%26amp%3Bbar%27path=/"
            + "root/network-guide>",
        )
        for example in rejected:
            with self.subTest(kind="rejected", example=example[:120]):
                self.assertTrue(checker.contains_machine_specific_path(example))
        for example in allowed:
            with self.subTest(kind="allowed", example=example):
                self.assertFalse(checker.contains_machine_specific_path(example))

    def test_wrapper_residual_tokens_and_html_entities_are_generic_and_bounded(self):
        examples = (
            "~~https://example.test/guide~~" + "path%3D%2FUsers%2Falice%2Fprivate",
            "'https://example.test/guide'" + "file%253D%252Froot%252Fprivate",
            "*https://example.test/guide*" + "path%3DC%3A%5CUsers%5Calice%5Cprivate",
            "*https://example.test/guide*" + "1path=/" + "Users/alice/private",
            "~~https://example.test/guide~~" + "1=%2Froot%2Fprivate",
            "_https://example.test/guide_" + "$HOME=/" + "opt/vendor/tool",
            "~~https://example.test/guide~~" + "&AMP;path=/" + "Users/alice/private",
            "https://example.test/guide&LT;" + "/%2Froot%2Fprivate",
            "https://example.test/guide&GT;" + "/%252Fopt%252Fvendor",
            "（https://example.test/guide）" + "9$cache%253D%252Fhome%252Falice%252Fprivate",
            "~~https://example.test/guide~~" + "%26AmP%3B2%25253D%25252Froot%25252Fprivate",
            "<https://example.test/guide>" + "&AMP;7%3DC%253A%255CUsers%255Calice",
            "「https://example.test/guide」" + "路径%3D%2FUsers%2Falice%2Fprivate",
            "*https://example.test/guide*" + "9$key%25%33%44%252Froot%252Fprivate",
            "*https://example.test/guide*key+part=/" + "Users/alice/private",
            "*https://example.test/guide*key" + "%" + "2Bpart" + "%" + "3D"
            + "%" + "2Froot" + "%" + "2Fprivate",
            "_https://example.test/guide_scope:id=/" + "opt/vendor/tool",
            "~~https://example.test/guide~~path" + "%" + "5B0" + "%" + "5D"
            + "%" + "3D" + "%" + "2Fhome" + "%" + "2Falice"
            + "%" + "2Fprivate",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertTrue(checker.contains_machine_specific_path(example))

    def test_wrapper_residual_invalid_and_overlimit_encodings_fail_closed(self):
        long_token = "x" * (checker.MAX_RESIDUAL_TOKEN_CHARACTERS + 1)
        examples = (
            "~~https://example.test/guide~~" + "key%ZZ=%2FUsers%2Falice%2Fprivate",
            "*https://example.test/guide*" + "key%2525253D%2525252Froot%2525252Fprivate",
            "_https://example.test/guide_" + long_token + "%3D%2Fopt%2Fvendor",
            "~~https://example.test/guide~~" + "&AMP;AMP;AMP;AMP;key=/"
            + "Users/alice/private",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertTrue(checker.contains_machine_specific_path(example))

    def test_triple_encoded_maximum_token_uses_derived_source_window(self):
        def encode_every_byte(value):
            return "".join(f"%{byte:02X}" for byte in value.encode("utf-8"))

        residual = "ab" + encode_every_byte(
            encode_every_byte(
                encode_every_byte("k" * 62 + "=/" + "Users/alice/private")
            )
        )
        self.assertEqual(len(residual), 2243)
        self.assertEqual(
            checker.MAX_RESIDUAL_SOURCE_CHARACTERS,
            checker.MAX_RESIDUAL_DECODED_CHARACTERS
            * checker.MAX_UTF8_BYTES_PER_CHARACTER
            * checker.PERCENT_ESCAPE_EXPANSION
            ** checker.MAX_PERCENT_DECODE_LAYERS,
        )
        self.assertTrue(
            checker.contains_machine_specific_path(
                "~~https://example.test/guide~~" + residual
            )
        )

        truncated = residual + "x" * checker.MAX_RESIDUAL_SOURCE_CHARACTERS
        self.assertEqual(
            checker._bounded_boundary_probe(truncated, 0, allow_token=True),
            (False, True),
        )
        unfinished = encode_every_byte(
            encode_every_byte(
                encode_every_byte("k" * checker.MAX_RESIDUAL_TOKEN_CHARACTERS)
            )
        )
        self.assertEqual(
            checker._bounded_boundary_probe(unfinished, 0, allow_token=True),
            (False, True),
        )
        invalid_escape = "key" + "%" + "ZZ=/" + "Users/alice/private"
        self.assertEqual(
            checker._bounded_boundary_probe(invalid_escape, 0, allow_token=True),
            (False, True),
        )
        excess_layer = encode_every_byte(
            encode_every_byte(
                encode_every_byte(
                    encode_every_byte("key=/" + "Users/alice/private")
                )
            )
        )
        self.assertEqual(
            checker._bounded_boundary_probe(excess_layer, 0, allow_token=True),
            (False, True),
        )

    def test_ambiguous_wrapped_paths_fail_closed_but_explicit_links_are_valid(self):
        ambiguous = (
            "*https://example.test/release*1path=/" + "Users/alice/guide*",
            "_https://example.test/release_scope:id=/" + "opt/vendor/tool_",
        )
        explicit = (
            "[network path](https://example.test/release*1path=/"
            + "Users/alice/guide*)",
            "<https://example.test/release*1path=/" + "Users/alice/guide*>",
        )
        for example in ambiguous:
            with self.subTest(kind="ambiguous", example=example):
                self.assertTrue(checker.contains_machine_specific_path(example))
        for example in explicit:
            with self.subTest(kind="explicit", example=example):
                self.assertFalse(checker.contains_machine_specific_path(example))

    def test_generic_wrapper_residual_rule_preserves_valid_url_forms(self):
        examples = (
            "https://user!$&'()*+,;=:pass@example.test/-._~!$&'()*+,;=:@/Users/alice/guide",
            "https://[2001:db8::1]:8443/root/guide?key=$HOME=value#part_1",
            "~~https://example.test/release~notes/Users/alice/guide~~",
            "（https://example.test/release_notes/root/guide）",
            "<https://example.test/release*notes/opt/tool>",
            "https://example.test/Users/alice/guide https://example.test/root/guide",
            "*https://example.test/release*notes/opt/tool*",
            "_https://example.test/release_notes/home/alice/guide_",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertFalse(checker.contains_machine_specific_path(example))

    def test_generic_wrapper_residual_probe_has_bounded_linear_work(self):
        class CountedString(str):
            def __new__(cls, value, counts=None):
                instance = super().__new__(cls, value)
                instance.counts = counts if counts is not None else {"slice_work": 0}
                return instance

            def __getitem__(self, key):
                value = super().__getitem__(key)
                if isinstance(key, slice):
                    self.counts["slice_work"] += len(value)
                    return type(self)(value, self.counts)
                return value

        def residual_work(segments):
            candidate = CountedString(
                "https://example.test/" + "segment*" * segments
                + "1path%253D%252FUsers%252Falice"
            )
            self.assertIsNotNone(checker._split_url_candidate(candidate, ("*",)))
            return candidate.counts["slice_work"]

        small_work = residual_work(256)
        large_work = residual_work(512)
        self.assertLessEqual(large_work, small_work * 2 + 1024)

    def test_consecutive_wrapper_separator_scan_has_linear_slice_work(self):
        class CountedString(str):
            def __new__(cls, value, counts=None):
                instance = super().__new__(cls, value)
                instance.counts = counts if counts is not None else {"slice_work": 0}
                return instance

            def __getitem__(self, key):
                value = super().__getitem__(key)
                if isinstance(key, slice):
                    self.counts["slice_work"] += len(value)
                    return type(self)(value, self.counts)
                return value

        def sequence_work(segments):
            candidate = CountedString(
                "https://example.test/" + "segment*''" * segments + "path=public"
            )
            self.assertIsNotNone(checker._split_url_candidate(candidate, ("*",)))
            return candidate.counts["slice_work"]

        small_work = sequence_work(256)
        large_work = sequence_work(512)
        self.assertLessEqual(large_work, small_work * 2 + 1024)

    def test_alternating_wrapper_separator_scan_has_linear_slice_work(self):
        class CountedString(str):
            def __new__(cls, value, counts=None):
                instance = super().__new__(cls, value)
                instance.counts = counts if counts is not None else {"slice_work": 0}
                return instance

            def __getitem__(self, key):
                value = super().__getitem__(key)
                if isinstance(key, slice):
                    self.counts["slice_work"] += len(value)
                    return type(self)(value, self.counts)
                return value

        def alternating_work(segments):
            candidate = CountedString(
                "https://example.test/"
                + "segment*'a'b'" * segments
                + "path=public"
            )
            self.assertIsNotNone(checker._split_url_candidate(candidate, ("*",)))
            return candidate.counts["slice_work"]

        small_work = alternating_work(256)
        large_work = alternating_work(512)
        self.assertLessEqual(large_work, small_work * 2 + 1024)

    def test_url_boundary_residuals_use_bounded_percent_decoding(self):
        examples = (
            "https://example.test/guide\x1f/%" + "2FUsers%2Falice%2Fprivate",
            "https://example.test/guide</%" + "2Froot%2Fprivate",
            "https://example.test/guide>/%" + "252Fopt%252Fvendor",
            "https://example.test/guide&lt;/%" + "2Fhome%2Falice%2Fprivate",
            r"https://example.test/guide&gt;C%" + r"3A%5CUsers%5Calice%5Cprivate",
            "https://example.test/guide&amp;lt;/%" + "252Froot%252Fprivate",
            r"https://example.test/guide&amp;gt;C%" + r"253A%255CUsers%255Calice%255Cprivate",
            "https://example.test/guide</%ZZ/%" + "2FUsers%2Falice/private",
            "https://example.test/guide>/%" + "2525252Fopt%2525252Fvendor",
        )
        for example in examples:
            with self.subTest(example=repr(example)):
                self.assertTrue(checker.contains_machine_specific_path(example))

    def test_url_boundary_residuals_do_not_absorb_a_following_url(self):
        examples = (
            "<https://example.test/Users/alice/guide>"
            "<https://example.test/root/network-guide>",
            "https://example.test/" + "opt/network-guide\x1f"
            "https://example.test/Users/alice/guide",
        )
        for example in examples:
            with self.subTest(example=repr(example)):
                self.assertFalse(checker.contains_machine_specific_path(example))

    def test_repeated_symmetric_wrapper_closer_scan_has_linear_work(self):
        class CountedString(str):
            def __new__(cls, value, counts=None):
                instance = super().__new__(cls, value)
                instance.counts = counts if counts is not None else {"work": 0}
                return instance

            def __getitem__(self, key):
                value = super().__getitem__(key)
                if isinstance(key, slice):
                    self.counts["work"] += len(value)
                    return type(self)(value, self.counts)
                self.counts["work"] += 1
                return value

        def closer_work(segments):
            network_path = "https://example.test/" + "segment/" * segments
            candidate = CountedString(
                network_path + "*foo*bar%3Fbaz/" + "opt/vendor/tool*"
            )
            url, suffix = checker._split_url_candidate(candidate, ("*",))
            self.assertEqual(url, network_path)
            self.assertEqual(suffix, "*foo*bar%3Fbaz/" + "opt/vendor/tool*")
            return candidate.counts["work"]

        small_work = closer_work(256)
        large_work = closer_work(512)
        self.assertGreater(small_work, 0)
        self.assertLessEqual(large_work, small_work * 2 + 64)

    def test_wrapper_context_limits_fail_closed_with_bounded_work(self):
        class CountedString(str):
            def __new__(cls, value, counts=None):
                instance = super().__new__(cls, value)
                instance.counts = counts if counts is not None else {"index": 0}
                return instance

            def __getitem__(self, key):
                self.counts["index"] += 1
                value = super().__getitem__(key)
                if isinstance(key, slice):
                    return type(self)(value, self.counts)
                return value

        content = CountedString(
            "(" + " " * (checker.MAX_WRAPPER_CONTEXT_CHARACTERS + 512)
            + "https://example.test/Users/alice/guide"
        )
        start = content.index("https://")
        self.assertEqual(checker._url_wrapper_openers(content, start), (checker.CONTEXT_LIMIT,))
        self.assertLessEqual(
            content.counts["index"], checker.MAX_WRAPPER_CONTEXT_CHARACTERS + 2
        )
        self.assertTrue(checker.contains_machine_specific_path(content))

        overlong_tail = (
            "* https://example.test/Users/alice/guide"
            + " " * (checker.MAX_WRAPPER_CONTEXT_CHARACTERS + 512)
            + "*/public"
        )
        self.assertTrue(checker.contains_machine_specific_path(overlong_tail))

        def tail_work(spaces):
            tail_content = CountedString(" " * spaces + "*/%2FUsers%2Falice")
            suffix, exhausted = checker._bounded_wrapper_tail(tail_content, 0, ("*",))
            self.assertFalse(exhausted)
            self.assertEqual(suffix, " " * spaces + "*/%2FUsers%2Falice")
            return tail_content.counts["index"]

        small_work = tail_work(512)
        large_work = tail_work(1024)
        self.assertLessEqual(large_work, small_work * 2 + 8)

    def test_nested_percent_encoding_cannot_hide_machine_paths_in_url_parameters(self):
        examples = (
            "https://example.test/upload?source=%" + "252FUsers%252Falice%252Fprivate.txt",
            "https://example.test/docs#source=%" + "252Froot%252Fprivate",
            r"https://example.test/docs#source=C%" + r"253A%255CUsers%255Calice%255Cprivate.txt",
            "https://[not-an-ipv6]/%" + "252Fopt%252Fvendor%252Ftool",
            r"https://example.test:invalid/C%" + r"253A%255CUsers%255Calice%255Cprivate.txt",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertTrue(checker.contains_machine_specific_path(example))

    def test_encoding_beyond_decode_limit_fails_closed(self):
        examples = (
            "https://example.test/upload?source=%" + "2525252FUsers%2525252Falice",
            r"https://example.test/docs#source=C%" + r"2525253A%2525255CUsers%2525255Calice",
            "https://[not-an-ipv6]/%" + "2525252Froot%2525252Fprivate",
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertTrue(checker.contains_machine_specific_path(example))

    def test_percent_decoding_has_stability_and_depth_bounds(self):
        self.assertEqual(checker._bounded_percent_decodings("ordinary=value"), ("ordinary=value",))
        self.assertEqual(
            checker._bounded_percent_decodings("%252FUsers%252Falice"),
            ("%252FUsers%252Falice", "%2FUsers%2Falice", "/" + "Users/alice"),
        )
        deeply_encoded = "%252525252FUsers%252525252Falice"
        with mock.patch.object(checker, "unquote", wraps=checker.unquote) as decoder:
            layers = checker._bounded_percent_decodings(deeply_encoded)
            self.assertEqual(decoder.call_count, checker.MAX_PERCENT_DECODE_LAYERS)
            self.assertLessEqual(len(layers), checker.MAX_PERCENT_DECODE_LAYERS + 1)
            self.assertLessEqual(
                sum(len(layer) for layer in layers),
                len(deeply_encoded) * (checker.MAX_PERCENT_DECODE_LAYERS + 1),
            )
            self.assertTrue(checker._percent_decoding_limit_exhausted(layers))
            self.assertEqual(decoder.call_count, checker.MAX_PERCENT_DECODE_LAYERS + 1)

    def test_url_candidate_trimming_does_not_require_balanced_path_parentheses(self):
        self.assertEqual(
            checker._split_url_candidate("https://example.test/releases/foo(/Users/guide"),
            ("https://example.test/releases/foo(/Users/guide", ""),
        )
        self.assertEqual(
            checker._split_url_candidate("https://example.test/Users/guide)."),
            ("https://example.test/Users/guide", ")."),
        )
        self.assertEqual(
            checker._split_url_candidate("https://example.test/(stable)/Users/guide)."),
            ("https://example.test/(stable)/Users/guide", ")."),
        )

    def test_url_candidate_trimming_has_linear_scan_work(self):
        class CountedString(str):
            def __new__(cls, value, counts=None):
                instance = super().__new__(cls, value)
                instance.counts = counts if counts is not None else {"index": 0, "count_work": 0}
                return instance

            def __getitem__(self, key):
                self.counts["index"] += 1
                value = super().__getitem__(key)
                if isinstance(key, slice):
                    return type(self)(value, self.counts)
                return value

            def count(self, *args, **kwargs):
                self.counts["count_work"] += len(self)
                return super().count(*args, **kwargs)

        def trimming_work(closers):
            candidate = CountedString("https://example.test/guide" + ")" * closers)
            url, suffix = checker._split_url_candidate(candidate)
            self.assertEqual(url, "https://example.test/guide")
            self.assertEqual(suffix, ")" * closers)
            return candidate.counts["index"] + candidate.counts["count_work"]

        small_work = trimming_work(512)
        large_work = trimming_work(1024)
        self.assertLessEqual(large_work, small_work * 2 + 32)

    def test_url_wrapper_context_scan_has_linear_work(self):
        class CountedString(str):
            def __new__(cls, value, counts=None):
                instance = super().__new__(cls, value)
                instance.counts = counts if counts is not None else {"index": 0}
                return instance

            def __getitem__(self, key):
                self.counts["index"] += 1
                value = super().__getitem__(key)
                if isinstance(key, slice):
                    return type(self)(value, self.counts)
                return value

        def context_work(spaces):
            content = CountedString("Nested ( [" + " " * spaces + "https://example.test/guide")
            start = content.index("https://")
            self.assertEqual(checker._url_wrapper_openers(content, start), ("[", "("))
            return content.counts["index"]

        small_work = context_work(512)
        large_work = context_work(1024)
        self.assertLessEqual(large_work, small_work * 2 + 8)

    def test_documented_generic_tmp_path_is_allowed(self):
        readme = self.root / "README.md"
        example = "/tmp/codex-commander-behavioral-results.json"
        readme.write_text(readme.read_text(encoding="utf-8") + "\n" + example + "\n", encoding="utf-8")
        self.assertNotIn("Machine-specific path: README.md", self.errors())

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
