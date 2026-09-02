#!/usr/bin/env python3
"""Read-only structural checks, not a claim of behavioral correctness."""

import ast
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SKIP = {".git", "__pycache__", ".local-evaluation", "dist"}
REQUIRED = (
    "SKILL.md", "agents/openai.yaml", "README.md", "README.zh-CN.md", "LICENSE", "NOTICE.md",
    "licenses/mattpocock-skills-MIT.txt", "VERSION", "VALIDATION.md",
    "references/engineering-depth.md", "references/sidebar-coordination.md",
    "references/project-records.md", "scripts/project_records.py",
    "tests/test_project_records.py", "tests/behavioral-cases.json",
    "tests/behavioral-evaluation.md",
)


def check(root=ROOT):
    errors = []
    for relative in REQUIRED:
        if not (root / relative).is_file():
            errors.append(f"Missing file: {relative}")
    skill = root / "SKILL.md"
    if skill.exists():
        text = skill.read_text(encoding="utf-8")
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
        if re.search(r"/(?:Users|Volumes)/[A-Za-z0-9]", content):
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
