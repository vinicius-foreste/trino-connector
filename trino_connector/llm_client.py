"""Cliente LLM — chama o Toqan para gerar SQL a partir de linguagem natural.

Envia o dicionário de dados (YAML) + pergunta do usuário para o Toqan
e recebe de volta um JSON com sql_query e lineage.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Optional

import requests
import urllib3

import config

logger = logging.getLogger(__name__)

# ─── System Prompt ────────────────────────────────────────────────

SYSTEM_PROMPT = """\
Você é um especialista em Trino SQL.

Baseie-se APENAS neste dicionário de dados para responder:
{data_dictionary}

Regras estritas:
1. Gere SOMENTE queries SELECT. Nunca gere INSERT, UPDATE, DELETE, DROP, ALTER, CREATE.
2. Use nomes completos de tabelas (catalog.schema.tabela).
3. Se a pergunta implicar em ordenação (ex: maiores, top 10, mais recentes, ordem alfabética), inclua nativamente ORDER BY e LIMIT no SQL.
4. Limite a 1000 linhas por padrão, a menos que o usuário peça algo diferente.
5. Use funções de data do Trino (DATE, TIMESTAMP, CURRENT_DATE) quando aplicável.

Retorne ESTRITAMENTE um objeto JSON com estas duas chaves:
- "sql_query": a consulta SQL final
- "lineage": lista de dicionários no formato [{{"table": "catalog.schema.tabela", "columns": ["col1", "col2"]}}]

Não inclua explicações, markdown ou qualquer texto fora do JSON.
"""


def _build_headers() -> dict[str, str]:
    """Monta headers de autenticação."""
    return {
        "accept": "*/*",
        "content-type": "application/json",
        "X-Api-Key": config.TOQAN_API_KEY,
    }


def _clean_response(text: str) -> str:
    """Remove blocos <think>, cercas markdown e whitespace."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = text.replace("```json", "").replace("```", "")
    return text.strip()


def _call_toqan(user_message: str) -> str:
    """Chama a API do Toqan via create_conversation + polling get_answer."""
    base_url = config.TOQAN_BASE_URL.rstrip("/")
    headers = _build_headers()
    verify = config.TOQAN_VERIFY_SSL

    if not verify:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # 1. Criar conversa
    create_url = f"{base_url}/create_conversation"
    payload = {
        "user_message": user_message,
        "agent_name": config.TOQAN_AGENT_NAME,
    }

    resp = requests.post(create_url, json=payload, headers=headers, timeout=120, verify=verify)
    resp.raise_for_status()
    data = resp.json()

    conversation_id = data.get("conversation_id")
    request_id = data.get("request_id")
    if not conversation_id or not request_id:
        raise RuntimeError(f"Resposta inválida do Toqan: {data}")

    # 2. Polling
    answer_url = f"{base_url}/get_answer"
    for attempt in range(config.TOQAN_MAX_ATTEMPTS):
        time.sleep(config.TOQAN_POLL_INTERVAL)

        resp = requests.get(
            answer_url,
            headers=headers,
            params={"conversation_id": conversation_id, "request_id": request_id},
            timeout=120,
            verify=verify,
        )
        resp.raise_for_status()
        answer = resp.json()

        status = str(answer.get("status", "")).lower()
        text = answer.get("answer")

        if text is not None or status in {"completed", "done", "success"}:
            return _clean_response(str(text or ""))

    raise TimeoutError(
        f"Toqan não respondeu após {config.TOQAN_MAX_ATTEMPTS * config.TOQAN_POLL_INTERVAL}s"
    )


def generate(question: str, yaml_context: str) -> dict:
    """Envia pergunta + dicionário de dados ao Toqan e retorna JSON parseado.

    Args:
        question: pergunta do usuário em linguagem natural.
        yaml_context: dicionário de dados em YAML (gerado pelo retriever).

    Returns:
        Dict com chaves "sql_query" e "lineage".

    Raises:
        ValueError: se a resposta não for um JSON válido.
        RuntimeError: se falhar a comunicação com o Toqan.
    """
    system = SYSTEM_PROMPT.format(data_dictionary=yaml_context)

    # Monta mensagem combinada (Toqan usa user_message único)
    user_message = (
        f"[INSTRUCOES]\n{system}\n\n"
        f"[PERGUNTA]\n{question}"
    )

    raw = _call_toqan(user_message)

    # Parse do JSON
    try:
        # Tenta extrair JSON do texto (pode vir com lixo antes/depois)
        json_start = raw.index("{")
        json_end = raw.rindex("}") + 1
        result = json.loads(raw[json_start:json_end])
    except (ValueError, json.JSONDecodeError) as exc:
        logger.error("Resposta do Toqan não é JSON válido: %s", raw[:500])
        raise ValueError(
            f"A IA retornou uma resposta que não é JSON válido.\n"
            f"Resposta bruta: {raw[:300]}"
        ) from exc

    # Valida presença das chaves
    if "sql_query" not in result:
        raise ValueError(f"Resposta da IA não contém 'sql_query': {result}")

    if "lineage" not in result:
        result["lineage"] = []

    return result


def validate_sql(sql: str) -> None:
    """Rejeita operações de escrita."""
    dangerous = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "GRANT", "REVOKE"}
    first_word = sql.lstrip().split()[0].upper() if sql.strip() else ""
    if first_word in dangerous:
        raise ValueError(
            f"Query rejeitada: operação '{first_word}' não é permitida. "
            "Apenas consultas SELECT são aceitas."
        )
