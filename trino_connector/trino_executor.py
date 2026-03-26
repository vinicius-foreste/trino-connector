"""Executor Trino — recebe SQL gerado pelo LLM e executa no cluster.

Retorna os dados como pandas DataFrame com tratamento de erros robusto.
"""

from __future__ import annotations

import logging

import pandas as pd

import config
from trino_connect import TrinoClient
from credenciais import load_credentials

logger = logging.getLogger(__name__)

_client: TrinoClient | None = None


def get_client() -> TrinoClient:
    """Retorna um TrinoClient conectado (singleton por sessão)."""
    global _client
    if _client is not None:
        return _client

    user, pwd = load_credentials()
    _client = TrinoClient(host=config.TRINO_HOST, port=config.TRINO_PORT)
    _client.connect(user, pwd)
    return _client


def execute(sql: str, client: TrinoClient | None = None) -> pd.DataFrame:
    """Executa SQL no Trino e retorna DataFrame.

    Args:
        sql: query SQL a ser executada.
        client: TrinoClient conectado (usa singleton se None).

    Returns:
        pd.DataFrame com os resultados.

    Raises:
        RuntimeError: se houver erro de conexão ou SQL inválido.
    """
    c = client or get_client()

    try:
        df = c.execute(sql)
        logger.info("Query executada com sucesso: %d linhas", len(df))
        return df
    except Exception as exc:
        error_msg = str(exc)
        # Erros comuns do Trino com mensagens amigáveis
        if "CATALOG_NOT_FOUND" in error_msg:
            raise RuntimeError(f"Catálogo não encontrado. Verifique o nome. Erro: {error_msg}") from exc
        if "SCHEMA_NOT_FOUND" in error_msg:
            raise RuntimeError(f"Schema não encontrado. Verifique o nome. Erro: {error_msg}") from exc
        if "TABLE_NOT_FOUND" in error_msg:
            raise RuntimeError(f"Tabela não encontrada. Verifique o nome. Erro: {error_msg}") from exc
        if "COLUMN_NOT_FOUND" in error_msg:
            raise RuntimeError(f"Coluna não encontrada. Verifique o nome. Erro: {error_msg}") from exc
        if "SYNTAX_ERROR" in error_msg:
            raise RuntimeError(f"Erro de sintaxe SQL gerado pela IA. Erro: {error_msg}") from exc
        raise RuntimeError(f"Erro ao executar query no Trino: {error_msg}") from exc


def close():
    """Fecha a conexão do cliente singleton."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
