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
