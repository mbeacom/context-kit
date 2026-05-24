import os

from local_rag.loaders.markdown import iter_corpus, load_markdown

DOC = """\
---
title: Demo
tags:
  - project
  - active
---

# Top

Intro paragraph linking [[Other Note]] and an inline #idea tag.

## Section A

Body of A.

## Section B

Body of B with a [[Note|alias]] link.
"""


def test_chunks_split_by_heading():
    chunks = load_markdown(DOC, "demo.md")
    headings = [c.heading for c in chunks]
    assert any("Top" in h for h in headings)
    assert any("Section A" in h for h in headings)
    assert any("Section B" in h for h in headings)


def test_metadata_extracted():
    chunks = load_markdown(DOC, "demo.md")
    all_tags = {t for c in chunks for t in c.tags}
    all_links = {link for c in chunks for link in c.links}
    assert "project" in all_tags and "active" in all_tags
    assert "idea" in all_tags
    assert "Other Note" in all_links
    assert "Note" in all_links


def test_offsets_are_within_source():
    chunks = load_markdown(DOC, "demo.md")
    for c in chunks:
        assert 0 <= c.start <= c.end <= len(DOC)
        assert c.path == "demo.md"


def test_long_section_subsplits_with_overlap():
    big = "# H\n\n" + ("word " * 1000)
    chunks = load_markdown(big, "big.md", max_chars=400, overlap=50)
    assert len(chunks) >= 3
    assert all(len(c.text) <= 400 + 50 for c in chunks)


def test_iter_corpus_prunes_and_skips_symlinks(tmp_path):
    (tmp_path / "keep.md").write_text("# k")
    obs = tmp_path / ".obsidian"
    obs.mkdir()
    (obs / "config.md").write_text("# c")  # in a pruned dir
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "note.md").write_text("# n")
    # a symlinked dir pointing outside should not be traversed
    outside = tmp_path.parent / "outside_vault"
    outside.mkdir(exist_ok=True)
    (outside / "leak.md").write_text("# leak")
    try:
        os.symlink(outside, tmp_path / "linkdir")
    except (OSError, NotImplementedError):
        pass  # symlinks may be unavailable; the prune assertions still hold
    found = {p.relative_to(tmp_path).as_posix() for p in iter_corpus(tmp_path)}
    assert "keep.md" in found
    assert "sub/note.md" in found
    assert ".obsidian/config.md" not in found  # pruned
    assert "linkdir/leak.md" not in found  # symlink not followed
