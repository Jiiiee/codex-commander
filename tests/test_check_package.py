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
            "https://example.test/releases/[stable]/Users/alice/guide",
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
        )
        for example in examples:
            with self.subTest(example=example):
                self.assertTrue(checker.contains_machine_specific_path(example))

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
