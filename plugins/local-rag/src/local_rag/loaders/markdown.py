from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

_FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
_WIKILINK_RE = re.compile(r"\[\[([^\]\|#]+)(?:[#|][^\]]*)?\]\]")
_TAG_RE = re.compile(r"(?:^|\s)#([A-Za-z][\w\-/]*)")


@dataclass
class Chunk:
    text: str
    path: str
    heading: str
    start: int
    end: int
    tags: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)


def _parse_frontmatter_tags(text: str) -> tuple[list[str], int]:
    """Return (tags, body_offset). Minimal YAML subset."""
    m = _FM_RE.match(text)
    if not m:
        return [], 0
    fm = m.group(1)
    tags: list[str] = []
    inline = re.search(r"^tags:\s*\[(.*?)\]\s*$", fm, re.MULTILINE)
    if inline:
        tags = [t.strip().strip("'\"") for t in inline.group(1).split(",") if t.strip()]
    else:
        block = re.search(r"^tags:\s*$((?:\n[ \t]*-\s*.+)+)", fm, re.MULTILINE)
        if block:
            tags = [ln.strip()[1:].strip().strip("'\"")
                    for ln in block.group(1).splitlines() if ln.strip().startswith("-")]
        else:
            single = re.search(r"^tags:[^\S\n]*(\S.*)$", fm, re.MULTILINE)
            if single:
                tags = [single.group(1).strip().strip("'\"")]
    return tags, m.end()


def _extract(text: str) -> tuple[list[str], list[str]]:
    tags = sorted({t for t in _TAG_RE.findall(text)})
    links = sorted({link.strip() for link in _WIKILINK_RE.findall(text)})
    return tags, links


def load_markdown(text: str, path: str, *, max_chars: int = 1200, overlap: int = 150) -> list[Chunk]:
    fm_tags, body_off = _parse_frontmatter_tags(text)

    headings = list(_HEADING_RE.finditer(text, body_off))
    spans: list[tuple[int, int, str]] = []
    if not headings:
        spans = [(body_off, len(text), "")]
    else:
        if headings[0].start() > body_off:
            spans.append((body_off, headings[0].start(), ""))
        for i, h in enumerate(headings):
            end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
            spans.append((h.start(), end, h.group(2).strip()))

    chunks: list[Chunk] = []
    for start, end, heading in spans:
        section = text[start:end]
        if not section.strip():
            continue
        pos = 0
        while pos < len(section):
            piece = section[pos: pos + max_chars]
            if not piece.strip():
                break
            c_start = start + pos
            c_end = start + pos + len(piece)
            tags, links = _extract(piece)
            chunks.append(Chunk(
                text=piece.strip(),
                path=path,
                heading=heading,
                start=c_start,
                end=c_end,
                tags=sorted(set(tags) | set(fm_tags)),
                links=links,
            ))
            if pos + max_chars >= len(section):
                break
            pos += max_chars - overlap
    return chunks


def iter_corpus(root, include: list[str] | None = None, exclude: list[str] | None = None) -> Iterator[Path]:
    root = Path(root)
    include = include or ["*.md", "*.markdown"]
    exclude = exclude or []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if not any(p.match(g) for g in include):
            continue
        if any(Path(rel).match(g) or g in rel for g in exclude):
            continue
        yield p
