import pytest
from local_rag.embed import OllamaEmbedder, EmbedError


class FakeResp:
    def __init__(self, payload, status=200):
        self._p, self.status_code = payload, status

    def json(self):
        return self._p

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError("err", request=None, response=None)


def test_embed_returns_vectors(monkeypatch):
    e = OllamaEmbedder(model="m", host="http://h")

    def fake_post(url, json, timeout):
        return FakeResp({"embedding": [0.1, 0.2, 0.3]})

    monkeypatch.setattr(e._client, "post", fake_post)
    out = e.embed(["a", "b"])
    assert out == [[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]]


def test_dim_probes_once(monkeypatch):
    e = OllamaEmbedder(model="m", host="http://h")
    calls = {"n": 0}

    def fake_post(url, json, timeout):
        calls["n"] += 1
        return FakeResp({"embedding": [0.0] * 768})

    monkeypatch.setattr(e._client, "post", fake_post)
    assert e.dim() == 768
    assert e.dim() == 768
    assert calls["n"] == 1


def test_connection_error_is_actionable(monkeypatch):
    import httpx
    e = OllamaEmbedder(model="nomic-embed-text", host="http://h")

    def boom(url, json, timeout):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(e._client, "post", boom)
    with pytest.raises(EmbedError) as ei:
        e.embed(["x"])
    msg = str(ei.value)
    assert "ollama serve" in msg and "nomic-embed-text" in msg
