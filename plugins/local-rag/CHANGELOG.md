# Changelog

## 0.1.2 — 2026-05-28

- Docs: clarify that `rag` is not rtk-wrapped (prefixing is a no-op); prefer
  `rtk` on the surrounding `rg`/`git` steps, where `rtk rg -l` keeps paths raw.

## 0.1.1 — 2026-05-24

Docs: correct the `rag status` skill example (reports counts/model/dim, not staleness).

## 0.1.0 — 2026-05-24

Initial engine: bin/rag CLI, uv venv bootstrap, plugin manifest (loader/store/embed/index/engine/cli land in subsequent commits).
