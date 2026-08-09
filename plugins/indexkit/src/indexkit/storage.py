from __future__ import annotations

from contextlib import ExitStack
import errno
import hashlib
import os
import stat
import uuid
from pathlib import Path
from typing import BinaryIO

OWNED_ARTIFACT_NAMES = (
    "meta.sqlite",
    "meta.sqlite-wal",
    "meta.sqlite-shm",
    "meta.sqlite-journal",
    "index.tvim",
)


class IndexRemovalError(RuntimeError):
    """Raised when an index leaves the active namespace but cleanup is incomplete."""


class IndexBusyError(RuntimeError):
    """Raised when another process owns the named index lock."""


def validate_index_name(name: str) -> str:
    if not name or name in {".", ".."} or "\x00" in name or "/" in name or "\\" in name:
        raise ValueError(
            "index name must be one non-empty path component other than '.' or '..' "
            "and cannot contain '/', '\\', or NUL"
        )
    return name


def indexes_dir(data_dir) -> Path:
    return Path(data_dir) / "indexes"


def index_dir(data_dir, name: str) -> Path:
    return indexes_dir(data_dir) / validate_index_name(name)


def _validate_owned_artifacts(directory: Path, name: str) -> None:
    for filename in OWNED_ARTIFACT_NAMES:
        artifact = directory / filename
        if artifact.is_symlink() or (artifact.exists() and not artifact.is_file()):
            raise RuntimeError(f"index '{name}' has an unsafe '{filename}' storage entry")


def ensure_index_dir(data_dir, name: str) -> Path:
    directory = index_dir(data_dir, name)
    if directory.is_symlink():
        raise RuntimeError(f"index '{name}' has an unsafe storage entry")
    directory.mkdir(parents=True, exist_ok=True)
    if not directory.is_dir():
        raise RuntimeError(f"index '{name}' storage entry is not a directory")
    _validate_owned_artifacts(directory, name)
    return directory


def existing_index_dir(data_dir, name: str) -> Path:
    directory = index_dir(data_dir, name)
    if not directory.exists():
        raise FileNotFoundError(f"no index named '{name}'")
    if directory.is_symlink() or not directory.is_dir():
        raise RuntimeError(f"index '{name}' has an unsafe storage entry")
    _validate_owned_artifacts(directory, name)
    if not (directory / "meta.sqlite").is_file():
        raise FileNotFoundError(f"no index named '{name}'")
    return directory


class IndexLock:
    def __init__(self, data_dir, name: str) -> None:
        self.name = validate_index_name(name)
        digest = hashlib.sha256(self.name.encode("utf-8")).hexdigest()
        lock_dir = Path(data_dir) / ".index-locks"
        if lock_dir.is_symlink():
            raise RuntimeError("index lock storage has an unsafe entry")
        lock_dir.mkdir(parents=True, exist_ok=True)
        if lock_dir.is_symlink() or not lock_dir.is_dir():
            raise RuntimeError("index lock storage is not a directory")
        self.path = lock_dir / f"{digest}.lock"
        if self.path.is_symlink():
            raise RuntimeError(f"index '{name}' has an unsafe lock entry")
        self._handle: BinaryIO | None = None

    def acquire(self) -> None:
        if self._handle is not None:
            raise RuntimeError(f"index '{self.name}' lock is already acquired")
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(self.path, flags, 0o600)
        handle = os.fdopen(descriptor, "r+b", buffering=0)
        with ExitStack() as cleanup:
            cleanup.callback(handle.close)
            if os.name == "nt":
                import msvcrt

                handle.seek(0, os.SEEK_END)
                if handle.tell() == 0:
                    handle.write(b"\0")
                handle.seek(0)
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError as error:
                    raise IndexBusyError(f"index '{self.name}' is in use") from error
            else:
                import fcntl

                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError as error:
                    if error.errno not in {errno.EACCES, errno.EAGAIN}:
                        raise
                    raise IndexBusyError(f"index '{self.name}' is in use") from error
            self._handle = handle
            cleanup.pop_all()

    def release(self) -> None:
        handle = self._handle
        if handle is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._handle = None
            handle.close()

    def __enter__(self) -> "IndexLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.release()


def list_indexes(data_dir) -> list[str]:
    base = indexes_dir(data_dir)
    if not base.exists():
        return []
    names: list[str] = []
    for entry in base.iterdir():
        prefix, marker, suffix = entry.name.rpartition(".deleting-")
        if (
            marker
            and prefix.startswith(".")
            and len(suffix) == 32
            and all(character in "0123456789abcdef" for character in suffix)
        ):
            continue
        try:
            validate_index_name(entry.name)
        except ValueError:
            continue
        if entry.is_dir() and not entry.is_symlink():
            names.append(entry.name)
    return sorted(names)


def remove_index(data_dir, name: str) -> int:
    """Atomically hide and then delete one flat, per-index artifact directory."""
    with IndexLock(data_dir, name):
        return _remove_index_locked(data_dir, name)


def _is_directory_link(artifact: Path) -> bool:
    if artifact.is_symlink():
        return artifact.is_dir()
    is_junction = getattr(artifact, "is_junction", None)
    if is_junction is not None and is_junction():
        return True
    if os.name != "nt":
        return False
    attributes = getattr(artifact.lstat(), "st_file_attributes", 0)
    reparse_point = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return artifact.is_dir() and bool(attributes & reparse_point)


def _unlink_artifact(artifact: Path) -> None:
    try:
        artifact.unlink()
    except OSError:
        if not _is_directory_link(artifact):
            raise
        artifact.rmdir()


def _remove_index_locked(data_dir, name: str) -> int:
    directory = index_dir(data_dir, name)
    if not directory.exists():
        raise FileNotFoundError(f"no index named '{name}'")
    if directory.is_symlink() or not directory.is_dir():
        raise RuntimeError(f"index '{name}' has an unsafe storage entry")

    children = list(directory.iterdir())
    nested = [child.name for child in children if child.is_dir() and not _is_directory_link(child)]
    if nested:
        raise RuntimeError(
            f"index '{name}' contains unexpected nested directories; no artifacts were removed"
        )

    quarantine = indexes_dir(data_dir) / f".{name}.deleting-{uuid.uuid4().hex}"
    os.replace(directory, quarantine)

    try:
        children = list(quarantine.iterdir())
    except OSError as error:
        raise IndexRemovalError(
            f"index '{name}' was removed from the active namespace, but its artifacts "
            f"could not be inspected at '{quarantine}': {error}"
        ) from error
    nested = [child.name for child in children if child.is_dir() and not _is_directory_link(child)]
    if nested:
        raise IndexRemovalError(
            f"index '{name}' changed during removal; artifacts remain at '{quarantine}'"
        )

    removed = 0
    try:
        for child in children:
            _unlink_artifact(child)
            removed += 1
        quarantine.rmdir()
    except OSError as error:
        raise IndexRemovalError(
            f"index '{name}' was removed from the active namespace, but cleanup failed "
            f"after deleting {removed} artifact(s); remaining artifacts are at "
            f"'{quarantine}': {error}"
        ) from error
    return removed
