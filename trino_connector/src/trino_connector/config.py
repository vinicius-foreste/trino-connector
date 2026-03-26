"""Configurações centralizadas do projeto NL2SQL.

Carrega variáveis de ambiente via python-dotenv e expõe
constantes de configuração para todos os módulos.
"""

from __future__ import annotations

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ─── Toqan (LLM Gateway) ──────────────────────────────────────
TOQAN_API_KEY: str = os.environ.get("TOQAN_API_KEY", "")
TOQAN_BASE_URL: str = os.environ.get("TOQAN_BASE_URL", "https://api.toqan.ai/api")
TOQAN_AGENT_NAME: str = os.environ.get("TOQAN_AGENT_NAME", "GeneralAssistant")
TOQAN_VERIFY_SSL: bool = os.environ.get("TOQAN_VERIFY_SSL", "false").lower() not in ("false", "0", "no")
TOQAN_POLL_INTERVAL: float = float(os.environ.get("TOQAN_POLL_INTERVAL", "3"))
TOQAN_MAX_ATTEMPTS: int = int(os.environ.get("TOQAN_MAX_ATTEMPTS", "20"))

# ─── Trino ─────────────────────────────────────────────────────
TRINO_HOST: str = os.environ.get("TRINO_HOST", "trino-gateway.dataeng.bigdata.olxbr.io")
TRINO_PORT: str = os.environ.get("TRINO_PORT", "443")
TRINO_USER: str = os.environ.get("TRINO_USER", "")
TRINO_PASSWORD: str = os.environ.get("TRINO_PASSWORD", "")
TRINO_CATALOG: str = os.environ.get("TRINO_CATALOG", "hive")
TRINO_SCHEMA: str = os.environ.get("TRINO_SCHEMA", "ods")

# ─── ChromaDB / RAG ───────────────────────────────────────────
CHROMA_PERSIST_DIR: str = os.environ.get("CHROMA_PERSIST_DIR", ".chroma_db")
CHROMA_COLLECTION: str = os.environ.get("CHROMA_COLLECTION", "trino_catalog")
RAG_TOP_K: int = int(os.environ.get("RAG_TOP_K", "10"))

# ─── Logs ──────────────────────────────────────────────────────
AUDIT_LOG_FILE: str = os.environ.get("AUDIT_LOG_FILE", "query_audit_log.json")


def validate() -> list[str]:
    """Retorna lista de problemas de configuração (vazia se tudo OK)."""
    problems = []
    if not TOQAN_API_KEY:
        problems.append("TOQAN_API_KEY não configurada")
    if not TOQAN_BASE_URL:
        problems.append("TOQAN_BASE_URL não configurada")
    if not TRINO_HOST:
        problems.append("TRINO_HOST não configurado")
    return problems
