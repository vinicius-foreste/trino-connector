"""Descoberta de schema do Trino para fornecer contexto ao LLM.

Consulta catalogs, schemas, tabelas e colunas do Trino e formata
como contexto estruturado para prompts de text-to-SQL.

Suporta auto-descoberta completa: catalogs → schemas → tabelas.
O Trino já filtra por permissão, retornando apenas o que o usuário pode ver.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

import pandas as pd

from trino_connect import TrinoClient

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent / ".schema_cache"

# Catálogos internos do Trino que não contêm dados do usuário
_IGNORE_CATALOGS = {"system", "jmx", "memory", "tpch", "tpcds"}
# Schemas internos que geralmente não interessam
_IGNORE_SCHEMAS = {"information_schema"}


def _quote(identifier: str) -> str:
    """Coloca aspas duplas em identificadores com caracteres especiais (ex: '-')."""
    if not identifier.replace("_", "").isalnum():
        return f'"{identifier}"'
    return identifier


def discover_catalogs(client: TrinoClient) -> list[str]:
    """Lista todos os catálogos acessíveis ao usuário."""
    df = client.execute("SHOW CATALOGS")
    col = df.columns[0]
    return [c for c in df[col].tolist() if c.lower() not in _IGNORE_CATALOGS]


def discover_schemas(client: TrinoClient, catalog: str) -> list[str]:
    """Lista schemas de um catálogo."""
    df = client.execute(f"SHOW SCHEMAS FROM {_quote(catalog)}")
    col = df.columns[0]
    return [s for s in df[col].tolist() if s.lower() not in _IGNORE_SCHEMAS]


def discover_tables(client: TrinoClient, catalog: str, schema: str) -> pd.DataFrame:
    """Lista tabelas de um schema específico."""
    query = f"SHOW TABLES FROM {_quote(catalog)}.{_quote(schema)}"
    return client.execute(query)


def discover_columns(
    client: TrinoClient, catalog: str, schema: str, table: str
) -> pd.DataFrame:
    """Lista colunas de uma tabela específica."""
    query = f"SHOW COLUMNS FROM {_quote(catalog)}.{_quote(schema)}.{_quote(table)}"
    return client.execute(query)


# Sem timeout por padrão (0 = ilimitado). Configura via env se quiser limitar.
# Ex: $env:TRINO_DISCOVERY_TIMEOUT = '120'
_DISCOVERY_TIMEOUT_RAW = os.environ.get("TRINO_DISCOVERY_TIMEOUT", "0")
_DISCOVERY_TIMEOUT: Optional[int] = int(_DISCOVERY_TIMEOUT_RAW) if _DISCOVERY_TIMEOUT_RAW.isdigit() and int(_DISCOVERY_TIMEOUT_RAW) > 0 else None


def _print(msg: str, **kwargs) -> None:
    """Print com flush garantido."""
    print(msg, **kwargs)
    sys.stdout.flush()


def discover_all_tables(
    client: TrinoClient,
    *,
    catalogs: Optional[list[str]] = None,
    use_cache: bool = True,
) -> list[str]:
    """Descobre tabelas acessíveis ao usuário no Trino.

    Faz: SHOW CATALOGS → SHOW SCHEMAS → SHOW TABLES para cada combinação.
    Sem timeout por padrão — processa tudo até o fim.
    Use TRINO_DISCOVERY_TIMEOUT (segundos) para adicionar limite se desejar.

    Dica: use catalogs=["meu_catalogo"] para descoberta muito mais rápida.
    """
    cache_file = CACHE_DIR / "_all_tables.json" if use_cache else None
    if cache_file:
        CACHE_DIR.mkdir(exist_ok=True)
        if cache_file.exists():
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            _print(f"   (cache: {len(data)} tabelas — use --no-cache para atualizar)")
            return data

    deadline = (time.monotonic() + _DISCOVERY_TIMEOUT) if _DISCOVERY_TIMEOUT else None

    if catalogs is None:
        _print("   Listando catálogos...", end=" ")
        catalogs = discover_catalogs(client)
        _print(f"{len(catalogs)} encontrados: {', '.join(catalogs)}")
        if len(catalogs) > 3:
            _print(
                f"   ⚡ Dica: use -c para ser mais rápido na próxima vez:\n"
                f"      python cli.py ask 'pergunta' -c {catalogs[0]}"
            )

    all_tables: list[str] = []
    total_cats = len(catalogs)
    for idx, cat in enumerate(catalogs, 1):
        if deadline and time.monotonic() > deadline:
            _print(f"\n   ⏱ Timeout ({_DISCOVERY_TIMEOUT}s) atingido após {len(all_tables)} tabelas.")
            break

        _print(f"   [{idx}/{total_cats}] {cat}: listando schemas...", end=" ")
        try:
            schemas = discover_schemas(client, cat)
        except Exception as exc:
            _print(f"erro ({exc})")
            logger.warning("Não foi possível listar schemas de %s: %s", cat, exc)
            continue

        _print(f"{len(schemas)} schemas", end=" | ")
        cat_tables = 0
        for sch in schemas:
            if deadline and time.monotonic() > deadline:
                break
            try:
                df = discover_tables(client, cat, sch)
                col = df.columns[0]
                tbls = df[col].tolist()
                for tbl in tbls:
                    all_tables.append(f"{cat}.{sch}.{tbl}")
                cat_tables += len(tbls)
                _print(f"{sch}({len(tbls)})", end=" ")
            except Exception as exc:
                logger.warning("Não foi possível listar tabelas de %s.%s: %s", cat, sch, exc)
        _print(f"| total: {cat_tables} tabelas")

    if cache_file and all_tables:
        cache_file.write_text(
            json.dumps(all_tables, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _print(f"   ✓ Schema salvo em cache ({len(all_tables)} tabelas totais).")

    return all_tables


def build_schema_context(
    client: TrinoClient,
    tables: list[dict],
    *,
    use_cache: bool = True,
) -> str:
    """Constrói descrição textual do schema para uso em prompts LLM.

    Args:
        client: TrinoClient conectado.
        tables: lista de dicts com chaves 'catalog', 'schema', 'table'.
                 Ex: [{"catalog": "ods", "schema": "public", "table": "ad"}]
        use_cache: se True, usa cache local para evitar consultas repetidas.

    Returns:
        String formatada descrevendo as tabelas e colunas.
    """
    if use_cache:
        CACHE_DIR.mkdir(exist_ok=True)

    lines: list[str] = []
    for tbl in tables:
        cat = tbl["catalog"]
        sch = tbl["schema"]
        name = tbl["table"]
        fqn = f"{cat}.{sch}.{name}"

        cache_file = CACHE_DIR / f"{fqn}.json" if use_cache else None

        if cache_file and cache_file.exists():
            cols = json.loads(cache_file.read_text(encoding="utf-8"))
        else:
            try:
                df = discover_columns(client, cat, sch, name)
                cols = df.to_dict(orient="records")
                if cache_file:
                    cache_file.write_text(
                        json.dumps(cols, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
            except Exception as exc:
                logger.warning("Não foi possível obter colunas de %s: %s", fqn, exc)
                cols = []

        lines.append(f"Tabela: {fqn}")
        if cols:
            for c in cols:
                col_name = c.get("Column Name") or c.get("column_name") or c.get("Column", "")
                col_type = c.get("Type") or c.get("type") or c.get("Data Type", "")
                lines.append(f"  - {col_name} ({col_type})")
        else:
            lines.append("  (sem colunas disponíveis)")
        lines.append("")

    return "\n".join(lines)


def clear_cache() -> None:
    """Remove o cache local de schemas."""
    if CACHE_DIR.exists():
        for f in CACHE_DIR.glob("*.json"):
            f.unlink()
        logger.info("Cache de schema limpo.")
