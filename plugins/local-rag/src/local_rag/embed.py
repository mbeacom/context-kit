from __future__ import annotations

import httpx


class EmbedError(RuntimeError):
    pass


class OllamaEmbedder:
    def __init__(self, model: str = "nomic-embed-text", host: str = "http://localhost:11434"):
        self.model = model
        self.host = host.rstrip("/")
        self._client = httpx.Client()
        self._dim: int | None = None

    def _embed_one(self, text: str) -> list[float]:
        try:
            resp = self._client.post(
                f"{self.host}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=60.0,
            )
            resp.raise_for_status()
        except httpx.ConnectError as e:
            raise EmbedError(
                f"Could not reach ollama at {self.host}: {e}. "
                f"Start it with 'ollama serve' and ensure the model is pulled: "
                f"'ollama pull {self.model}'."
            ) from e
        except httpx.HTTPStatusError as e:
            raise EmbedError(
                f"ollama returned an error for model '{self.model}'. "
                f"Pull it with 'ollama pull {self.model}'. ({e})"
            ) from e
        vec = resp.json().get("embedding")
        if not vec:
            raise EmbedError(f"ollama returned no embedding for model '{self.model}'.")
        return vec

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def dim(self) -> int:
        if self._dim is None:
            self._dim = len(self._embed_one("dimension probe"))
        return self._dim
