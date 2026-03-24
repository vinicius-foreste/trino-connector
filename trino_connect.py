"""Wrapper minimalista para conexão com Trino (pyhive).

Este módulo disponibiliza a classe `TrinoClient` que encapsula a
conexão, execução de queries e política simples de retry com
exponential backoff + jitter. Não loga credenciais.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Optional, Any

import pandas as pd
from pyhive import trino

logger = logging.getLogger(__name__)


class TrinoClient:
    """Cliente leve para executar queries no Trino via pyhive.

    Exemplo:
        cfg = TrinoClient(host="trino-host")
        cfg.connect(user, password)
        df = cfg.execute("SELECT ...")
        cfg.close()

    Note:
    - Não armazene senhas em logs. Use `credentials` module ou env vars.
    - `pyhive.trino.connect` pode não expor timeout; controle tempo via retry/backoff.
    """

    def __init__(
        self,
        host: str,
        port: str = "443",
        protocol: str = "https",
        source: str = "dataeng-trino-api",
        timeout: int = 10,
        max_retries: int = 3,
        retry_backoff: float = 1.0,
        max_backoff: float = 30.0,
    ):
        """Inicializa o cliente.

        Args:
            host: endereço do Trino (host ou host:port se preferir).
            port: porta (padrão 443 para HTTPS gateways).
            protocol: 'https' ou 'http'.
            source: string identificadora (user agent) enviada ao Trino.
            timeout: timeout de rede sugerido (não garantido por pyhive).
            max_retries: número máximo de tentativas em caso de erro.
            retry_backoff: tempo base (s) para backoff exponencial.
            max_backoff: cap máximo (s) para backoff.
        """
        self.host = host
        self.port = port
        self.protocol = protocol
        self.source = source
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.max_backoff = max_backoff

        self._conn: Optional[Any] = None  # objeto de conexão (None quando não conectado)

    def connect(self, username: str, password: str) -> None:
        """Abre a conexão com Trino usando as credenciais fornecidas.

        Não retorna a senha nem a loga. Lança exceção em caso de falha.
        """
        # pyhive.trino.connect cria e retorna um objeto de conexão
        self._conn = trino.connect(
            host=self.host,
            port=443,
            protocol='https',
            source='dataeng-trino-api',
            username=username,
            password=password,
        )

    def execute(self, query: str) -> pd.DataFrame:
        """Executa uma query no Trino e retorna um pandas.DataFrame.

        Implementa política de retry com exponential backoff + jitter.

        Args:
            query: SQL a ser executado.

        Returns:
            pd.DataFrame com os resultados (colunas quando disponíveis).

        Raises:
            Exception: a exceção final caso todas as tentativas falhem.
        """
        if not self._conn:
            raise RuntimeError("Conexão não iniciada. Chame connect() primeiro.")

        last_exc = None
        for attempt in range(1, self.max_retries + 1):
            try:
                cursor = self._conn.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
                cols = [c[0] for c in cursor.description] if cursor.description else None
                return pd.DataFrame(rows, columns=cols)
            except Exception as exc:
                last_exc = exc
                logger.debug("Trino query failed on attempt %d: %s", attempt, exc)
                if attempt == self.max_retries:
                    logger.error("Todas as tentativas falharam: %s", exc)
                    raise
                # exponential backoff with cap and jitter
                base = self.retry_backoff * (2 ** (attempt - 1))
                sleep = min(base, self.max_backoff)
                jitter = random.uniform(0.5, 1.5)
                sleep *= jitter
                logger.debug("Sleeping %.2fs before retrying (attempt=%d)", sleep, attempt)
                time.sleep(sleep)

        # should not reach here, but keep safety
        if last_exc:
            raise last_exc

    def close(self) -> None:
        """Fecha a conexão localmente. Em muitas versões do pyhive isso apenas libera a referência."""
        self._conn = None

    def __enter__(self) -> "TrinoClient":
        if not self._conn:
            raise RuntimeError("Conexão não iniciada. Chame connect() antes de usar o context manager.")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()