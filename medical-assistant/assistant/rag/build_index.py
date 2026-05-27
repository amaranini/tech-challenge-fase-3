"""Constrói o índice RAG a partir dos protocolos sintéticos.

Lê todos os `.md` em `data/synthetic/protocols/`, extrai o frontmatter
para metadados, quebra cada protocolo em chunks com `RecursiveCharacterTextSplitter`
respeitando headers markdown, gera embeddings com
`paraphrase-multilingual-MiniLM-L12-v2` e persiste em ChromaDB.

Idempotente: a coleção existente é deletada e recriada a cada execução.

Uso:
    uv run python assistant/rag/build_index.py
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Caminhos
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.parent
PROTOCOLS_DIR = PROJECT_ROOT / "data" / "synthetic" / "protocols"
CHROMA_DIR = PROJECT_ROOT / "assistant" / "data" / "chroma_db"

# Configuração do índice
COLLECTION_NAME = "protocols"
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Chunking: tamanho em tokens (aproximado via tiktoken cl100k_base).
# 400 ~= "uma seção típica" de protocolo; overlap 80 evita perder frases na borda.
CHUNK_SIZE_TOKENS = 400
CHUNK_OVERLAP_TOKENS = 80


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Extrai frontmatter YAML simples e retorna (metadata, body)."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    fm_text = text[4:end]
    body = text[end + 5 :]
    fm: dict[str, str] = {}
    for line in fm_text.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip('"')
    return fm, body


def split_into_sections(body: str) -> list[tuple[str, str]]:
    """Quebra o corpo do protocolo por headers `## `. Retorna [(seção, texto), ...].

    A primeira parte (antes do primeiro `## `) é rotulada como "Introdução".
    """
    parts = re.split(r"\n(?=## )", body)
    sections: list[tuple[str, str]] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part.startswith("## "):
            first_nl = part.find("\n")
            if first_nl > 0:
                title = part[3:first_nl].strip()
                content = part[first_nl + 1 :].strip()
            else:
                title = part[3:].strip()
                content = ""
        else:
            title = "Introdução"
            content = part
        if content:
            sections.append((title, content))
    return sections


def chunk_protocol(
    body: str, splitter: RecursiveCharacterTextSplitter
) -> list[tuple[str, str]]:
    """Divide um protocolo em chunks, mantendo a seção em cada chunk.

    Retorna lista de (section_title, chunk_text). Seções pequenas viram
    um único chunk; grandes são divididas pelo splitter.
    """
    chunks: list[tuple[str, str]] = []
    for section_title, section_body in split_into_sections(body):
        # Prepend o título da seção pra dar contexto ao embedding.
        prefixed = f"## {section_title}\n\n{section_body}"
        for piece in splitter.split_text(prefixed):
            chunks.append((section_title, piece))
    return chunks


def _embedding_function():
    """Instancia o embedding function do Chroma (com sentence-transformers).
    Em caso de incompatibilidade Chroma <-> ST, faz fallback claro."""
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )


def main() -> int:
    if not PROTOCOLS_DIR.exists():
        print(f"❌ {PROTOCOLS_DIR.relative_to(PROJECT_ROOT)} não existe.")
        print("   Gere os protocolos antes: uv run python data/generate_synthetic.py")
        return 1

    md_files = sorted(PROTOCOLS_DIR.glob("*.md"))
    if not md_files:
        print(f"❌ Nenhum .md em {PROTOCOLS_DIR.relative_to(PROJECT_ROOT)}.")
        return 1

    print("=" * 64)
    print("  Construção do índice RAG (Chroma + sentence-transformers)")
    print("=" * 64)
    print(f"  Protocolos:    {len(md_files)} arquivos")
    print(f"  Modelo emb.:   {EMBEDDING_MODEL}")
    print(f"  Chunk size:    ~{CHUNK_SIZE_TOKENS} tokens (overlap {CHUNK_OVERLAP_TOKENS})")
    print(f"  Persistência:  {CHROMA_DIR.relative_to(PROJECT_ROOT)}")
    print(
        f"  Tempo estimado: ~30-90s (primeira vez pode demorar mais — baixa o "
        f"modelo de embeddings, ~120 MB)"
    )
    print()

    t0 = time.monotonic()

    # Splitter por tokens via tiktoken.
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        chunk_size=CHUNK_SIZE_TOKENS,
        chunk_overlap=CHUNK_OVERLAP_TOKENS,
        separators=["\n## ", "\n### ", "\n\n", "\n", ". ", " ", ""],
    )

    # Coleta todos os chunks + metadados antes de chamar o Chroma.
    all_ids: list[str] = []
    all_docs: list[str] = []
    all_metas: list[dict] = []

    print("→ Lendo e quebrando protocolos...")
    for md in md_files:
        text = md.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(text)
        title = fm.get("titulo", md.stem)
        specialty = fm.get("especialidade", "")

        chunks = chunk_protocol(body, splitter)
        for idx, (section, chunk_text) in enumerate(chunks):
            chunk_id = f"{md.stem}::{idx}"
            all_ids.append(chunk_id)
            all_docs.append(chunk_text)
            all_metas.append(
                {
                    "source_file": md.name,
                    "title": title,
                    "specialty": specialty,
                    "section": section,
                    "chunk_index": idx,
                }
            )
        print(f"  {md.name:48s} {len(chunks):3d} chunks")

    print(f"\n→ Total: {len(all_docs)} chunks de {len(md_files)} protocolos.")

    # Conecta ao Chroma e reseta a coleção (idempotente).
    print(f"\n→ Conectando ao Chroma em {CHROMA_DIR.relative_to(PROJECT_ROOT)}...")
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )

    try:
        client.delete_collection(COLLECTION_NAME)
        print(f"  (coleção anterior '{COLLECTION_NAME}' apagada)")
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=_embedding_function(),
        metadata={"hnsw:space": "cosine"},
    )

    # Indexa em batches (Chroma calcula embeddings automaticamente).
    BATCH = 64
    print(f"\n→ Indexando {len(all_docs)} chunks em batches de {BATCH}...")
    for i in range(0, len(all_docs), BATCH):
        end = min(i + BATCH, len(all_docs))
        collection.add(
            ids=all_ids[i:end],
            documents=all_docs[i:end],
            metadatas=all_metas[i:end],
        )
        print(f"  {end}/{len(all_docs)}")

    elapsed = time.monotonic() - t0

    # Estatísticas finais
    chunk_lens = [len(d) for d in all_docs]
    avg_len = sum(chunk_lens) / len(chunk_lens) if chunk_lens else 0
    print("\n" + "=" * 64)
    print(f"✅ Índice construído em {elapsed:.1f}s")
    print(f"   Protocolos:    {len(md_files)}")
    print(f"   Chunks:        {len(all_docs)}")
    print(f"   Tam. médio:    {avg_len:.0f} caracteres (~{avg_len/4:.0f} tokens)")
    print(f"   Tam. máx/mín:  {max(chunk_lens)} / {min(chunk_lens)} caracteres")
    print(f"   Persistido em: {CHROMA_DIR.relative_to(PROJECT_ROOT)}")
    print("\nSmoke test do retriever:")
    print('   uv run python -m assistant.rag.retriever "Como manejar sepse?"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
