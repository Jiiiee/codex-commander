#!/usr/bin/env python3
"""Read-only structural checks, not a claim of behavioral correctness."""

import ast
from bisect import bisect_right
import hashlib
from html.entities import html5
import ipaddress
import json
from pathlib import Path
import re
import sys
import unicodedata
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
    "docs/check-package-detection-contract-v0.5.md",
    "tests/fixtures/check-package-detection-contract-v0.5.json",
)
DEVELOPMENT_ONLY_FILES = {
    # The frozen specification necessarily contains literal reject examples.
    # It is retained as review evidence, but is not a release-package member.
    "docs/check-package-detection-contract-v0.5.md",
}
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
AMBIGUOUS_URL_PREFIX_CHARACTERS = frozenset("_*~'+-.%:/\\@")
MAX_WRAPPER_CONTEXT_CHARACTERS = 4096
MAX_WRAPPER_DEPTH = 32
CONTEXT_LIMIT = "<wrapper-context-limit>"
MAX_RESIDUAL_TOKEN_CHARACTERS = 64
MAX_RESIDUAL_SEPARATOR_CHARACTERS = MAX_RESIDUAL_TOKEN_CHARACTERS
MAX_HTML_ENTITY_LAYERS = 3
MAX_UTF8_BYTES_PER_CHARACTER = 4
PERCENT_ESCAPE_EXPANSION = 3
# 源窗口覆盖三层 HTML 前缀、总计 64 字符的 bounded token、总计
# 64 字符的 separator sequence 和赋值符；每个字符再按四字节 UTF-8
# 与三层 ``%XX`` 的最坏膨胀计算，不能使用经验常量。
MAX_RESIDUAL_DECODED_CHARACTERS = (
    1
    + 4 * MAX_HTML_ENTITY_LAYERS
    + MAX_RESIDUAL_TOKEN_CHARACTERS
    + MAX_RESIDUAL_SEPARATOR_CHARACTERS
    + 1
)
MAX_RESIDUAL_SOURCE_CHARACTERS = (
    MAX_RESIDUAL_DECODED_CHARACTERS
    * MAX_UTF8_BYTES_PER_CHARACTER
    * PERCENT_ESCAPE_EXPANSION ** MAX_PERCENT_DECODE_LAYERS
)
RESIDUAL_TOKEN_STRUCTURAL_DELIMITERS = frozenset(
    "=%/\\?#&*~'\"`(){}<>（）「」『』【】〈〉《》"
)
DRIVE_PREFIX = re.compile(r"[A-Za-z](?::|%[0-9A-Fa-f]{2})")
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
# ``=``/``%`` have dedicated phase transitions; URI component stops and a
# literal ``&``/single ``~`` are not document evidence by themselves.  A
# bounded ``&...;`` entity is promoted to evidence while scanning separators.
RESIDUAL_NON_DOCUMENT_STRUCTURAL_CHARACTERS = frozenset("=%/\\?#&~")
RESIDUAL_DOCUMENT_MARKERS = tuple(
    sorted(
        set(WRAPPER_CLOSERS)
        | set(WRAPPER_CLOSERS.values())
        | set(
            RESIDUAL_TOKEN_STRUCTURAL_DELIMITERS.difference(
                RESIDUAL_NON_DOCUMENT_STRUCTURAL_CHARACTERS
            )
        ),
        key=lambda marker: (-len(marker), marker),
    )
)
# Once a recognized wrapper closer starts the residual state machine, every
# structural delimiter except the two control characters handled separately
# below is an ambiguous separator.  Keeping this category grammar-derived lets
# raw and decoded URI component stops follow the same bounded/restart rules as
# document punctuation instead of becoming punctuation-specific safe exits.
AMBIGUOUS_RESIDUAL_SEPARATOR_CHARACTERS = frozenset(
    RESIDUAL_TOKEN_STRUCTURAL_DELIMITERS.difference("=%")
)
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
        if opener in SYMMETRIC_WRAPPERS and token_start:
            previous = content[token_start - 1]
            if previous.isalnum() or (opener == "~~" and previous == "~"):
                break
        openers.append(opener)
        scanned += len(opener)
        index = token_start
    if index and (
        scanned >= MAX_WRAPPER_CONTEXT_CHARACTERS or len(openers) == MAX_WRAPPER_DEPTH
    ):
        return (CONTEXT_LIMIT,)
    return tuple(openers)


def _ascii_case_insensitive_startswith(value, start, token):
    """Compare a fixed ASCII token without allocating an unbounded suffix."""
    if start + len(token) > len(value):
        return False
    for offset, expected in enumerate(token):
        actual = value[start + offset]
        if actual == expected:
            continue
        if "A" <= actual <= "Z":
            actual = chr(ord(actual) + 32)
        if actual != expected:
            return False
    return True


def _decoded_html_prefix(value):
    """Return the text after a bounded, case-insensitive ``&amp;`` prefix."""
    if not value.startswith("&"):
        return 0, False
    index = 1
    layers = 0
    while _ascii_case_insensitive_startswith(value, index, "amp;"):
        if layers == MAX_HTML_ENTITY_LAYERS:
            return index, True
        index += 4
        layers += 1
    return index, False


def _residual_document_marker(value, index):
    """Return the longest complete wrapper/document marker at one position."""
    return next(
        (
            marker
            for marker in RESIDUAL_DOCUMENT_MARKERS
            if value.startswith(marker, index)
        ),
        None,
    )


def _decoded_boundary_kind(
    value, allow_token, restart_closer=None, terminal_closers=()
):
    """用固定上界识别已解码的 wrapper 残余结构。"""
    index = 0
    separator_characters = 0
    if value.startswith("&"):
        index, exhausted = _decoded_html_prefix(value)
        if exhausted:
            return False, True
        if (
            _ascii_case_insensitive_startswith(value, index, "lt;")
            or _ascii_case_insensitive_startswith(value, index, "gt;")
        ):
            return True, False
        if not allow_token:
            return False, False
        separator_characters = index
    elif not allow_token:
        return False, False

    token_length = 0
    token_characters = 0
    has_restarted = False
    has_contradictory_marker = False
    while index < len(value):
        document_marker = _residual_document_marker(value, index)
        if restart_closer and document_marker == restart_closer:
            if has_restarted or has_contradictory_marker:
                return True, False
            index += len(restart_closer)
            separator_characters = 0
            token_length = 0
            token_characters = 0
            has_restarted = True
            continue
        if has_restarted and any(
            value.startswith(closer, index) for closer in terminal_closers
        ):
            return False, False
        if document_marker is not None:
            has_contradictory_marker = True
        character = value[index]
        if character == "=":
            return token_length > 0, False
        separator_end, separator_exhausted = _ambiguous_residual_separator_end(
            value, index
        )
        if separator_exhausted:
            return False, True
        if separator_end is not None:
            if not allow_token:
                return False, False
            if character == "&" and separator_end > index + 1:
                has_contradictory_marker = True
            token_length = 0
            separator_characters += separator_end - index
            if separator_characters > MAX_RESIDUAL_SEPARATOR_CHARACTERS:
                return False, True
            index = separator_end
            continue
        if (
            character.isspace()
            or character in RESIDUAL_TOKEN_STRUCTURAL_DELIMITERS
        ):
            return False, False
        if token_characters == MAX_RESIDUAL_TOKEN_CHARACTERS:
            return False, True
        index += 1
        token_length += 1
        token_characters += 1
    return False, token_characters > 0 or separator_characters > 0


def _ambiguous_residual_separator_end(value, index):
    """Return one raw/HTML separator end and whether its bound was exhausted."""
    character = value[index]
    if character not in AMBIGUOUS_RESIDUAL_SEPARATOR_CHARACTERS:
        return None, False
    if character != "&":
        return index + 1, False

    # Repeated ``amp;`` layers are one encoded separator.  This mirrors the
    # prefix decoder at arbitrary positions without allocating a suffix.
    entity_end = index + 1
    layers = 0
    while _ascii_case_insensitive_startswith(value, entity_end, "amp;"):
        if layers == MAX_HTML_ENTITY_LAYERS:
            return entity_end, True
        entity_end += 4
        layers += 1
    if layers:
        return entity_end, False

    # Treat another bounded named or numeric HTML entity as one separator token.
    # A bare ampersand remains a one-character separator.
    while entity_end < len(value) and entity_end - index <= MAX_RESIDUAL_TOKEN_CHARACTERS:
        character = value[entity_end]
        if character == ";":
            return entity_end + 1, False
        if not (character.isalnum() or character == "#"):
            break
        entity_end += 1
    return index + 1, False


def _bounded_boundary_probe(
    candidate,
    start,
    allow_token,
    restart_closer=None,
    terminal_closers=(),
):
    """在推导出的固定源窗口内解码；任何不完整状态均 fail-closed。"""
    source_end = min(len(candidate), start + MAX_RESIDUAL_SOURCE_CHARACTERS)
    source = candidate[start:source_end]
    source_truncated = source_end < len(candidate)
    layers = _bounded_percent_decodings(source)
    if (
        source_truncated
        or _percent_decoding_limit_exhausted(layers)
        or any(INVALID_PERCENT_ESCAPE.search(layer) for layer in layers)
    ):
        return False, True
    for layer in layers:
        matched, exhausted = _decoded_boundary_kind(
            layer, allow_token, restart_closer, terminal_closers
        )
        if matched or exhausted:
            return matched, exhausted
    return False, False


def _raw_residual_boundary(
    candidate, start, restart_closer=None, terminal_closers=()
):
    """线性扫描 raw 短 token 和连续结构分隔符；percent 交给 probe。"""
    if start >= len(candidate):
        return False, False, False
    if candidate[start] == "%":
        return False, True, False

    index = start
    token_length = 0
    token_characters = 0
    separator_characters = 0
    has_restarted = False
    has_contradictory_marker = False
    while index < len(candidate):
        document_marker = _residual_document_marker(candidate, index)
        if restart_closer and document_marker == restart_closer:
            if has_restarted or has_contradictory_marker:
                return True, False, False
            index += len(restart_closer)
            separator_characters = 0
            token_length = 0
            token_characters = 0
            has_restarted = True
            continue
        if has_restarted and any(
            candidate.startswith(closer, index) for closer in terminal_closers
        ):
            return False, False, False
        if document_marker is not None:
            has_contradictory_marker = True
        character = candidate[index]
        if character == "=":
            return token_length > 0, False, False
        if character == "%":
            return False, True, False
        separator_end, separator_exhausted = _ambiguous_residual_separator_end(
            candidate, index
        )
        if separator_exhausted:
            return False, False, True
        if separator_end is not None:
            if character == "&" and separator_end > index + 1:
                has_contradictory_marker = True
            token_length = 0
            separator_characters += separator_end - index
            if separator_characters > MAX_RESIDUAL_SEPARATOR_CHARACTERS:
                return False, False, True
            index = separator_end
            continue
        if (
            character.isspace()
            or character in RESIDUAL_TOKEN_STRUCTURAL_DELIMITERS
        ):
            return False, False, False
        if token_characters == MAX_RESIDUAL_TOKEN_CHARACTERS:
            return False, False, True
        index += 1
        token_length += 1
        token_characters += 1
    return False, False, token_characters > 0 or separator_characters > 0


def _is_wrapper_closer_boundary(candidate, end, closer, outer_openers):
    """Distinguish document closers from legal URI sub-delimiters."""
    if end == len(candidate):
        return True
    if candidate[end].isspace() or candidate[end] in URL_TRAILING_PUNCTUATION + "/\\%=":
        return True
    if any(candidate.startswith(WRAPPER_CLOSERS[opener], end) for opener in outer_openers):
        return True
    outer_closers = tuple(WRAPPER_CLOSERS[opener] for opener in outer_openers)
    residual, requires_probe, exhausted = _raw_residual_boundary(
        candidate, end, closer, outer_closers
    )
    if exhausted:
        return None
    if residual:
        return True
    if requires_probe:
        residual, exhausted = _bounded_boundary_probe(
            candidate,
            end,
            allow_token=True,
            restart_closer=closer,
            terminal_closers=outer_closers,
        )
        if exhausted:
            return None
    return residual or DRIVE_PREFIX.match(candidate, end) is not None


def _bounded_url_boundary_tail(content, start):
    """Capture text attached after a raw URL boundary with bounded work."""
    if start == len(content):
        return "", False
    character = content[start]
    codepoint = ord(character)
    if character not in "<>" and not (codepoint < 0x20 or 0x7F <= codepoint <= 0x9F):
        return "", False

    index = start + 1
    scanned = 1
    while (
        index < len(content)
        and scanned < MAX_WRAPPER_CONTEXT_CHARACTERS
        and not content[index].isspace()
    ):
        index += 1
        scanned += 1
    exhausted = scanned == MAX_WRAPPER_CONTEXT_CHARACTERS and index < len(content)
    next_url = URL.search(content, start + 1, index)
    if next_url:
        next_openers = _url_wrapper_openers(content, next_url.start())
        if CONTEXT_LIMIT not in next_openers and _has_http_scheme_start_boundary(
            content, next_url.start(), next_openers
        ):
            index = next_url.start()
            exhausted = False
    return content[start:index], exhausted


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


def _split_url_candidate(
    candidate, leading_delimiters=(), has_external_wrapper_closer=False
):
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
        if character == "&":
            html_boundary, exhausted = _bounded_boundary_probe(
                candidate, index, allow_token=False
            )
            if exhausted:
                return None
            if html_boundary:
                end = index
                break
        if character in NON_URI_DOCUMENT_DELIMITERS:
            end = index
            break
        if (
            wrapper_openers
            and expected_closer not in closer_counts
            and candidate.startswith(expected_closer, index)
        ):
            boundary = _is_wrapper_closer_boundary(
                candidate,
                index + len(expected_closer),
                expected_closer,
                wrapper_openers[1:],
            )
            if boundary is None:
                if has_external_wrapper_closer:
                    continue
                return None
            if boundary:
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
    """仅豁免无歧义的 HTTP(S) 网络路径；歧义输入按安全优先 fail-closed。"""
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
        boundary_tail, boundary_limit_exhausted = _bounded_url_boundary_tail(
            match.string, match.end()
        )
        if boundary_limit_exhausted:
            decode_limit_exhausted = True

        def scan_candidate():
            return scan_payload(candidate + "\n" + boundary_tail)

        wrapper_openers = _url_wrapper_openers(match.string, match.start())
        if CONTEXT_LIMIT in wrapper_openers:
            return scan_candidate()
        if not _has_http_scheme_start_boundary(match.string, match.start(), wrapper_openers):
            return scan_candidate()
        split_candidate = _split_url_candidate(candidate, wrapper_openers)
        if split_candidate is None:
            external_wrapper_tail, external_wrapper_limit_exhausted = (
                _bounded_wrapper_tail(match.string, match.end(), wrapper_openers)
            )
            if external_wrapper_limit_exhausted:
                decode_limit_exhausted = True
            if external_wrapper_tail:
                split_candidate = _split_url_candidate(
                    candidate,
                    wrapper_openers,
                    has_external_wrapper_closer=True,
                )
            if split_candidate is None:
                return scan_candidate()
        url, suffix = split_candidate
        if (
            INVALID_PERCENT_ESCAPE.search(url)
            or INVALID_PERCENT_ESCAPE.search(suffix)
            or INVALID_PERCENT_ESCAPE.search(boundary_tail)
        ):
            return scan_candidate()
        try:
            parsed = urlsplit(url)
            hostname = parsed.hostname
            parsed.port  # Access validates a malformed or out-of-range port.
        except ValueError:
            return scan_candidate()
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc or not hostname:
            return scan_candidate()
        if not _has_valid_http_authority(parsed):
            return scan_candidate()
        if not _has_valid_uri_path(parsed.path):
            return scan_candidate()

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
                scan_payload(boundary_tail),
            )
        )

    without_urls = URL.sub(replace_url, content)
    return decode_limit_exhausted or any(
        pattern.search(without_urls) for pattern in MACHINE_SPECIFIC_PATHS
    )


# Frozen detection contract v0.5.  The legacy boolean helper above remains for
# callers that depended on its historical fail-closed URL heuristics; package
# validation uses the structured, manifest-driven entry points below.
DETECTION_WINDOW = 16_384
DETECTION_OVERLAP = 8_192
MAX_DETECTION_TOKEN = 8_192
MAX_DETECTION_DEPTH = 3
MAX_DETECTION_STATES = 15
ASCII_WHITESPACE = frozenset(" \t\n\r\f\v")
PATH_TERMINATORS = frozenset(
    "\"'`()[]{}<>,;!?，。；：！？、（）【】《》「」『』"
)
PLACEHOLDER = re.compile(r"<[A-Za-z][A-Za-z0-9_-]*>\Z")
HTTP_START = re.compile(r"https?://", re.I)
BAD_BARE_URL_END = frozenset(".,\"'`()[]{}<>;!?，。；：！？、（）【】《》「」『』*_~")
REPORT_PRIORITY = {
    "text_encoding": 0,
    "candidate_too_long": 1,
    "url_boundary": 2,
    "machine_path": 3,
}
REPORT_HINT = {
    "text_encoding": "fix_utf8",
    "candidate_too_long": "reduce_token",
    "url_boundary": "rewrite_url",
    "machine_path": "use_placeholder",
}
REPORT_ADVICE = {
    "text_encoding": "save the file as strict UTF-8",
    "candidate_too_long": "split the path or URL candidate into a shorter token",
    "url_boundary": "rewrite the URL as [text](URL) or <URL>",
    "machine_path": "replace the device-specific segment with an approved placeholder",
}


def _ascii_space(character):
    return character in ASCII_WHITESPACE


def _source_span(spans, start, end):
    if start >= end:
        return (0, 0)
    # Both approved transforms preserve source order, so endpoint spans are the
    # exact union bounds without copying or rescanning a candidate substring.
    return (spans[start][0], spans[end - 1][1])


def _transform_percent(text, spans):
    output = []
    output_spans = []
    index = 0
    while index < len(text):
        if (
            text[index] == "%"
            and index + 2 < len(text)
            and text[index + 1] in HEXADECIMAL_CHARACTERS
            and text[index + 2] in HEXADECIMAL_CHARACTERS
        ):
            value = int(text[index + 1:index + 3], 16)
            if value < 128:
                output.append(chr(value))
                output_spans.append(_source_span(spans, index, index + 3))
                index += 3
                continue
        output.append(text[index])
        output_spans.append(spans[index])
        index += 1
    return "".join(output), tuple(output_spans)


def _transform_entities(text, spans):
    output = []
    output_spans = []
    index = 0
    while index < len(text):
        if text[index] == "&":
            cursor = index + 1
            base = None
            if cursor < len(text) and text[cursor] == "#":
                cursor += 1
                if cursor < len(text) and text[cursor] in "xX":
                    base = 16
                    cursor += 1
                    digit_start = cursor
                    while cursor < len(text) and text[cursor] in HEXADECIMAL_CHARACTERS:
                        cursor += 1
                else:
                    base = 10
                    digit_start = cursor
                    while cursor < len(text) and text[cursor].isascii() and text[cursor].isdigit():
                        cursor += 1
            else:
                digit_start = cursor
                while cursor < len(text) and text[cursor].isascii() and text[cursor].isalnum():
                    cursor += 1

            decoded = None
            if cursor < len(text) and text[cursor] == ";" and cursor > digit_start:
                body = text[digit_start:cursor]
                if base is not None:
                    # Numeric entities have no contract length cap.  Strip zero
                    # padding before bounded integer conversion so even an
                    # arbitrarily long decimal/hex spelling remains linear and
                    # avoids Python's large-integer digit guard.
                    significant = body.lstrip("0") or "0"
                    if len(significant) <= (2 if base == 16 else 3):
                        value = int(significant, base)
                        if value < 128:
                            decoded = chr(value)
                else:
                    decoded = html5.get(body + ";")
            if decoded is not None and all(ord(character) < 128 for character in decoded):
                span = _source_span(spans, index, cursor + 1)
                output.extend(decoded)
                output_spans.extend((span,) * len(decoded))
                index = cursor + 1
                continue
        output.append(text[index])
        output_spans.append(spans[index])
        index += 1
    return "".join(output), tuple(output_spans)


def _valid_percent_syntax(value):
    index = 0
    while index < len(value):
        if value[index] == "%":
            if (
                index + 2 >= len(value)
                or value[index + 1] not in HEXADECIMAL_CHARACTERS
                or value[index + 2] not in HEXADECIMAL_CHARACTERS
            ):
                return False
            index += 3
        else:
            index += 1
    return True


def _valid_http_url(value):
    if any(_ascii_space(character) or ord(character) < 32 or ord(character) == 127 for character in value):
        return None
    if not _valid_percent_syntax(value):
        return None
    scheme = HTTP_START.match(value)
    if not scheme or scheme.start() != 0:
        return None
    authority_start = scheme.end()
    authority_end = len(value)
    for delimiter in "/?#":
        position = value.find(delimiter, authority_start)
        if position != -1:
            authority_end = min(authority_end, position)
    authority = value[authority_start:authority_end]
    if not authority or "\\" in authority or authority.count("@") > 1:
        return None
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        parsed.port
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc or not host:
        return None
    if any(unicodedata.category(character) in {"Cc", "Cf", "Zs", "Zl", "Zp"} for character in host):
        return None
    hostport = authority.rsplit("@", 1)[-1]
    if hostport.startswith("["):
        close = hostport.find("]")
        if close == -1:
            return None
        remainder = hostport[close + 1:]
        if remainder == ":" or (remainder and not re.fullmatch(r":[0-9]+", remainder)):
            return None
        literal = hostport[1:close]
        if literal.lower().startswith("v"):
            return None
        try:
            ipaddress.IPv6Address(literal)
        except ipaddress.AddressValueError:
            return None
    else:
        if hostport.endswith(":") or hostport.count(":") > 1:
            return None
        try:
            ipaddress.IPv4Address(host)
        except ipaddress.AddressValueError:
            try:
                labels = host.rstrip(".").split(".")
                if not labels or any(not label for label in labels):
                    return None
                ascii_labels = [label.encode("idna").decode("ascii") for label in labels]
            except UnicodeError:
                return None
            if any(
                not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
                for label in ascii_labels
            ):
                return None
    path_start = authority_end
    query_start = value.find("?", authority_end)
    fragment_start = value.find("#", authority_end)
    path_end = min(
        [position for position in (query_start, fragment_start) if position != -1]
        or [len(value)]
    )
    non_path = []
    if "@" in authority:
        non_path.append((authority_start, authority_start + authority.rfind("@")))
    if query_start != -1:
        non_path.append((query_start + 1, fragment_start if fragment_start > query_start else len(value)))
    if fragment_start != -1:
        non_path.append((fragment_start + 1, len(value)))
    return {"path": (path_start, path_end), "non_path": tuple(non_path)}


def _raw_url_regions(text, global_start):
    exempt = []
    forced = []
    boundary = []
    too_long = []
    url_starts = []
    whitespace = []
    inline_closers = []
    autolink_closers = []
    last_label_open = -1
    last_label_close = -1
    previous_label_close = -1

    # Tokenize the raw window exactly once from left to right.  Boundary
    # positions let candidate extraction avoid a backward label search and
    # repeated forward searches over overlapping suffixes for every URL start.
    for index, character in enumerate(text):
        match = HTTP_START.match(text, index)
        if match is not None:
            inline = (
                index >= 2
                and text[index - 2:index] == "]("
                and last_label_open != -1
                and previous_label_close <= last_label_open
            )
            url_starts.append(
                (
                    index,
                    match.end(),
                    inline,
                    index > 0 and text[index - 1] == "<",
                    index == 0 or _ascii_space(text[index - 1]),
                )
            )
        if _ascii_space(character):
            whitespace.append(index)
        if character == ")":
            inline_closers.append(index)
        elif character == ">":
            autolink_closers.append(index)
        if character == "[":
            last_label_open = index
        elif character == "]":
            previous_label_close = last_label_close
            last_label_close = index

    work = len(text)
    occupied_until = -1
    whitespace_index = 0
    inline_closer_index = 0
    autolink_closer_index = 0
    for start, scheme_end, inline, autolink, bare in url_starts:
        if start < occupied_until:
            continue
        kind = None
        end = None
        if inline:
            while (
                inline_closer_index < len(inline_closers)
                and inline_closers[inline_closer_index] < scheme_end
            ):
                inline_closer_index += 1
            if inline_closer_index < len(inline_closers):
                kind, end = "inline", inline_closers[inline_closer_index]
        elif autolink:
            while (
                autolink_closer_index < len(autolink_closers)
                and autolink_closers[autolink_closer_index] < scheme_end
            ):
                autolink_closer_index += 1
            if autolink_closer_index < len(autolink_closers):
                kind, end = "autolink", autolink_closers[autolink_closer_index]
        elif bare:
            while (
                whitespace_index < len(whitespace)
                and whitespace[whitespace_index] < scheme_end
            ):
                whitespace_index += 1
            end = (
                whitespace[whitespace_index]
                if whitespace_index < len(whitespace)
                else len(text)
            )
            kind = "bare"
        if end is None:
            while (
                whitespace_index < len(whitespace)
                and whitespace[whitespace_index] < scheme_end
            ):
                whitespace_index += 1
            end = (
                whitespace[whitespace_index]
                if whitespace_index < len(whitespace)
                else len(text)
            )
        candidate = text[start:end]
        work += len(candidate)
        explicit = kind is not None
        if kind == "bare" and candidate and candidate[-1] in BAD_BARE_URL_END:
            explicit = False
        parsed = _valid_http_url(candidate) if explicit else None
        source_start = global_start + start
        source_end = global_start + end
        occupied_until = end
        if source_end - source_start > MAX_DETECTION_TOKEN:
            too_long.append((source_start, source_end))
        if parsed is None:
            boundary.append((source_start, source_end))
            continue
        path_start, path_end = parsed["path"]
        exempt.append((source_start + path_start, source_start + path_end))
        forced.extend(
            (source_start + component_start, source_start + component_end)
            for component_start, component_end in parsed["non_path"]
        )
    return exempt, forced, boundary, too_long, work


def _in_interval(start, end, intervals):
    return any(start >= left and end <= right for left, right in intervals)


def _overlaps_interval(start, end, intervals):
    return any(start < right and end > left for left, right in intervals)


def _token_end(text, start):
    end = start
    while end < len(text):
        if text[end] == "<" and end > start and text[end - 1] in "/\\":
            placeholder = re.match(r"<[A-Za-z][A-Za-z0-9_-]*>", text[end:])
            if placeholder:
                placeholder_end = end + placeholder.end()
                if (
                    placeholder_end == len(text)
                    or text[placeholder_end] in "/\\"
                    or _ascii_space(text[placeholder_end])
                    or text[placeholder_end] in PATH_TERMINATORS
                ):
                    end = placeholder_end
                    continue
        if _ascii_space(text[end]) or text[end] in PATH_TERMINATORS:
            break
        end += 1
    return end


def _placeholder(value):
    return PLACEHOLDER.fullmatch(value) is not None


def _root_or_descendant(value, root):
    return value == root or value.startswith(root + "/")


def _machine_path_token(token):
    for root in (
        "\x2fprivate/var/folders", "\x2fvar/folders", "\x2fprivate/tmp",
        "\x2fopt/homebrew", "\x2froot",
    ):
        if _root_or_descendant(token, root):
            return True
    for root in ("\x2fUsers", "\x2fVolumes", "\x2fhome"):
        prefix = root + "/"
        if token.startswith(prefix):
            segment = token[len(prefix):].split("/", 1)[0]
            if segment and not _placeholder(segment):
                return True

    normalized = token.replace("\\", "/")
    if re.match(r"^[A-Za-z]:/", normalized):
        remainder = normalized[3:]
        lowered = remainder.lower()
        if lowered == "programdata" or lowered.startswith("programdata/"):
            return True
        if lowered.startswith("users/"):
            segment = remainder[6:].split("/", 1)[0]
            if segment and not _placeholder(segment):
                return True

    if token.startswith("\\\\"):
        parts = re.split(r"[\\/]", token[2:])
        if len(parts) >= 3 and all(parts[:3]):
            host, share = parts[:2]
            if not (_placeholder(host) and _placeholder(share)):
                return True
    return False


def _looks_like_path_start(text, index):
    if any(
        text.startswith(prefix, index)
        for prefix in (
            "\x2fUsers", "\x2fVolumes", "\x2fhome", "\x2fprivate/var/folders",
            "\x2fvar/folders", "\x2fprivate/tmp", "\x2fopt/homebrew", "\x2froot",
        )
    ):
        return True
    if index + 2 < len(text) and text[index].isascii() and text[index].isalpha():
        return text[index + 1] == ":" and text[index + 2] in "/\\"
    return text.startswith("\\\\", index)


def _make_report(file_name, line, category, source_start, source_end):
    return {
        "file": file_name,
        "line": line,
        "category": category,
        "hint_kind": REPORT_HINT[category],
        "source_start": source_start,
        "source_end": source_end,
        "message": REPORT_ADVICE[category],
    }


def scan_text(text, file_name="<memory>"):
    """Scan one already-decoded text using the public v0.5 result model."""
    reports = []
    metrics = {
        "work": 0,
        "states": 0,
        "max_depth": 0,
        "max_window": 0,
        "max_candidate_span": 0,
    }
    line_starts = [0]
    line_starts.extend(index + 1 for index, character in enumerate(text) if character == "\n")

    def line_for(position):
        return bisect_right(line_starts, position)

    for window_start in range(0, len(text), DETECTION_OVERLAP):
        raw = text[window_start:min(window_start + DETECTION_WINDOW, len(text))]
        metrics["max_window"] = max(metrics["max_window"], len(raw))
        exempt, forced, boundary, long_urls, raw_url_work = _raw_url_regions(raw, window_start)
        metrics["work"] += raw_url_work
        for source_start, source_end in long_urls:
            metrics["max_candidate_span"] = max(metrics["max_candidate_span"], source_end - source_start)
            reports.append(_make_report(file_name, line_for(source_start), "candidate_too_long", source_start, source_end))

        initial_spans = tuple((window_start + index, window_start + index + 1) for index in range(len(raw)))
        states = [(raw, initial_spans, 0)]
        seen = {raw}
        state_index = 0
        while state_index < len(states):
            value, spans, depth = states[state_index]
            state_index += 1
            metrics["work"] += len(value)
            metrics["max_depth"] = max(metrics["max_depth"], depth)

            index = 0
            current_token_end = 0
            while index < len(value):
                if not _looks_like_path_start(value, index):
                    index += 1
                    continue
                if index < current_token_end:
                    end = current_token_end
                else:
                    end = _token_end(value, index)
                    current_token_end = end
                source_start, source_end = _source_span(spans, index, end)
                in_exempt = _in_interval(source_start, source_end, exempt)
                in_forced = _overlaps_interval(source_start, source_end, forced)
                in_boundary = _overlaps_interval(source_start, source_end, boundary)
                ordinary_boundary = (
                    index == 0
                    and (source_start == 0 or text[source_start - 1] in ASCII_WHITESPACE or text[source_start - 1] in PATH_TERMINATORS)
                ) or (
                    index > 0 and (value[index - 1] in ASCII_WHITESPACE or value[index - 1] in PATH_TERMINATORS)
                )
                if not (in_exempt or in_forced or in_boundary or ordinary_boundary):
                    index += 1
                    continue
                span_length = source_end - source_start
                metrics["max_candidate_span"] = max(metrics["max_candidate_span"], span_length)
                if span_length > MAX_DETECTION_TOKEN:
                    category = "candidate_too_long"
                elif _machine_path_token(value[index:end]):
                    if in_exempt:
                        index += 1
                        continue
                    category = "url_boundary" if in_boundary else "machine_path"
                else:
                    index += 1
                    continue
                reports.append(_make_report(file_name, line_for(source_start), category, source_start, source_end))
                index = max(index + 1, end)

            if depth == MAX_DETECTION_DEPTH:
                continue
            for transform in (_transform_percent, _transform_entities):
                metrics["work"] += len(value)
                transformed, transformed_spans = transform(value, spans)
                if transformed not in seen and len(states) < MAX_DETECTION_STATES:
                    seen.add(transformed)
                    states.append((transformed, transformed_spans, depth + 1))
        metrics["states"] = max(metrics["states"], len(states))

    deduplicated = {}
    for report in reports:
        # Overlapping fixed windows may observe one original candidate once in
        # full and once truncated.  Source start identifies that candidate;
        # keep only the contract's highest-priority result for the location.
        key = report["source_start"]
        previous = deduplicated.get(key)
        if previous is None or REPORT_PRIORITY[report["category"]] < REPORT_PRIORITY[previous["category"]]:
            deduplicated[key] = report
    ordered = sorted(
        deduplicated.values(),
        key=lambda report: (report["source_start"], REPORT_PRIORITY[report["category"]]),
    )
    return {"reports": ordered, "metrics": metrics}


def _manifest_entries(root):
    path = root / "RELEASE_CHECKSUMS.txt"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    entries = []
    for line in lines[1:]:
        match = re.fullmatch(r"[0-9a-f]{64}  (.+)", line)
        if match and match.group(1) != "RELEASE_CHECKSUMS.txt":
            entries.append(match.group(1))
    return entries


def scan_release_paths(root=ROOT):
    """Scan every manifest member and return v0.5 reports and aggregate metrics."""
    reports = []
    structure_errors = []
    aggregate = {
        "work": 0,
        "states": 0,
        "max_depth": 0,
        "max_window": 0,
        "max_candidate_span": 0,
    }
    resolved_root = root.resolve()
    for relative in _manifest_entries(root):
        listed_path = root / relative
        if listed_path.is_symlink():
            structure_errors.append(
                "Release checksum entry must be a regular file, not a symbolic link: "
                f"{relative}"
            )
            continue
        path = listed_path.resolve()
        try:
            path.relative_to(resolved_root)
        except ValueError:
            structure_errors.append(f"Release checksum entry escapes package root: {relative}")
            continue
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            line = raw[:error.start].count(b"\n") + 1
            reports.append(_make_report(relative, line, "text_encoding", error.start, error.start + 1))
            continue
        result = scan_text(text, relative)
        reports.extend(result["reports"])
        aggregate["work"] += result["metrics"]["work"]
        for key in ("states", "max_depth", "max_window", "max_candidate_span"):
            aggregate[key] = max(aggregate[key], result["metrics"][key])
    reports.sort(key=lambda report: (report["file"], report["source_start"], REPORT_PRIORITY[report["category"]]))
    return {
        "reports": reports,
        "structure_errors": structure_errors,
        "metrics": aggregate,
    }


def format_detection_report(report):
    return (
        f"{report['category']}: {report['file']}:{report['line']}; "
        f"hint_kind={report['hint_kind']}; {report['message']}"
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
        and str(path.relative_to(root)) not in DEVELOPMENT_ONLY_FILES
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
    detection_result = scan_release_paths(root)
    errors.extend(detection_result["structure_errors"])
    detection_reports = detection_result["reports"]
    legacy_path_errors = {
        f"Machine-specific path: {report['file']}"
        for report in detection_reports
        if report["category"] != "text_encoding"
    }
    errors.extend(sorted(legacy_path_errors))
    errors.extend(format_detection_report(report) for report in detection_reports)
    for path in root.rglob("*"):
        if not path.is_file() or SKIP.intersection(path.relative_to(root).parts):
            continue
        relative = str(path.relative_to(root))
        if relative in DEVELOPMENT_ONLY_FILES:
            continue
        if path.suffix.lower() in {".mp4", ".mp3", ".srt", ".vtt", ".png", ".jpg"}:
            errors.append(f"Unexpected media in this instruction-only package: {relative}")
        if path.suffix not in {".md", ".py", ".json", ".yaml", ".txt"}:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"Non-UTF-8 text: {relative}")
            continue
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
