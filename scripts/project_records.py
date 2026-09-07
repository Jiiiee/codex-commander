#!/usr/bin/env python3
"""Preview or initialize minimal project records; Python 3.10+, standard library."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import threading
import time
import uuid

try:
    import fcntl
except ImportError:  # Windows keeps preview support but apply is refused below.
    fcntl = None

BEGIN = "<!-- codex-commander:begin -->"
END = "<!-- codex-commander:end -->"
LEVELS = ("prototype", "maintainable", "production")
_UMASK_LOCK = threading.Lock()
_TEMPORARY_PATTERN = re.compile(
    r"^\.commander-v1-([0-9a-f]{64})-([0-9a-f]{64})-([0-9]{1,20})-([0-9a-f]{32})$"
)

TEXT = {
    "en": {
        "rules_title": "Codex Commander working agreement",
        "rules": [
            "For commander-managed work, read `docs/commander.md` for the current agreement. These rules do not launch a team by themselves.",
            "Follow the user's conversation and document language; preserve explicit per-artifact language choices.",
            "Create project-team tasks under the verified target project. Keep its normal sidebar grouping; create or use a custom section only when the user explicitly requests it. Pass this placement agreement to any delegated commander.",
            "The commander owns shared planning records. Workers stay within assigned outputs, preserve other people's changes, and report completion or genuine blockers to the verified commander destination.",
            "Accept work only after checking the actual artifact and relevant evidence. Do not silently expand the agreed scope or engineering depth.",
            "Keep private runtime bindings and credentials out of portable project records. Existing project-specific requirements still apply.",
        ],
        "title": "Commander project record",
        "status": "Record initialized; no accepted deliverable is recorded yet.",
        "goal": "Goal",
        "depth": "Delivery agreement",
        "level": "Engineering depth",
        "levels": {"prototype": "Prototype", "maintainable": "Maintainable", "production": "Production"},
        "language_label": "Conversation and document language",
        "language": "English, unless the user specifies otherwise for an artifact",
        "scope": "Scope and non-goals",
        "scope_text": "Record the confirmed boundaries here before dispatch; future suggestions are not approved requirements.",
        "acceptance": "Acceptance criteria",
        "acceptance_text": "Not recorded yet. Add observable checks for the agreed goal; a worker's completion claim is not acceptance.",
        "team": "Ownership and dependencies",
        "team_text": "No team creation is recorded. Choose solo work, reuse, or an explicitly authorized minimal team. List real owners, inputs, and dependencies as they become known.",
        "decisions": "Decisions and evidence",
        "decisions_text": "Record material decisions and accepted artifact versions with the checks actually performed. Do not copy full conversations or private runtime IDs here.",
        "next": "Current state and next step",
        "next_text": "Complete this record from the confirmed agreement, then take only the next authorized step.",
        "existing": "Existing docs/commander.md preserved. Reconcile the current goal, level, and language manually if needed.",
    },
    "zh-CN": {
        "rules_title": "Codex Commander 协作约定",
        "rules": [
            "执行总指挥工作流时，先读取 `docs/commander.md` 中的当前约定；这些规则本身不会启动团队。",
            "对话与新增文档跟随用户语言；保留用户对特定产物另行指定的语言。",
            "项目团队的任务归属已核实的目标项目，默认保留项目下的侧边栏显示；只有用户明确要求时才创建或使用自定义分区。委派新总指挥时也须传递此归属约定。",
            "共享计划记录由总指挥维护。执行者只处理分配的产物，保留其他人的修改，并向已核实的总指挥地址回报完成情况或真实阻塞。",
            "核查实际产物和相关证据后才能验收；不得自行扩大已约定的范围或工程化程度。",
            "可共享的项目记录不包含私有运行时标识或凭据；原有项目专属要求继续适用。",
        ],
        "title": "总指挥项目记录",
        "status": "记录已初始化；尚未记录任何已验收产物。",
        "goal": "目标",
        "depth": "交付约定",
        "level": "工程化档位",
        "levels": {"prototype": "轻量验证", "maintainable": "实用维护", "production": "正式交付"},
        "language_label": "对话与文档语言",
        "language": "简体中文；用户对特定产物另有指定时，以该指定为准",
        "scope": "范围与非目标",
        "scope_text": "派单前在此记录已确认的边界；未来建议不等于已批准需求。",
        "acceptance": "验收条件",
        "acceptance_text": "尚未记录。应为当前目标补充可观察的检查条件；执行者自报完成不等于验收通过。",
        "team": "责任与依赖",
        "team_text": "尚未记录已创建团队。根据实际工作选择单独执行、复用或明确授权的最小团队，并记录真实责任人、输入和依赖。",
        "decisions": "决策与证据",
        "decisions_text": "记录重要取舍、已验收产物版本以及实际执行的检查；不在此复制完整聊天或私有运行时标识。",
        "next": "当前状态与下一步",
        "next_text": "依据已确认的约定补充本记录，然后只执行下一项已获授权的工作。",
        "existing": "已保留现有 docs/commander.md；如有需要，请在授权范围内手动对齐当前目标、档位和语言。",
    },
    "zh-TW": {
        "rules_title": "Codex Commander 協作約定",
        "rules": [
            "執行總指揮工作流程時，先讀取 `docs/commander.md` 中的目前約定；這些規則本身不會啟動團隊。",
            "對話與新增文件跟隨使用者語言；保留使用者對特定產物另行指定的語言。",
            "專案團隊的任務歸屬已核實的目標專案，預設保留專案下的側邊欄顯示；只有使用者明確要求時才建立或使用自訂分區。委派新總指揮時也須傳遞此歸屬約定。",
            "共用計畫記錄由總指揮維護。執行者只處理分配的產物，保留其他人的修改，並向已核實的總指揮位址回報完成情況或實際阻礙。",
            "核查實際產物和相關證據後才能驗收；不得自行擴大已約定的範圍或工程化程度。",
            "可分享的專案記錄不包含私有執行階段識別碼或憑證；原有專案專屬要求繼續適用。",
        ],
        "title": "總指揮專案記錄",
        "status": "記錄已初始化；尚未記錄任何已驗收產物。",
        "goal": "目標",
        "depth": "交付約定",
        "level": "工程化層級",
        "levels": {"prototype": "輕量驗證", "maintainable": "實用維護", "production": "正式交付"},
        "language_label": "對話與文件語言",
        "language": "繁體中文；使用者對特定產物另有指定時，以該指定為準",
        "scope": "範圍與非目標",
        "scope_text": "派單前在此記錄已確認的邊界；未來建議不等於已核准需求。",
        "acceptance": "驗收條件",
        "acceptance_text": "尚未記錄。應為目前目標補充可觀察的檢查條件；執行者自報完成不等於驗收通過。",
        "team": "責任與相依性",
        "team_text": "尚未記錄已建立團隊。根據實際工作選擇單獨執行、重用或明確授權的最小團隊，並記錄實際負責人、輸入和相依性。",
        "decisions": "決策與證據",
        "decisions_text": "記錄重要取捨、已驗收產物版本以及實際執行的檢查；不在此複製完整聊天或私有執行階段識別碼。",
        "next": "目前狀態與下一步",
        "next_text": "依據已確認的約定補充本記錄，然後只執行下一項已獲授權的工作。",
        "existing": "已保留現有 docs/commander.md；如有需要，請在授權範圍內手動對齊目前目標、層級和語言。",
    },
}


class RecordError(Exception):
    """A refused or incomplete operation, with no claim of success."""


@dataclass(frozen=True)
class Change:
    path: Path
    before: bytes | None
    after: bytes

    @property
    def action(self) -> str:
        if self.before is None:
            return "create"
        return "unchanged" if self.before == self.after else "update"


@dataclass(frozen=True)
class RootIdentity:
    st_dev: int
    st_ino: int


@dataclass(frozen=True)
class Plan:
    root: Path
    changes: tuple[Change, ...]
    warnings: tuple[str, ...]
    root_identity: RootIdentity


def root_identity(path: Path) -> RootIdentity:
    try:
        status = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        raise RecordError(f"Could not verify project root identity: {path}") from exc
    if not stat.S_ISDIR(status.st_mode):
        raise RecordError(f"Project root changed while verifying its identity: {path}")
    return RootIdentity(status.st_dev, status.st_ino)


def checked_root(value: str | Path) -> Path:
    supplied = Path(value).expanduser()
    if not supplied.is_absolute():
        raise RecordError("Use an explicit absolute project root.")
    if supplied.is_symlink():
        raise RecordError("Resolve and confirm the real project root instead of a symlink.")
    if not supplied.is_dir():
        raise RecordError("The project root must be an existing directory.")
    root = supplied.resolve()
    home = Path.home().resolve()
    protected = {Path(root.anchor), home, home / ".codex", home / ".agents", Path(__file__).resolve().parents[1]}
    configured_home = os.environ.get("CODEX_HOME")
    if configured_home:
        protected.add(Path(configured_home).expanduser().resolve())
    if root in protected:
        raise RecordError("Refusing a filesystem, home, configuration, or skill root.")
    override = root / "AGENTS.override.md"
    if override.exists() or override.is_symlink():
        raise RecordError("AGENTS.override.md exists; integrate with the effective instructions manually.")
    return root


def check_target(root: Path, path: Path) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise RecordError("Output must stay inside the confirmed project root.") from exc
    current = root
    for index, part in enumerate(relative.parts):
        current = current / part
        if current.is_symlink():
            raise RecordError(f"Refusing symlinked output: {current}")
        if current.exists():
            is_last = index == len(relative.parts) - 1
            if is_last and not current.is_file():
                raise RecordError(f"Output is not a regular file: {current}")
            if not is_last and not current.is_dir():
                raise RecordError(f"Output parent is not a directory: {current}")


def read_optional(root: Path, path: Path) -> bytes | None:
    check_target(root, path)
    return path.read_bytes() if path.exists() else None


def managed_block(language: str) -> str:
    words = TEXT[language]
    bullets = "\n".join(f"- {rule}" for rule in words["rules"])
    return f"{BEGIN}\n## {words['rules_title']}\n\n{bullets}\n{END}"


def merge_agents(original: bytes | None, language: str) -> bytes:
    try:
        text = (original or b"").decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RecordError("Existing AGENTS.md is not UTF-8; preserve it and integrate manually.") from exc
    begin_count, end_count = text.count(BEGIN), text.count(END)
    block = managed_block(language)
    if begin_count == 0 and end_count == 0:
        separator = "" if not text else ("\n" if text.endswith("\n") else "\n\n")
        return (text + separator + block + "\n").encode("utf-8")
    if begin_count != 1 or end_count != 1:
        raise RecordError("Duplicate or incomplete Codex Commander markers; refusing to guess.")
    start, end = text.index(BEGIN), text.index(END)
    if end < start or BEGIN not in text.splitlines() or END not in text.splitlines():
        raise RecordError("Malformed Codex Commander marker boundaries.")
    return (text[:start] + block + text[end + len(END):]).encode("utf-8")


def new_record(language: str, level: str, goal: str) -> bytes:
    words = TEXT[language]
    colon = ": " if language == "en" else "："
    sections = [
        f"# {words['title']}\n\n{words['status']}",
        f"## {words['goal']}\n\n{goal}",
        f"## {words['depth']}\n\n- {words['level']}{colon}{words['levels'][level]}\n- {words['language_label']}{colon}{words['language']}",
    ]
    for key in ("scope", "acceptance", "team", "decisions", "next"):
        sections.append(f"## {words[key]}\n\n{words[key + '_text']}")
    return ("\n\n".join(sections) + "\n").encode("utf-8")


def plan_records(root_value: str | Path, language: str, level: str, goal: str) -> Plan:
    if language not in TEXT:
        raise RecordError("Unsupported language; create equivalent localized records manually.")
    if level not in LEVELS:
        raise RecordError("Unknown engineering level.")
    if not goal.strip() or "\x00" in goal:
        raise RecordError("Supply a nonempty goal without NUL characters.")
    root = checked_root(root_value)
    identity = root_identity(root)
    agents_path, record_path = root / "AGENTS.md", root / "docs" / "commander.md"
    old_agents = read_optional(root, agents_path)
    old_record = read_optional(root, record_path)
    agents = Change(agents_path, old_agents, merge_agents(old_agents, language))
    record = Change(record_path, old_record, old_record if old_record is not None else new_record(language, level, goal.strip()))
    warnings = (TEXT[language]["existing"],) if old_record is not None else ()
    if root_identity(root) != identity:
        raise RecordError("Project root changed while planning; inspect and retry.")
    return Plan(root, (record, agents), warnings, identity)


def assert_unchanged(root: Path, change: Change) -> None:
    current = read_optional(root, change.path)
    if current != change.before:
        raise RecordError(f"File changed since preview; inspect and replan: {change.path}")


def anchored_writes_supported() -> bool:
    return ANCHORED_WRITES_SUPPORTED


ANCHORED_WRITES_SUPPORTED = (
    fcntl is not None
    and hasattr(os, "O_DIRECTORY")
    and hasattr(os, "O_NOFOLLOW")
    and all(
        function in os.supports_dir_fd
        for function in (os.open, os.stat, os.unlink, os.mkdir, os.link, os.rename)
    )
)


def assert_root_identity(root: Path, descriptor: int, expected: RootIdentity | None = None) -> None:
    visible = root_identity(root)
    opened_status = os.fstat(descriptor)
    opened = RootIdentity(opened_status.st_dev, opened_status.st_ino)
    if visible != opened:
        raise RecordError("Project root changed while opening it; inspect and retry.")
    if expected is not None and opened != expected:
        raise RecordError("Project root identity changed since preview; inspect and replan.")


@contextmanager
def open_root_directory(root: Path, expected: RootIdentity | None = None):
    if not anchored_writes_supported():
        raise RecordError(
            "Apply requires directory-relative filesystem operations available on macOS/Linux; "
            "preview remains available on this platform."
        )
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open(root, flags)
    try:
        assert_root_identity(root, descriptor, expected)
        yield descriptor
    finally:
        os.close(descriptor)


@contextmanager
def open_parent_directory(
    root_fd: int,
    root: Path,
    path: Path,
    create: bool,
    created: list[tuple[Path, tuple[int, int]]] | None = None,
):
    relative = path.relative_to(root)
    descriptor = os.dup(root_fd)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    current = root
    try:
        for part in relative.parts[:-1]:
            current = current / part
            try:
                child = os.open(part, flags, dir_fd=descriptor)
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(part, 0o777, dir_fd=descriptor)
                os.fsync(descriptor)
                child = os.open(part, flags, dir_fd=descriptor)
                if created is not None:
                    identity = os.fstat(child)
                    created.append((current, (identity.st_dev, identity.st_ino)))
            os.close(descriptor)
            descriptor = child
        yield descriptor, relative.name
    finally:
        os.close(descriptor)


def assert_directory_identity(path: Path, descriptor: int) -> None:
    try:
        visible = os.stat(path, follow_symlinks=False)
    except FileNotFoundError as exc:
        raise RecordError(f"Output parent changed during apply: {path}") from exc
    opened = os.fstat(descriptor)
    if not stat.S_ISDIR(visible.st_mode) or (visible.st_dev, visible.st_ino) != (
        opened.st_dev,
        opened.st_ino,
    ):
        raise RecordError(f"Output parent changed during apply: {path}")


def read_optional_at(parent_fd: int, name: str) -> bytes | None:
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
    except FileNotFoundError:
        return None
    with os.fdopen(descriptor, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise RecordError(f"Output is not a regular file: {name}")
        return handle.read()


def assert_unchanged_at(parent_fd: int, change: Change, name: str) -> None:
    if read_optional_at(parent_fd, name) != change.before:
        raise RecordError(f"File changed since preview; inspect and replan: {change.path}")


@contextmanager
def exclusive_apply(root_fd: int, root: Path):
    """Serialize helper writers with a kernel lock on the opened root directory."""
    try:
        fcntl.flock(root_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        if exc.errno not in (errno.EACCES, errno.EAGAIN):
            raise
        raise RecordError(f"Another apply may be running for {root}; inspect and retry.") from exc
    try:
        yield
    finally:
        fcntl.flock(root_fd, fcntl.LOCK_UN)


def temporary_name(path: Path, content: bytes, created_ns: int | None = None) -> str:
    """Name a private carrier so a later run can bind it to one exact change."""
    path_digest = hashlib.sha256(os.fsencode(path)).hexdigest()
    content_digest = hashlib.sha256(content).hexdigest()
    timestamp = time.time_ns() if created_ns is None else created_ns
    return f".commander-v1-{path_digest}-{content_digest}-{timestamp}-{uuid.uuid4().hex}"


def write_temporary(parent_fd: int, path: Path, content: bytes, mode: int | None) -> str:
    for _ in range(100):
        temporary = temporary_name(path, content)
        try:
            if mode is None:
                # Capture the caller's normal file mode while forcing this carrier
                # private until all content has been handed to the file object.
                with _UMASK_LOCK:
                    # umask is process-wide, so its set/restore pair must not
                    # interleave across independent project-root writers.
                    previous_umask = os.umask(0o077)
                    try:
                        descriptor = os.open(
                            temporary,
                            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                            0o666,
                            dir_fd=parent_fd,
                        )
                    finally:
                        os.umask(previous_umask)
                final_mode = 0o666 & ~previous_umask
            else:
                descriptor = os.open(
                    temporary,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    mode,
                    dir_fd=parent_fd,
                )
                final_mode = mode
        except FileExistsError:
            continue
        break
    else:  # pragma: no cover - requires repeated UUID collisions or hostile creation
        raise RecordError(f"Could not reserve a temporary file beside {path}.")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fchmod(handle.fileno(), final_mode)
            os.fsync(handle.fileno())
        os.fsync(parent_fd)
    except BaseException:
        try:
            os.unlink(temporary, dir_fd=parent_fd)
            os.fsync(parent_fd)
        except FileNotFoundError:
            pass
        raise
    return temporary


def _same_file(first: os.stat_result, second: os.stat_result) -> bool:
    fields = (
        "st_dev", "st_ino", "st_mode", "st_uid", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns",
    )
    return all(getattr(first, field, None) == getattr(second, field, None) for field in fields)


def cleanup_stale_temporaries(root_fd: int, root: Path, plan: Plan, cutoff_ns: int) -> list[str]:
    """Remove only carriers whose name, metadata, and bytes prove a current-plan origin."""
    expected = {
        (
            hashlib.sha256(os.fsencode(change.path)).hexdigest(),
            hashlib.sha256(change.after).hexdigest(),
        ): change.after
        for change in plan.changes
    }
    removed: list[str] = []
    assert_directory_identity(root, root_fd)
    for name in os.listdir(root_fd):
        match = _TEMPORARY_PATTERN.fullmatch(name)
        if match is None:
            continue
        content = expected.get((match.group(1), match.group(2)))
        if content is None:
            continue
        try:
            created_ns = int(match.group(3))
        except ValueError:  # pragma: no cover - excluded by the bounded regex
            continue
        identifier = uuid.UUID(hex=match.group(4))
        if identifier.version != 4 or identifier.variant != uuid.RFC_4122:
            continue
        if created_ns <= 0 or created_ns >= cutoff_ns:
            continue
        try:
            visible = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
        except FileNotFoundError:
            continue
        if not stat.S_ISREG(visible.st_mode):
            continue
        if visible.st_uid != os.geteuid() or visible.st_nlink != 1:
            continue
        if visible.st_mode & (stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX):
            continue
        if visible.st_size > len(content):
            continue
        # ``created_ns`` and the cutoff both come from this process's wall
        # clock.  Filesystem mtime/ctime can use a different clock or a
        # coarser precision, so they cannot safely corroborate that value.
        # The carrier's exact current-plan path/content identity, private
        # shape, and bounded prefix are the evidence for cleanup; time only
        # rejects a carrier whose own name does not predate this apply.
        try:
            descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=root_fd)
        except (FileNotFoundError, OSError):
            continue
        try:
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode) or not _same_file(visible, opened):
                continue
            chunks: list[bytes] = []
            remaining = len(content) + 1
            while remaining:
                chunk = os.read(descriptor, min(65536, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            carried = b"".join(chunks)
            after_read = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        if not _same_file(opened, after_read):
            continue
        if carried != content[:len(carried)] or len(carried) != opened.st_size:
            continue
        try:
            current = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
        except FileNotFoundError:
            continue
        if not _same_file(opened, current):
            continue
        os.unlink(name, dir_fd=root_fd)
        removed.append(name)
    if removed:
        os.fsync(root_fd)
    assert_directory_identity(root, root_fd)
    return removed


def cleanup_created_directories(
    root_fd: int,
    root: Path,
    created: list[tuple[Path, tuple[int, int]]],
) -> None:
    """Best-effort rollback for empty parents created by this process invocation."""
    for path, identity in reversed(created):
        try:
            with open_parent_directory(root_fd, root, path, create=False) as (parent_fd, name):
                visible = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
                if not stat.S_ISDIR(visible.st_mode) or (visible.st_dev, visible.st_ino) != identity:
                    continue
                os.rmdir(name, dir_fd=parent_fd)
                os.fsync(parent_fd)
        except (FileNotFoundError, NotADirectoryError, OSError):
            # A nonempty, replaced, or otherwise uncertain directory is not ours to remove.
            continue


def write_change(root_fd: int, root: Path, change: Change) -> None:
    check_target(root, change.path)
    mode = None
    try:
        with open_parent_directory(root_fd, root, change.path, create=False) as (parent_fd, name):
            assert_directory_identity(change.path.parent, parent_fd)
            assert_unchanged_at(parent_fd, change, name)
            if change.before is not None:
                mode = stat.S_IMODE(os.stat(name, dir_fd=parent_fd, follow_symlinks=False).st_mode)
    except FileNotFoundError:
        if change.before is not None:
            raise RecordError(f"Output parent changed during apply: {change.path.parent}")

    # Build and sync the carrier in the already-opened project root. A missing
    # docs parent is created only after the complete carrier is durable.
    temporary = write_temporary(root_fd, change.path, change.after, mode)
    created: list[tuple[Path, tuple[int, int]]] = []
    try:
        with open_parent_directory(root_fd, root, change.path, create=True, created=created) as (parent_fd, name):
            assert_directory_identity(change.path.parent, parent_fd)
            assert_unchanged_at(parent_fd, change, name)
            if change.before is None:
                os.link(
                    temporary,
                    name,
                    src_dir_fd=root_fd,
                    dst_dir_fd=parent_fd,
                    follow_symlinks=False,
                )
                os.fsync(parent_fd)
                os.unlink(temporary, dir_fd=root_fd)
                temporary = None
                os.fsync(root_fd)
            else:
                os.rename(temporary, name, src_dir_fd=root_fd, dst_dir_fd=parent_fd)
                temporary = None
                os.fsync(parent_fd)
                if change.path.parent != root:
                    os.fsync(root_fd)
            assert_directory_identity(change.path.parent, parent_fd)
    except BaseException:
        cleanup_created_directories(root_fd, root, created)
        raise
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary, dir_fd=root_fd)
                os.fsync(root_fd)
            except FileNotFoundError:
                pass


def apply_plan(plan: Plan) -> list[str]:
    written: list[str] = []
    try:
        if checked_root(plan.root) != plan.root:
            raise RecordError("Project identity changed since preview.")
        with open_root_directory(plan.root, plan.root_identity) as root_fd:
            with exclusive_apply(root_fd, plan.root):
                for change in plan.changes:
                    assert_unchanged(plan.root, change)
                assert_root_identity(plan.root, root_fd, plan.root_identity)
                cleanup_stale_temporaries(root_fd, plan.root, plan, time.time_ns())
                for change in plan.changes:
                    if change.action != "unchanged":
                        write_change(root_fd, plan.root, change)
                        written.append(str(change.path.relative_to(plan.root)))
    except (OSError, RecordError) as exc:
        detail = ", ".join(written) if written else "none confirmed"
        raise RecordError(f"Apply did not finish: {exc}. Files written before failure: {detail}. Inspect before retrying.") from exc
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Explicit existing absolute project root")
    parser.add_argument("--language", required=True, choices=tuple(TEXT))
    parser.add_argument("--level", required=True, choices=LEVELS)
    parser.add_argument("--goal", required=True)
    parser.add_argument("--apply", action="store_true", help="Write the previewed scaffold; default is read-only")
    args = parser.parse_args(argv)
    try:
        plan = plan_records(args.root, args.language, args.level, args.goal)
        written = apply_plan(plan) if args.apply else []
        print(json.dumps({
            "mode": "applied" if args.apply else "preview",
            "root": str(plan.root),
            "language": args.language,
            "changes": [{"path": str(item.path.relative_to(plan.root)), "action": item.action, "bytes": len(item.after)} for item in plan.changes],
            "written": written,
            "warnings": list(plan.warnings),
        }, ensure_ascii=False, indent=2))
        return 0
    except (RecordError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
