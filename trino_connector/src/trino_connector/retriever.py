"""Buscador semântico — recupera schemas relevantes do ChromaDB.

Recebe a pergunta do usuário, faz busca de similaridade no banco vetorial
e retorna os Top-K schemas mais relevantes formatados em YAML.
"""

from __future__ import annotations

import sys
from typing import Optional

from trino_connector import config

try:
    import chromadb
except ImportError:
    print("❌ chromadb não instalado. Execute: pip install chromadb")
    sys.exit(1)


def _get_collection():
    """Retorna a collection do ChromaDB. Levanta erro se não existir."""
    client = chromadb.PersistentClient(path=config.CHROMA_PERSIST_DIR)
    try:
        return client.get_collection(config.CHROMA_COLLECTION)
    except Exception:
        raise RuntimeError(
            f"Collection '{config.CHROMA_COLLECTION}' não encontrada.\n"
            "Execute primeiro: python indexer.py"
        )


def search(question: str, top_k: Optional[int] = None) -> list[dict]:
    """Busca semântica no ChromaDB.

    Args:
        question: pergunta do usuário em linguagem natural.
        top_k: quantidade de resultados (padrão: config.RAG_TOP_K).

    Returns:
        Lista de dicts com: id, document, metadata, distance.
    """
    k = top_k or config.RAG_TOP_K
    collection = _get_collection()

    results = collection.query(
        query_texts=[question],
        n_results=k,
    )

    hits = []
    for i in range(len(results["ids"][0])):
        hits.append({
            "id": results["ids"][0][i],
            "document": results["documents"][0][i],
            "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
            "distance": results["distances"][0][i] if results["distances"] else None,
        })

    return hits


def to_yaml_context(hits: list[dict]) -> str:
    """Converte os resultados da busca para formato YAML compacto.

    Formato otimizado para economizar tokens no prompt do LLM:
      - table: catalog.schema.tabela
        columns:
          - name: coluna1
            type: varchar
    """
    lines = ["tables:"]
    for hit in hits:
        table_id = hit["id"]
        doc = hit["document"]

        lines.append(f"  - table: {table_id}")
        lines.append("    columns:")

        # Extrai colunas do documento formatado pelo indexer
        for line in doc.split("\n"):
            line = line.strip()
            if line.startswith("- ") and "(" in line:
                # Formato: "- col_name (type)"
                col_part = line[2:]  # remove "- "
                paren_idx = col_part.rfind("(")
                if paren_idx > 0:
                    col_name = col_part[:paren_idx].strip()
                    col_type = col_part[paren_idx + 1 :].rstrip(")")
                    lines.append(f"      - name: {col_name}")
                    lines.append(f"        type: {col_type}")

    return "\n".join(lines)


def retrieve(question: str, top_k: Optional[int] = None) -> tuple[list[dict], str]:
    """Busca + formatação em uma chamada.

    Returns:
        (hits, yaml_context)
    """
    hits = search(question, top_k)
    yaml_ctx = to_yaml_context(hits)
    return hits, yaml_ctx
