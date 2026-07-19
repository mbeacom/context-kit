import io
import json

import pytest

from local_rag import cli
from tests.test_engine import StubEmbedder


def test_index_and_query_json(tmp_path, monkeypatch, capsys):
    (tmp_path / "apple.md").write_text("# Apple\n\nApples. #fruit\n")
    data = tmp_path / "data"
    monkeypatch.setattr(cli, "_make_embedder", lambda args: StubEmbedder())
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(data))

    rc = cli.main(["index", str(tmp_path), "--name", "t"])
    assert rc == 0
    capsys.readouterr()

    rc = cli.main(["query", "apple", "--name", "t", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out[0]["path"] == "apple.md"
    assert out[0]["retrieval_mode"] == "semantic"
    assert "start" in out[0] and "end" in out[0]


def test_hybrid_query_json_and_text_output(tmp_path, monkeypatch, capsys):
    (tmp_path / "apple.md").write_text("# Apple\n\nunique orchard phrase\n")
    data = tmp_path / "data"
    monkeypatch.setattr(cli, "_make_embedder", lambda args: StubEmbedder())
    monkeypatch.setenv("CONTEXT_KIT_DATA", str(data))
    assert cli.main(["index", str(tmp_path), "--name", "t"]) == 0
    capsys.readouterr()

    assert cli.main(["status", "--name", "t"]) == 0
    status = json.loads(capsys.readouterr().out)
    if not status["fts5"]:
        pytest.skip("SQLite was compiled without FTS5")
    assert cli.main(["query", "orchard", "--name", "t", "--hybrid", "--json"]) == 0
    hits = json.loads(capsys.readouterr().out)
    assert hits[0]["retrieval_mode"] == "hybrid"
    assert hits[0]["lexical_rank"] == 1
    assert cli.main(["query", "orchard", "--name", "t", "--hybrid"]) == 0
    assert "hybrid" in capsys.readouterr().out


def test_allowlist_from_stdin(tmp_path, monkeypatch, capsys):
    (tmp_path / "a.md").write_text("# A\n\napple\n")
    (tmp_path / "b.md").write_text("# B\n\napple\n")
    data = tmp_path / "data"
    monkeypatch.setattr(cli, "_make_embedder", lambda args: StubEmbedder())
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(data))
    cli.main(["index", str(tmp_path), "--name", "t"])
    capsys.readouterr()

    monkeypatch.setattr("sys.stdin", io.StringIO("b.md\n"))
    cli.main(["query", "apple", "--name", "t", "--allowlist", "-", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert out and all(h["path"] == "b.md" for h in out)


def test_context_kit_data_overrides_claude_env(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note.md").write_text("# Note\n\nportable env\n")
    claude_data = tmp_path / "claude-data"
    portable_data = tmp_path / "portable-data"
    monkeypatch.setattr(cli, "_make_embedder", lambda args: StubEmbedder())
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(claude_data))
    monkeypatch.setenv("CONTEXT_KIT_DATA", str(portable_data))

    rc = cli.main(["index", str(vault), "--name", "t"])

    assert rc == 0
    assert (portable_data / "indexes" / "t" / "meta.sqlite").exists()
    assert not (claude_data / "indexes").exists()


def test_context_kit_data_overrides_legacy_and_claude(tmp_path, monkeypatch):
    """CONTEXT_KIT_DATA wins over the deprecated PRODUCTIVITY_SKILLS_DATA alias."""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note.md").write_text("# Note\n\nprecedence\n")
    claude_data = tmp_path / "claude-data"
    legacy_data = tmp_path / "legacy-data"
    portable_data = tmp_path / "portable-data"
    monkeypatch.setattr(cli, "_make_embedder", lambda args: StubEmbedder())
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(claude_data))
    monkeypatch.setenv("PRODUCTIVITY_SKILLS_DATA", str(legacy_data))
    monkeypatch.setenv("CONTEXT_KIT_DATA", str(portable_data))

    rc = cli.main(["index", str(vault), "--name", "t"])

    assert rc == 0
    assert (portable_data / "indexes" / "t" / "meta.sqlite").exists()
    assert not (legacy_data / "indexes").exists()
    assert not (claude_data / "indexes").exists()


def test_legacy_productivity_skills_data_still_supported(tmp_path, monkeypatch):
    """Back-compat: the pre-rename PRODUCTIVITY_SKILLS_DATA alias still resolves."""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note.md").write_text("# Note\n\nback compat\n")
    claude_data = tmp_path / "claude-data"
    legacy_data = tmp_path / "legacy-data"
    monkeypatch.setattr(cli, "_make_embedder", lambda args: StubEmbedder())
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(claude_data))
    monkeypatch.setenv("PRODUCTIVITY_SKILLS_DATA", str(legacy_data))

    rc = cli.main(["index", str(vault), "--name", "t"])

    assert rc == 0
    assert (legacy_data / "indexes" / "t" / "meta.sqlite").exists()
    assert not (claude_data / "indexes").exists()


def test_data_dir_expands_tilde(tmp_path, monkeypatch):
    """A tilde in CONTEXT_KIT_DATA expands to the home dir, not a literal '~'."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CONTEXT_KIT_DATA", "~/kit-data")

    assert cli._data_dir() == home / "kit-data"


def test_context_kit_embed_env_overrides_claude_env(
    tmp_path,
    monkeypatch,
):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note.md").write_text("# Note\n\nportable embed env\n")
    data = tmp_path / "data"
    captured = {}

    class CaptureEmbedder(StubEmbedder):
        def __init__(self, model, host):
            self.model = model
            self.host = host
            captured["model"] = model
            captured["host"] = host

    monkeypatch.setenv("CLAUDE_PLUGIN_OPTION_EMBED_MODEL", "claude-model")
    monkeypatch.setenv(
        "CLAUDE_PLUGIN_OPTION_OLLAMA_HOST",
        "http://claude-host:11434",
    )
    monkeypatch.setenv("CONTEXT_KIT_DATA", str(data))
    monkeypatch.setenv("CONTEXT_KIT_EMBED_MODEL", "portable-model")
    monkeypatch.setenv(
        "CONTEXT_KIT_OLLAMA_HOST",
        "http://portable-host:11434",
    )
    monkeypatch.setattr(cli, "OllamaEmbedder", CaptureEmbedder)

    rc = cli.main(["index", str(vault), "--name", "t"])

    assert rc == 0
    assert captured == {
        "model": "portable-model",
        "host": "http://portable-host:11434",
    }


def test_legacy_productivity_skills_embed_env_still_supported(
    tmp_path,
    monkeypatch,
):
    """Back-compat: the pre-rename PRODUCTIVITY_SKILLS_* embed vars still resolve."""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note.md").write_text("# Note\n\nlegacy embed env\n")
    data = tmp_path / "data"
    captured = {}

    class CaptureEmbedder(StubEmbedder):
        def __init__(self, model, host):
            self.model = model
            self.host = host
            captured["model"] = model
            captured["host"] = host

    monkeypatch.setenv("CLAUDE_PLUGIN_OPTION_EMBED_MODEL", "claude-model")
    monkeypatch.setenv(
        "CLAUDE_PLUGIN_OPTION_OLLAMA_HOST",
        "http://claude-host:11434",
    )
    monkeypatch.setenv("PRODUCTIVITY_SKILLS_DATA", str(data))
    monkeypatch.setenv("PRODUCTIVITY_SKILLS_EMBED_MODEL", "legacy-model")
    monkeypatch.setenv(
        "PRODUCTIVITY_SKILLS_OLLAMA_HOST",
        "http://legacy-host:11434",
    )
    monkeypatch.setattr(cli, "OllamaEmbedder", CaptureEmbedder)

    rc = cli.main(["index", str(vault), "--name", "t"])

    assert rc == 0
    assert captured == {
        "model": "legacy-model",
        "host": "http://legacy-host:11434",
    }
