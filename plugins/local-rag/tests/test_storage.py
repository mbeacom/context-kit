import pytest

from local_rag.storage import (
    IndexRemovalError,
    index_dir,
    list_indexes,
    remove_index,
    validate_index_name,
)


@pytest.mark.parametrize("name", ["default", "notes", "Notes-2026", "team_notes.v2"])
def test_validate_index_name_accepts_portable_names(name):
    assert validate_index_name(name) == name


@pytest.mark.parametrize(
    "name",
    [
        "",
        ".",
        "..",
        ".hidden",
        "../notes",
        "notes/other",
        r"notes\other",
        "notes..old",
        "bad name",
        "n" * 81,
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


def test_list_indexes_ignores_quarantine_and_unsafe_entries(tmp_path):
    indexes = tmp_path / "indexes"
    (indexes / "notes").mkdir(parents=True)
    (indexes / "corrupt").mkdir()
    (indexes / ".notes.deleting-deadbeef").mkdir()
    (indexes / "not an index").mkdir()

    assert list_indexes(tmp_path) == ["corrupt", "notes"]
