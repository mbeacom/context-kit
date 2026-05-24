# Local RAG (planned)

Fully-local semantic retrieval: [`turbovec`](https://github.com/RyanCodrai/turbovec)
(quantized vector index, MIT) + `ollama` embeddings. Will ship a `bin/rag` CLI
(`index <path>` / `query <text>`), persist the index under `${CLAUDE_PLUGIN_DATA}`,
and expose turbovec's hybrid `allowlist` path so `retrieval-core` can feed it
candidates from lexical/graph layers.

**Status:** scaffold only — not listed in the marketplace catalog yet. Design in
a forthcoming spec. Open question: primary corpus (notes / code / mixed).
