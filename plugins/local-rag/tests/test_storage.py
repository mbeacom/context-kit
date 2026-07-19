import pytest

from local_rag.storage import (
    IndexBusyError,
    IndexLock,
    IndexRemovalError,
    ensure_index_dir,
    index_dir,
    list_indexes,
    remove_index,
    validate_index_name,
)


@pytest.mark.parametrize(
    "name",
    [
        "default",
        "notes",
        "Notes-2026",
        "team_notes.v2",
        "team notes",
        ".hidden",
        "notes..old",
        "n" * 120,
    ],
)
def test_validate_index_name_accepts_portable_names(name):
    assert validate_index_name(name) == name


@pytest.mark.parametrize(
    "name",
    [
        "",
        ".",
        "..",
        "../notes",
        "notes/other",
        r"notes\other",
        "bad\x00name",
    ],
)
def test_validate_index_name_rejects_unsafe_names(name):
    with pytest.raises(ValueError, match="index name must"):
        validate_index_name(name)


def test_remove_index_deletes_only_flat_owned_artifacts(tmp_path):
    indexes = tmp_path / "indexes"
    target = indexes / "notes"
    sibling = indexes / "keep"
    target.mkdir(parents=True)
    sibling.mkdir()
    for filename in ["meta.sqlite", "meta.sqlite-wal", "meta.sqlite-shm", "index.tvim"]:
        (target / filename).write_text(filename)
    (sibling / "meta.sqlite").write_text("keep")

    removed = remove_index(tmp_path, "notes")

    assert removed == 4
    assert not target.exists()
    assert (sibling / "meta.sqlite").read_text() == "keep"


def test_remove_index_unlinks_symlink_without_following_it(tmp_path):
    target = index_dir(tmp_path, "notes")
    target.mkdir(parents=True)
    (target / "meta.sqlite").write_text("metadata")
    outside = tmp_path / "outside.txt"
    outside.write_text("preserve")
    (target / "artifact-link").symlink_to(outside)

    assert remove_index(tmp_path, "notes") == 2
    assert outside.read_text() == "preserve"


def test_remove_index_falls_back_for_windows_directory_symlink(
    tmp_path,
    monkeypatch,
):
    target = index_dir(tmp_path, "notes")
    target.mkdir(parents=True)
    (target / "meta.sqlite").write_text("metadata")
    outside = tmp_path / "outside"
    outside.mkdir()
    link = target / "artifact-link"
    link.symlink_to(outside, target_is_directory=True)
    original_unlink = type(link).unlink
    original_rmdir = type(link).rmdir

    def windows_unlink(path, *args, **kwargs):
        if path.name == "artifact-link":
            raise PermissionError("directory symlink")
        return original_unlink(path, *args, **kwargs)

    def windows_rmdir(path, *args, **kwargs):
        if path.name == "artifact-link":
            return original_unlink(path)
        return original_rmdir(path, *args, **kwargs)

    monkeypatch.setattr(type(link), "unlink", windows_unlink)
    monkeypatch.setattr(type(link), "rmdir", windows_rmdir)

    assert remove_index(tmp_path, "notes") == 2
    assert outside.is_dir()


@pytest.mark.parametrize("filename", ["meta.sqlite", "index.tvim"])
def test_ensure_index_dir_rejects_owned_artifact_symlinks(tmp_path, filename):
    target = index_dir(tmp_path, "notes")
    target.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.write_text("preserve")
    (target / filename).symlink_to(outside)

    with pytest.raises(RuntimeError, match=f"unsafe '{filename}'"):
        ensure_index_dir(tmp_path, "notes")

    assert outside.read_text() == "preserve"


def test_remove_index_refuses_while_index_is_locked(tmp_path):
    target = index_dir(tmp_path, "notes")
    target.mkdir(parents=True)
    (target / "meta.sqlite").write_text("metadata")

    with IndexLock(tmp_path, "notes"):
        with pytest.raises(IndexBusyError, match="in use"):
            remove_index(tmp_path, "notes")

    assert remove_index(tmp_path, "notes") == 1
    assert not target.exists()


def test_remove_index_refuses_nested_directories_without_partial_cleanup(tmp_path):
    target = index_dir(tmp_path, "notes")
    target.mkdir(parents=True)
    (target / "meta.sqlite").write_text("metadata")
    (target / "unexpected").mkdir()

    with pytest.raises(RuntimeError, match="unexpected nested directories"):
        remove_index(tmp_path, "notes")

    assert (target / "meta.sqlite").exists()
    assert (target / "unexpected").is_dir()


def test_remove_index_reports_partial_cleanup_location(tmp_path, monkeypatch):
    target = index_dir(tmp_path, "notes")
    target.mkdir(parents=True)
    first = target / "a"
    second = target / "b"
    first.write_text("a")
    second.write_text("b")
    original_unlink = type(first).unlink

    def fail_second(path, *args, **kwargs):
        if path.name == "b":
            raise PermissionError("blocked")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(type(first), "unlink", fail_second)

    with pytest.raises(IndexRemovalError, match="remaining artifacts are at"):
        remove_index(tmp_path, "notes")

    assert not target.exists()
    quarantine = list((tmp_path / "indexes").glob(".notes.deleting-*"))
    assert len(quarantine) == 1
    assert (quarantine[0] / "b").exists()


def test_list_indexes_ignores_only_generated_quarantine_entries(tmp_path):
    indexes = tmp_path / "indexes"
    (indexes / "notes").mkdir(parents=True)
    (indexes / "corrupt").mkdir()
    (indexes / f".notes.deleting-{'d' * 32}").mkdir()
    (indexes / ".project.deleting-manual").mkdir()
    (indexes / "not an index").mkdir()

    assert list_indexes(tmp_path) == [
        ".project.deleting-manual",
        "corrupt",
        "not an index",
        "notes",
    ]
