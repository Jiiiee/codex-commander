#!/usr/bin/env python3
"""Read-only structural checks, not a claim of behavioral correctness."""

import ast
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SKIP = {".git", "__pycache__", ".local-evaluation", "dist"}
REQUIRED = (
    "SKILL.md", "agents/openai.yaml", "README.md", "README.zh-CN.md", "LICENSE", "NOTICE.md",
    "licenses/mattpocock-skills-MIT.txt", "VERSION", "VALIDATION.md",
    "RELEASE_NOTES.md", "RELEASE_CHECKSUMS.txt", ".github/workflows/ci.yml",
    "references/engineering-depth.md", "references/sidebar-coordination.md",
    "references/project-records.md", "scripts/project_records.py",
    "scripts/run_behavioral_cases.py", "tests/test_project_records.py",
    "tests/test_behavioral_runner.py", "tests/test_check_package.py",
    "tests/behavioral-cases.json",
    "tests/behavioral-evaluation.md",
)
VERSION_PATTERN = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")
OPENAI_FIELDS = {"display_name", "short_description"}
MACHINE_SPECIFIC_PATHS = (
    re.compile(r"/(?:Users|Volumes|home)/[^\s`'\"<>()\[\]]+"),
    re.compile(r"/(?:opt|root)/[^\s`'\"<>()\[\]]+"),
    re.compile(r"/(?:private/(?:var|tmp)|var/folders)/[^\s`'\"<>()\[\]]+"),
    re.compile(r"[A-Za-z]:[\\\\/](?:Users|ProgramData|home)[\\\\/][^\s`'\"<>()\[\]]+"),
    re.compile(r"\\\\[^\\\\/\s]+\\(?:Users|ProgramData|home)\\[^\s`'\"<>()\[\]]+"),
)
URL = re.compile(r"https?://(?:(?!https?://)[^\s<>])+", re.I)
URL_TRAILING_PUNCTUATION = ".,;:!?"
MAX_PERCENT_DECODE_LAYERS = 3
HOSTNAME = re.compile(
    r"(?:[A-Za-z0-9_](?:[A-Za-z0-9_-]{0,61}[A-Za-z0-9_])?)"
    r"(?:\.(?:[A-Za-z0-9_](?:[A-Za-z0-9_-]{0,61}[A-Za-z0-9_])?))*\.?"
)
USERINFO = re.compile(r"(?:[A-Za-z0-9._~!$&'()*+,;=:]|%[0-9A-Fa-f]{2})+")
INVALID_PERCENT_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")
URI_PATH_CHARACTERS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    "-._~!$&'()*+,;=:@/"
)
HEXADECIMAL_CHARACTERS = frozenset("0123456789ABCDEFabcdef")
AMBIGUOUS_URL_PREFIX_CHARACTERS = frozenset("_*'+-.%:/\\@")
MAX_WRAPPER_CONTEXT_CHARACTERS = 4096
MAX_WRAPPER_DEPTH = 32
CONTEXT_LIMIT = "<wrapper-context-limit>"
WRAPPER_CLOSERS = {
    "(": ")",
    "[": "]",
    "'": "'",
    '"': '"',
    "‘": "’",
    "“": "”",
    "*": "*",
    "**": "**",
    "_": "_",
    "__": "__",
    "`": "`",
    "~~": "~~",
    "（": "）",
    "「": "」",
    "『": "』",
    "【": "】",
    "〈": "〉",
    "《": "》",
    "<": ">",
}
SYMMETRIC_WRAPPERS = frozenset(
    ("'", '"', "‘", "“", "*", "**", "_", "__", "`", "~~")
)
NON_URI_DOCUMENT_DELIMITERS = frozenset(('"', "`", "‘", "’", "“", "”"))


def _has_http_scheme_start_boundary(content, start, wrapper_openers=()):
    """Reject a scheme match embedded in an identifier or URI-like prefix."""
    if start == 0:
        return True
    if wrapper_openers:
        return True
    previous = content[start - 1]
    return not (
        previous.isalnum()
        or previous in AMBIGUOUS_URL_PREFIX_CHARACTERS
    )


def _url_wrapper_openers(content, start):
    """Return adjacent document openers using bounded, longest-token scanning."""
    openers = []
    index = start
    scanned = 0
    while index and scanned < MAX_WRAPPER_CONTEXT_CHARACTERS:
        character = content[index - 1]
        if character.isspace():
            index -= 1
            scanned += 1
            continue
        opener = None
        for width in (2, 1):
            token_start = index - width
            if token_start < 0:
                continue
            token = content[token_start:index]
            if token in WRAPPER_CLOSERS:
                opener = token
                break
        if opener is None or len(openers) == MAX_WRAPPER_DEPTH:
            break
        token_start = index - len(opener)
        if opener in SYMMETRIC_WRAPPERS and token_start and content[token_start - 1].isalnum():
            break
        openers.append(opener)
        scanned += len(opener)
        index = token_start
    if index and (
        scanned >= MAX_WRAPPER_CONTEXT_CHARACTERS or len(openers) == MAX_WRAPPER_DEPTH
    ):
        return (CONTEXT_LIMIT,)
    return tuple(openers)


def _is_wrapper_closer_boundary(candidate, end, outer_openers):
    """Distinguish document closers from legal URI sub-delimiters."""
    if end == len(candidate):
        return True
    remainder = candidate[end:]
    if remainder[0].isspace() or remainder[0] in URL_TRAILING_PUNCTUATION + "/\\%=":
        return True
    if any(remainder.startswith(WRAPPER_CLOSERS[opener]) for opener in outer_openers):
        return True
    if re.match(r"&(?:amp;)*(?:[A-Za-z_][A-Za-z0-9_.-]*)=", remainder):
        return True
    return re.match(r"[A-Za-z](?::|%[0-9A-Fa-f]{2})", remainder) is not None


def _remaining_wrapper_openers(suffix, wrapper_openers):
    """Account for wrapper closers already captured in a URL candidate suffix."""
    index = 0
    for position, opener in enumerate(wrapper_openers):
        closer = WRAPPER_CLOSERS[opener]
        while index < len(suffix) and suffix[index].isspace():
            index += 1
        if not suffix.startswith(closer, index):
            return wrapper_openers[position:]
        index += len(closer)
    return ()


def _bounded_wrapper_tail(content, start, wrapper_openers):
    """Capture spaced outer closers and their adjacent token with fixed work."""
    if not wrapper_openers:
        return "", False
    index = start
    scanned = 0

    def skip_space():
        nonlocal index, scanned
        while (
            index < len(content)
            and scanned < MAX_WRAPPER_CONTEXT_CHARACTERS
            and content[index].isspace()
        ):
            index += 1
            scanned += 1

    consumed_closer = False
    for opener in wrapper_openers:
        skip_space()
        if scanned == MAX_WRAPPER_CONTEXT_CHARACTERS and index < len(content):
            return content[start:index], True
        closer = WRAPPER_CLOSERS[opener]
        if not content.startswith(closer, index):
            return "", False
        if scanned + len(closer) > MAX_WRAPPER_CONTEXT_CHARACTERS:
            return content[start:index], True
        index += len(closer)
        scanned += len(closer)
        consumed_closer = True

    skip_space()
    token_start = index
    while (
        index < len(content)
        and scanned < MAX_WRAPPER_CONTEXT_CHARACTERS
        and not content[index].isspace()
    ):
        index += 1
        scanned += 1
    exhausted = scanned == MAX_WRAPPER_CONTEXT_CHARACTERS and index < len(content)
    token = content[token_start:index]
    next_url = URL.search(token)
    if next_url:
        next_openers = _url_wrapper_openers(token, next_url.start())
        if CONTEXT_LIMIT not in next_openers and _has_http_scheme_start_boundary(
            token, next_url.start(), next_openers
        ):
            index = token_start
    return (content[start:index] if consumed_closer else ""), exhausted


def _split_url_candidate(candidate, leading_delimiters=()):
    """Separate sentence/Markdown closers without imposing URI path balance."""
    if isinstance(leading_delimiters, str):
        wrapper_openers = (leading_delimiters,)
    else:
        wrapper_openers = tuple(leading_delimiters)
    expected_closer = WRAPPER_CLOSERS.get(wrapper_openers[0]) if wrapper_openers else None
    opener_counts = {"(": 0, "[": 0}
    closer_counts = {")": 0, "]": 0}
    matching_opener = {")": "(", "]": "["}

    # The character immediately before a URL tells us whether an otherwise legal
    # URI delimiter closes surrounding Markdown/sentence syntax.  Walk once so a
    # balanced delimiter inside the URI remains part of its path, while the first
    # unmatched closer for that surrounding wrapper terminates the URL span.
    end = len(candidate)
    for index in range(end):
        character = candidate[index]
        if character in NON_URI_DOCUMENT_DELIMITERS:
            end = index
            break
        if (
            wrapper_openers
            and expected_closer not in closer_counts
            and candidate.startswith(expected_closer, index)
            and _is_wrapper_closer_boundary(
                candidate, index + len(expected_closer), wrapper_openers[1:]
            )
        ):
            end = index
            break
        if character in opener_counts:
            opener_counts[character] += 1
        elif character in closer_counts:
            opener = matching_opener[character]
            if opener_counts[opener] > closer_counts[character]:
                closer_counts[character] += 1
            elif expected_closer == character:
                end = index
                break
            else:
                closer_counts[character] += 1

    while end and candidate[end - 1] in URL_TRAILING_PUNCTUATION:
        end -= 1

    # When there is no surrounding wrapper boundary, trim only excess closing
    # delimiters at the end.  The counts above are decremented as the reverse scan
    # advances, avoiding repeated whole-prefix ``count`` calls and keeping O(n).
    while end and candidate[end - 1] in closer_counts:
        closer = candidate[end - 1]
        opener = matching_opener[closer]
        if closer_counts[closer] <= opener_counts[opener]:
            break
        closer_counts[closer] -= 1
        end -= 1
    return candidate[:end], candidate[end:]


def _has_valid_uri_path(path):
    """Accept exactly RFC 3986 path pchars, separators, and percent triplets."""
    index = 0
    while index < len(path):
        character = path[index]
        if character == "%":
            if (
                index + 2 >= len(path)
                or path[index + 1] not in HEXADECIMAL_CHARACTERS
                or path[index + 2] not in HEXADECIMAL_CHARACTERS
            ):
                return False
            index += 3
            continue
        if character not in URI_PATH_CHARACTERS:
            return False
        index += 1
    return True


def _bounded_percent_decodings(value):
    """Return distinct decode layers, stopping at stability or a fixed limit."""
    layers = [value]
    for _ in range(MAX_PERCENT_DECODE_LAYERS):
        decoded = unquote(layers[-1])
        if decoded == layers[-1]:
            break
        layers.append(decoded)
    return tuple(layers)


def _percent_decoding_limit_exhausted(layers):
    """Report when another decoding pass would change a max-depth result."""
    return (
        len(layers) == MAX_PERCENT_DECODE_LAYERS + 1
        and unquote(layers[-1]) != layers[-1]
    )


def _has_valid_http_authority(parsed):
    """Validate full userinfo, host, and port syntax left permissive by urlsplit."""
    netloc = parsed.netloc
    if "\\" in netloc or netloc.count("@") > 1 or INVALID_PERCENT_ESCAPE.search(netloc):
        return False

    if "@" in netloc:
        userinfo, hostport = netloc.split("@", 1)
        if not userinfo or not USERINFO.fullmatch(userinfo):
            return False
    else:
        hostport = netloc

    if hostport.startswith("["):
        match = re.fullmatch(r"\[([^\]]+)\](?::[0-9]+)?", hostport)
        if not match:
            return False
        try:
            ipaddress.IPv6Address(match.group(1))
        except ipaddress.AddressValueError:
            return False
        return True

    if (
        any(delimiter in hostport for delimiter in "[]()")
        or hostport.endswith(":")
        or hostport.count(":") > 1
    ):
        return False
    try:
        ascii_hostname = parsed.hostname.encode("idna").decode("ascii")
    except UnicodeError:
        return False
    return HOSTNAME.fullmatch(ascii_hostname) is not None


def contains_machine_specific_path(content):
    """Ignore HTTP(S) network paths while scanning URL parameters for local paths."""
    decode_limit_exhausted = False

    def scan_payload(value):
        nonlocal decode_limit_exhausted
        layers = _bounded_percent_decodings(value)
        if _percent_decoding_limit_exhausted(layers):
            decode_limit_exhausted = True
        return "\n".join(layers)

    def replace_url(match):
        nonlocal decode_limit_exhausted
        candidate = match.group()
        wrapper_openers = _url_wrapper_openers(match.string, match.start())
        if CONTEXT_LIMIT in wrapper_openers:
            return scan_payload(candidate)
        if not _has_http_scheme_start_boundary(match.string, match.start(), wrapper_openers):
            return scan_payload(candidate)
        split_candidate = _split_url_candidate(candidate, wrapper_openers)
        if split_candidate is None:
            return scan_payload(candidate)
        url, suffix = split_candidate
        if INVALID_PERCENT_ESCAPE.search(url) or INVALID_PERCENT_ESCAPE.search(suffix):
            return scan_payload(candidate)
        try:
            parsed = urlsplit(url)
            hostname = parsed.hostname
            parsed.port  # Access validates a malformed or out-of-range port.
        except ValueError:
            return scan_payload(candidate)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc or not hostname:
            return scan_payload(candidate)
        if not _has_valid_http_authority(parsed):
            return scan_payload(candidate)
        if not _has_valid_uri_path(parsed.path):
            return scan_payload(candidate)

        # A URL path names a network resource, whereas query and fragment values
        # commonly carry local filenames.  Scan both their literal and decoded
        # forms so percent-encoding cannot bypass the package check.
        remaining_openers = _remaining_wrapper_openers(suffix, wrapper_openers)
        wrapper_tail, wrapper_limit_exhausted = _bounded_wrapper_tail(
            match.string, match.end(), remaining_openers
        )
        if wrapper_limit_exhausted:
            decode_limit_exhausted = True
        if INVALID_PERCENT_ESCAPE.search(wrapper_tail):
            return scan_payload(candidate + "\n" + wrapper_tail)
        return "\n".join(
            (
                scan_payload(parsed.query),
                scan_payload(parsed.fragment),
                scan_payload(suffix),
                scan_payload(wrapper_tail),
            )
        )

    without_urls = URL.sub(replace_url, content)
    return decode_limit_exhausted or any(
        pattern.search(without_urls) for pattern in MACHINE_SPECIFIC_PATHS
    )


def check_version(root, errors):
    path = root / "VERSION"
    if not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        errors.append("VERSION must be UTF-8")
        return
    version = text.removesuffix("\n")
    if text not in {version, version + "\n"} or not VERSION_PATTERN.fullmatch(version):
        errors.append("VERSION must be a canonical three-part numeric version")
        return

    validation = root / "VALIDATION.md"
    if not validation.is_file():
        return
    try:
        validation_text = validation.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        errors.append("VALIDATION.md must be UTF-8")
        return
    declared = re.search(r"^Version: ([0-9]+\.[0-9]+\.[0-9]+)\. Date:", validation_text, re.M)
    if not declared:
        errors.append("VALIDATION.md must declare its package version")
    elif declared.group(1) != version:
        errors.append(f"Version mismatch: VERSION is {version}, VALIDATION.md is {declared.group(1)}")

    notes = root / "RELEASE_NOTES.md"
    if notes.is_file():
        try:
            notes_text = notes.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append("RELEASE_NOTES.md must be UTF-8")
        else:
            declared_version = re.search(r"^Version: ([0-9]+\.[0-9]+\.[0-9]+)$", notes_text, re.M)
            declared_tag = re.search(r"^Intended tag: (v[0-9]+\.[0-9]+\.[0-9]+)$", notes_text, re.M)
            if not declared_version:
                errors.append("RELEASE_NOTES.md must declare its package version")
            elif declared_version.group(1) != version:
                errors.append(
                    f"Release-notes mismatch: VERSION is {version}, "
                    f"RELEASE_NOTES.md is {declared_version.group(1)}"
                )
            if not declared_tag:
                errors.append("RELEASE_NOTES.md must declare its intended v-prefixed tag")
            elif declared_tag.group(1) != f"v{version}":
                errors.append(
                    f"Tag mismatch: expected v{version}, RELEASE_NOTES.md is {declared_tag.group(1)}"
                )


def release_files(root):
    excluded = {".git", "RELEASE_CHECKSUMS.txt"}
    return sorted(
        str(path.relative_to(root))
        for path in root.rglob("*")
        if path.is_file()
        and not SKIP.intersection(path.relative_to(root).parts)
        and str(path.relative_to(root)) not in excluded
    )


def check_release_checksums(root, errors):
    checksum_path = root / "RELEASE_CHECKSUMS.txt"
    version_path = root / "VERSION"
    if not checksum_path.is_file() or not version_path.is_file():
        return
    try:
        version = version_path.read_text(encoding="utf-8").strip()
        lines = checksum_path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        errors.append("RELEASE_CHECKSUMS.txt and VERSION must be UTF-8")
        return
    expected_header = f"# Codex Commander v{version} release candidate SHA-256"
    if not lines or lines[0] != expected_header:
        errors.append(f"RELEASE_CHECKSUMS.txt header must match v{version}")
        return
    entries = {}
    for number, line in enumerate(lines[1:], 2):
        if not line:
            continue
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if not match:
            errors.append(f"Invalid RELEASE_CHECKSUMS.txt line: {number}")
            continue
        digest, relative = match.groups()
        if relative in entries:
            errors.append(f"Duplicate release checksum entry: {relative}")
        entries[relative] = digest

    expected_files = release_files(root)
    if sorted(entries) != expected_files:
        missing = sorted(set(expected_files) - set(entries))
        extra = sorted(set(entries) - set(expected_files))
        if missing:
            errors.append(f"Missing release checksum entries: {', '.join(missing)}")
        if extra:
            errors.append(f"Unexpected release checksum entries: {', '.join(extra)}")
    for relative in sorted(set(entries).intersection(expected_files)):
        observed = hashlib.sha256((root / relative).read_bytes()).hexdigest()
        if entries[relative] != observed:
            errors.append(f"Release checksum mismatch: {relative}")


def check_openai_yaml(root, errors):
    path = root / "agents/openai.yaml"
    if not path.is_file():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        errors.append("agents/openai.yaml must be UTF-8")
        return
    meaningful = [(number, line) for number, line in enumerate(lines, 1) if line.strip()]
    if not meaningful or meaningful[0][1] != "interface:":
        errors.append("agents/openai.yaml must contain a top-level interface mapping")
        return

    values = {}
    for number, line in meaningful[1:]:
        field = re.fullmatch(r"  ([a-z_]+):\s*(.+)", line)
        if not field:
            errors.append(f"Invalid agents/openai.yaml line: {number}")
            continue
        name, raw = field.groups()
        if name not in OPENAI_FIELDS:
            errors.append(f"Unexpected agents/openai.yaml field: {name}")
            continue
        if name in values:
            errors.append(f"Duplicate agents/openai.yaml field: {name}")
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            errors.append(f"Invalid quoted string in agents/openai.yaml: {name}")
            continue
        if not isinstance(value, str) or not value.strip():
            errors.append(f"agents/openai.yaml field must be a nonempty string: {name}")
            continue
        values[name] = value
    for name in sorted(OPENAI_FIELDS - values.keys()):
        errors.append(f"Missing agents/openai.yaml field: {name}")


def check_behavioral_cases(root, errors):
    path = root / "tests/behavioral-cases.json"
    if not path.is_file():
        return
    try:
        cases = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return  # The general text/JSON checks report syntax and encoding errors.
    if not isinstance(cases, list) or not cases:
        errors.append("tests/behavioral-cases.json must be a nonempty array")
        return

    seen_ids = set()
    required = {"id", "user", "context"}
    for index, case in enumerate(cases):
        label = f"Behavioral case {index}"
        if not isinstance(case, dict):
            errors.append(f"{label} must be an object")
            continue
        missing = sorted(required - case.keys())
        if missing:
            errors.append(f"{label} missing required fields: {', '.join(missing)}")
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id.strip():
            errors.append(f"{label} id must be a nonempty string")
        elif case_id in seen_ids:
            errors.append(f"Duplicate behavioral case id: {case_id}")
        else:
            seen_ids.add(case_id)
        if not isinstance(case.get("user"), str) or not case.get("user", "").strip():
            errors.append(f"{label} user must be a nonempty string")
        context = case.get("context")
        if not isinstance(context, (str, dict)):
            errors.append(f"{label} context must be a string or object")


def check(root=ROOT):
    errors = []
    for relative in REQUIRED:
        if not (root / relative).is_file():
            errors.append(f"Missing file: {relative}")
    skill = root / "SKILL.md"
    if skill.exists():
        try:
            text = skill.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append("SKILL.md must be UTF-8")
        else:
            if not text.startswith("---\n") or "\n---\n" not in text[4:]:
                errors.append("Missing skill YAML frontmatter")
            else:
                header = text.split("---", 2)[1]
                if not re.search(r"^name: codex-commander$", header, re.M):
                    errors.append("Skill name does not match the package")
                description = re.search(r'^description: (".*")$', header, re.M)
                if not description:
                    errors.append("Description must be a nonempty quoted scalar")
                else:
                    try:
                        if not json.loads(description.group(1)).strip():
                            errors.append("Empty description")
                    except json.JSONDecodeError:
                        errors.append("Description is not a valid quoted string")
            if "[TODO" in text:
                errors.append("Unfinished skill scaffold")
    check_version(root, errors)
    check_release_checksums(root, errors)
    check_openai_yaml(root, errors)
    check_behavioral_cases(root, errors)
    for path in root.rglob("*"):
        if not path.is_file() or SKIP.intersection(path.relative_to(root).parts):
            continue
        relative = str(path.relative_to(root))
        if path.suffix.lower() in {".mp4", ".mp3", ".srt", ".vtt", ".png", ".jpg"}:
            errors.append(f"Unexpected media in this instruction-only package: {relative}")
        if path.suffix not in {".md", ".py", ".json", ".yaml", ".txt"}:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"Non-UTF-8 text: {relative}")
            continue
        if contains_machine_specific_path(content):
            errors.append(f"Machine-specific path: {relative}")
        if re.search(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", content, re.I):
            errors.append(f"Potential private runtime ID: {relative}")
        if path.suffix == ".py":
            try:
                ast.parse(content, filename=relative)
            except SyntaxError as exc:
                errors.append(f"Python syntax error: {relative}: {exc.lineno}")
        if path.suffix == ".json":
            try:
                json.loads(content)
            except json.JSONDecodeError as exc:
                errors.append(f"JSON error: {relative}: {exc.lineno}")
        if path.suffix == ".md":
            for target in re.findall(r"\[[^\]]*\]\(([^)\s]+)\)", content):
                if re.match(r"[a-z]+:", target, re.I) or target.startswith("#"):
                    continue
                resolved = (path.parent / target.split("#", 1)[0]).resolve()
                if not resolved.is_relative_to(root.resolve()) or not resolved.exists():
                    errors.append(f"Missing/escaping local link: {relative}: {target}")
    return errors


def main():
    errors = check()
    print(json.dumps({"structural_check": "fail" if errors else "pass", "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
