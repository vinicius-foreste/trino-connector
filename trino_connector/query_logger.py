"""Logger de auditoria — salva log de queries para rastreabilidade.

Cada execução é registrada com: timestamp, pergunta, SQL gerado,
lineage (tabelas/colunas usadas) e status.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import config

logger = logging.getLogger(__name__)


def log_query(
    question: str,
    sql_query: str,
    lineage: list[dict],
    *,
    status: str = "success",
    error: Optional[str] = None,
    rows_returned: Optional[int] = None,
) -> None:
    """Adiciona uma entrada ao arquivo de log de auditoria.

    Args:
        question: pergunta original do usuário.
        sql_query: SQL gerado pelo LLM.
        lineage: lista de tabelas/colunas usadas.
        status: "success" ou "error".
        error: mensagem de erro (se houver).
        rows_returned: quantidade de linhas retornadas.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "question": question,
        "sql_query": sql_query,
        "lineage": lineage,
        "status": status,
        "rows_returned": rows_returned,
    }
    if error:
        entry["error"] = error

    log_file = config.AUDIT_LOG_FILE

    # Lê log existente ou cria novo
    entries = []
    if os.path.isfile(log_file):
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                entries = json.load(f)
        except (json.JSONDecodeError, OSError):
            entries = []

    entries.append(entry)

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    logger.debug("Query logada em %s", log_file)
