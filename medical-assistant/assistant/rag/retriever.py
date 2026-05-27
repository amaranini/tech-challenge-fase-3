"""Recuperação de chunks relevantes do índice RAG.

A classe `ProtocolRetriever` encapsula o acesso ao Chroma e expõe o método
`retrieve(query, top_k)` que retorna `RetrievedChunk`s com texto, metadados
e score de similaridade.

Smoke test (linha de comando):
    uv run python -m assistant.rag.retriever "Como manejar sepse?"
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

logger = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.parent
CHROMA_DIR = PROJECT_ROOT / "assistant" / "data" / "chroma_db"

COLLECTION_NAME = "protocols"
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


@dataclass
class RetrievedChunk:
    """Um chunk recuperado, com texto, metadados e score de similaridade.

    `score` é a similaridade do cosseno (0 a 1, maior = mais similar).
    Convertido de `distance` do Chroma via `1 - distance` (cosine space).
    """

    text: str
    metadata: dict[str, Any]
    score: float

    @property
    def source_file(self) -> str:
        return self.metadata.get("source_file", "?")

    @property
    def title(self) -> str:
        return self.metadata.get("title", "?")

    @property
    def section(self) -> str:
        return self.metadata.get("section", "?")

    @property
    def specialty(self) -> str:
        return self.metadata.get("specialty", "")


class ProtocolRetriever:
    """Wrapper do Chroma para recuperação dos chunks de protocolos."""

    def __init__(
        self,
        persist_dir: Path | str = CHROMA_DIR,
        collection_name: str = COLLECTION_NAME,
    ) -> None:
        self.persist_dir = Path(persist_dir)
        if not self.persist_dir.exists():
            raise FileNotFoundError(
                f"Índice RAG não encontrado em '{self.persist_dir}'.\n"
                f"Construa antes: uv run python assistant/rag/build_index.py"
            )
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=Settings(anonymized_telemetry=False),
        )
        try:
            self.collection = self.client.get_collection(
                name=collection_name,
                embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name=EMBEDDING_MODEL
                ),
            )
        except Exception as e:
            raise RuntimeError(
                f"Coleção '{collection_name}' não encontrada em '{self.persist_dir}'.\n"
                f"Reconstrua o índice: uv run python assistant/rag/build_index.py"
            ) from e

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        min_score: float | None = None,
    ) -> list[RetrievedChunk]:
        """Busca top_k chunks mais similares à query.

        Se `min_score` for fornecido, chunks com score (cosseno) abaixo dele
        são descartados antes do retorno. Calibração empírica para nosso
        dataset: tema presente ≈ 0.65-0.80; tema ausente ≈ 0.40-0.50.
        `min_score=0.5` é o default usado em produção (via `RAG_MIN_SCORE`).

        Quando `min_score` filtra TUDO, retorna lista vazia — a chain detecta
        isso e injeta um aviso de "sem contexto relevante" no prompt do LLM.
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
        )
        ids = results["ids"][0]
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        dists = results["distances"][0]

        chunks: list[RetrievedChunk] = []
        for _id, doc, meta, dist in zip(ids, docs, metas, dists):
            # Em cosine space do Chroma: distance ∈ [0, 2]; similarity = 1 - distance.
            score = 1.0 - float(dist)
            chunks.append(RetrievedChunk(text=doc, metadata=dict(meta), score=score))

        raw_count = len(chunks)
        if min_score is not None:
            chunks = [c for c in chunks if c.score >= min_score]

        logger.info(
            "Retrieved top_k=%d min_score=%s for query=%r → %d/%d kept: %s",
            top_k,
            min_score,
            query[:60],
            len(chunks),
            raw_count,
            [(c.source_file, round(c.score, 3)) for c in chunks],
        )
        return chunks


_default: ProtocolRetriever | None = None


def default_retriever() -> ProtocolRetriever:
    """Retorna o retriever default (singleton). Levanta erro claro se o índice não existir."""
    global _default
    if _default is None:
        _default = ProtocolRetriever()
    return _default


def _cli(query: str, top_k: int = 3) -> int:
    """Smoke test: imprime os top_k chunks formatados pra leitura humana."""
    print(f'Query: "{query}"\n')
    retriever = ProtocolRetriever()
    chunks = retriever.retrieve(query, top_k=top_k)
    if not chunks:
        print("⚠ Nenhum chunk recuperado.")
        return 1
    for i, c in enumerate(chunks, start=1):
        print("=" * 70)
        print(
            f"  [{i}] {c.source_file} • {c.section} • "
            f"score={c.score:.3f} • {c.specialty}"
        )
        print("=" * 70)
        print(c.text[:500] + (" […]" if len(c.text) > 500 else ""))
        print()
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Uso: uv run python -m assistant.rag.retriever "sua pergunta"')
        sys.exit(2)
    sys.exit(_cli(sys.argv[1]))
