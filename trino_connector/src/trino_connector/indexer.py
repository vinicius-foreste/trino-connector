"""Indexador de metadados do Trino → ChromaDB.

Extrai schemas, tabelas e colunas via information_schema do Trino,
formata como documentos de texto e indexa no ChromaDB para busca
semântica (RAG).

Uso:
    python indexer.py                    # indexa catálogo padrão (config)
    python indexer.py --catalogs hive    # indexa catálogo específico
    python indexer.py --all-catalogs     # indexa tudo
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Optional

from trino_connector import config
from trino_connector.trino_connect import TrinoClient
from trino_connector.credenciais import load_credentials

try:
    import chromadb
except ImportError:
    print("❌ chromadb não instalado. Execute: pip install chromadb")
    sys.exit(1)


def _quote(identifier: str) -> str:
    """Coloca aspas duplas em identificadores com caracteres especiais."""
    if not identifier.replace("_", "").isalnum():
        return f'"{identifier}"'
    return identifier


def fetch_metadata(
    client: TrinoClient,
    catalogs: Optional[list[str]] = None,
) -> list[dict]:
    """Extrai metadados de tabelas e colunas via information_schema.

    Retorna lista de dicts:
      {
        "catalog": str,
        "schema": str,
        "table": str,
        "columns": [{"name": str, "type": str}, ...]
      }
    """
    if catalogs is None:
        catalogs = [config.TRINO_CATALOG]

    tables: dict[str, dict] = {}
    total_cols = 0

    for cat in catalogs:
        print(f"   📂 Extraindo metadados de {cat}...", end=" ", flush=True)
        query = f"""
            SELECT table_schema, table_name, column_name, data_type
            FROM {_quote(cat)}.information_schema.columns
            WHERE table_schema NOT IN ('information_schema')
            ORDER BY table_schema, table_name, ordinal_position
        """
        try:
            df = client.execute(query)
        except Exception as exc:
            print(f"erro ({exc})")
            continue

        count = 0
        for _, row in df.iterrows():
            schema = row.iloc[0]
            table = row.iloc[1]
            col_name = row.iloc[2]
            col_type = row.iloc[3]
            fqn = f"{cat}.{schema}.{table}"

            if fqn not in tables:
                tables[fqn] = {
                    "catalog": cat,
                    "schema": schema,
                    "table": table,
                    "columns": [],
                }
            tables[fqn]["columns"].append({"name": col_name, "type": col_type})
            count += 1

        total_cols += count
        print(f"{len([t for t in tables if t.startswith(cat + '.')])} tabelas, {count} colunas")

    print(f"   ✓ Total: {len(tables)} tabelas, {total_cols} colunas")
    return list(tables.values())


def format_document(table_meta: dict) -> str:
    """Formata metadados de uma tabela como texto estruturado para embedding."""
    fqn = f"{table_meta['catalog']}.{table_meta['schema']}.{table_meta['table']}"
    cols = "\n".join(
        f"  - {c['name']} ({c['type']})" for c in table_meta["columns"]
    )
    return (
        f"Tabela: {fqn}\n"
        f"Schema: {table_meta['schema']}\n"
        f"Catálogo: {table_meta['catalog']}\n"
        f"Colunas:\n{cols}"
    )


def index_to_chromadb(
    metadata: list[dict],
    persist_dir: str = config.CHROMA_PERSIST_DIR,
    collection_name: str = config.CHROMA_COLLECTION,
) -> int:
    """Insere metadados no ChromaDB. Retorna qtd de documentos indexados."""
    client = chromadb.PersistentClient(path=persist_dir)

    # Recria a collection do zero para garantir dados frescos
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass
    collection = client.create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )

    # Processa em batches de 500 (limite do ChromaDB)
    batch_size = 500
    total = len(metadata)
    indexed = 0

    for i in range(0, total, batch_size):
        batch = metadata[i : i + batch_size]
        ids = []
        documents = []
        metadatas = []

        for tbl in batch:
            fqn = f"{tbl['catalog']}.{tbl['schema']}.{tbl['table']}"
            ids.append(fqn)
            documents.append(format_document(tbl))
            metadatas.append({
                "catalog": tbl["catalog"],
                "schema": tbl["schema"],
                "table": tbl["table"],
                "num_columns": len(tbl["columns"]),
            })

        collection.add(ids=ids, documents=documents, metadatas=metadatas)
        indexed += len(batch)
        print(f"   Indexando... {indexed}/{total}", end="\r", flush=True)

    print(f"\n   ✓ {indexed} tabelas indexadas em {persist_dir}/")
    return indexed


def main():
    parser = argparse.ArgumentParser(description="Indexa metadados do Trino no ChromaDB")
    parser.add_argument(
        "--catalogs", nargs="+",
        help=f"Catálogos para indexar (padrão: {config.TRINO_CATALOG})",
    )
    parser.add_argument("--all-catalogs", action="store_true", help="Indexa todos os catálogos")
    args = parser.parse_args()

    print("=" * 60)
    print("  Indexador de Metadados — Trino → ChromaDB")
    print("=" * 60)

    # Valida config
    problems = config.validate()
    if "TRINO_HOST" in str(problems):
        print(f"❌ {problems}")
        return

    # Conecta ao Trino
    print("\n🔌 Conectando ao Trino...")
    user, pwd = load_credentials()
    client = TrinoClient(host=config.TRINO_HOST, port=config.TRINO_PORT)
    client.connect(user, pwd)

    # Determina catálogos
    catalogs = args.catalogs
    if args.all_catalogs:
        print("   Descobrindo catálogos...")
        from trino_connector.schema_discovery import discover_catalogs
        catalogs = discover_catalogs(client)
        print(f"   Catálogos: {', '.join(catalogs)}")
    elif catalogs is None:
        catalogs = [config.TRINO_CATALOG]

    # Extrai metadados
    print(f"\n📊 Extraindo metadados de {len(catalogs)} catálogo(s)...")
    t0 = time.time()
    metadata = fetch_metadata(client, catalogs)
    elapsed = time.time() - t0
    print(f"   Extração concluída em {elapsed:.1f}s")

    if not metadata:
        print("❌ Nenhuma tabela encontrada.")
        client.close()
        return

    # Indexa no ChromaDB
    print(f"\n🗄️ Indexando no ChromaDB...")
    t0 = time.time()
    count = index_to_chromadb(metadata)
    elapsed = time.time() - t0
    print(f"   Indexação concluída em {elapsed:.1f}s")

    client.close()
    print(f"\n✅ Pronto! {count} tabelas indexadas. Use main.py para fazer perguntas.")


if __name__ == "__main__":
    main()
