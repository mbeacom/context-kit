import io
import json

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


def test_productivity_skills_env_overrides_claude_env(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note.md").write_text("# Note\n\nportable env\n")
    claude_data = tmp_path / "claude-data"
    portable_data = tmp_path / "portable-data"
    monkeypatch.setattr(cli, "_make_embedder", lambda args: StubEmbedder())
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(claude_data))
    monkeypatch.setenv("PRODUCTIVITY_SKILLS_DATA", str(portable_data))

    rc = cli.main(["index", str(vault), "--name", "t"])

    assert rc == 0
    assert (portable_data / "indexes" / "t" / "meta.sqlite").exists()
    assert not (claude_data / "indexes").exists()


def test_productivity_skills_embed_env_overrides_claude_env(
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
    monkeypatch.setenv("PRODUCTIVITY_SKILLS_DATA", str(data))
    monkeypatch.setenv("PRODUCTIVITY_SKILLS_EMBED_MODEL", "portable-model")
    monkeypatch.setenv(
        "PRODUCTIVITY_SKILLS_OLLAMA_HOST",
        "http://portable-host:11434",
    )
    monkeypatch.setattr(cli, "OllamaEmbedder", CaptureEmbedder)

    rc = cli.main(["index", str(vault), "--name", "t"])

    assert rc == 0
    assert captured == {
        "model": "portable-model",
        "host": "http://portable-host:11434",
    }
