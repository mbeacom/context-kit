from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

INDEX_NAME_MAX_LENGTH = 80
_INDEX_NAME_RE = re.compile(rf"[A-Za-z0-9][A-Za-z0-9._-]{{0,{INDEX_NAME_MAX_LENGTH - 1}}}\Z")


class IndexRemovalError(RuntimeError):
    """Raised when an index leaves the active namespace but cleanup is incomplete."""


def validate_index_name(name: str) -> str:
    if not _INDEX_NAME_RE.fullmatch(name) or ".." in name:
        raise ValueError(
            "index name must be 1-80 characters, start with a letter or digit, "
            "contain only letters, digits, '.', '_', or '-', and not contain '..'"
        )
    return name


def indexes_dir(data_dir) -> Path:
    return Path(data_dir) / "indexes"


def index_dir(data_dir, name: str) -> Path:
    return indexes_dir(data_dir) / validate_index_name(name)


def index_exists(data_dir, name: str) -> bool:
    directory = index_dir(data_dir, name)
    metadata = directory / "meta.sqlite"
    return (
        directory.is_dir()
        and not directory.is_symlink()
        and metadata.is_file()
        and not metadata.is_symlink()
    )


def ensure_index_dir(data_dir, name: str) -> Path:
    directory = index_dir(data_dir, name)
    if directory.is_symlink():
        raise RuntimeError(f"index '{name}' has an unsafe storage entry")
    directory.mkdir(parents=True, exist_ok=True)
    if not directory.is_dir():
        raise RuntimeError(f"index '{name}' storage entry is not a directory")
    return directory


def list_indexes(data_dir) -> list[str]:
    base = indexes_dir(data_dir)
    if not base.exists():
        return []
    names: list[str] = []
    for entry in base.iterdir():
        try:
            validate_index_name(entry.name)
        except ValueError:
            continue
        if entry.is_dir() and not entry.is_symlink():
            names.append(entry.name)
    return sorted(names)


def remove_index(data_dir, name: str) -> int:
    """Atomically hide and then delete one flat, per-index artifact directory."""
    directory = index_dir(data_dir, name)
    if not directory.exists():
        raise FileNotFoundError(f"no index named '{name}'")
    if directory.is_symlink() or not directory.is_dir():
        raise RuntimeError(f"index '{name}' has an unsafe storage entry")

    children = list(directory.iterdir())
    nested = [child.name for child in children if child.is_dir() and not child.is_symlink()]
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
    nested = [child.name for child in children if child.is_dir() and not child.is_symlink()]
    if nested:
        raise IndexRemovalError(
            f"index '{name}' changed during removal; artifacts remain at '{quarantine}'"
        )

    removed = 0
    try:
        for child in children:
            child.unlink()
            removed += 1
        quarantine.rmdir()
    except OSError as error:
        raise IndexRemovalError(
            f"index '{name}' was removed from the active namespace, but cleanup failed "
            f"after deleting {removed} artifact(s); remaining artifacts are at "
            f"'{quarantine}': {error}"
        ) from error
    return removed
