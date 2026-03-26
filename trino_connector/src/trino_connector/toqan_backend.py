"""Backend Toqan — gateway corporativo de LLM.

O Toqan é o proxy/gateway de IA corporativo que dá acesso a modelos
como Claude Sonnet 4.5, GPT 5.3, entre outros via API.

Configuração (variáveis de ambiente):
  TOQAN_API_KEY    — chave de API do Toqan (obrigatória)
  TOQAN_BASE_URL   — URL base da API (ex: https://toqan.empresa.com.br/v1)
  TOQAN_MODEL      — modelo padrão (ex: claude-sonnet-4-5, gpt-5.3)

A API do Toqan segue o formato OpenAI-compatible (POST /chat/completions),
que é o padrão da maioria dos gateways corporativos.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-5"


def _get_config(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
) -> tuple[str, str, str]:
    """Retorna (api_key, base_url, model) resolvidos do ambiente."""
    key = api_key or os.environ.get("TOQAN_API_KEY")
    if not key:
        raise RuntimeError(
            "TOQAN_API_KEY não configurada.\n"
            "Configure: $env:TOQAN_API_KEY = 'sua-chave'\n"
            "Solicite sua chave ao time de plataforma."
        )
    url = base_url or os.environ.get("TOQAN_BASE_URL")
    if not url:
        raise RuntimeError(
            "TOQAN_BASE_URL não configurada.\n"
            "Configure: $env:TOQAN_BASE_URL = 'https://toqan.empresa.com.br/v1'\n"
            "Solicite a URL ao time de plataforma."
        )
    mdl = model or os.environ.get("TOQAN_MODEL") or DEFAULT_MODEL
    return key, url, mdl


def is_available() -> bool:
    """Retorna True se as variáveis do Toqan estão configuradas."""
    return bool(
        os.environ.get("TOQAN_API_KEY") and os.environ.get("TOQAN_BASE_URL")
    )


def _get_ssl_verify() -> bool | str:
    """Retorna o valor de verify para requests.

    Suporta:
      TOQAN_CA_BUNDLE  — caminho para certificado CA corporativo (.pem/.crt)
      TOQAN_VERIFY_SSL — 'false' para desabilitar verificação (último recurso)
      REQUESTS_CA_BUNDLE / CURL_CA_BUNDLE — variáveis padrão do sistema
    """
    ca = os.environ.get("TOQAN_CA_BUNDLE") or os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("CURL_CA_BUNDLE")
    if ca:
        return ca
    verify_env = os.environ.get("TOQAN_VERIFY_SSL", "").lower()
    if verify_env in ("false", "0", "no"):
        return False
    return True


def _build_headers(api_key: str) -> dict[str, str]:
    """Monta headers de autenticação para o Toqan."""
    headers = {
        "accept": "*/*",
        "content-type": "application/json",
    }

    # Muitos agentes Toqan usam X-Api-Key por padrão.
    auth_type = os.environ.get("TOQAN_AUTH_TYPE", "x-api-key").lower()
    if auth_type == "bearer":
        headers["Authorization"] = f"Bearer {api_key}"
    elif auth_type == "api-key":
        headers["api-key"] = api_key
    else:
        headers["X-Api-Key"] = api_key

    return headers


def _messages_to_user_message(messages: list[dict]) -> str:
    """Converte mensagens role-based em um único prompt para o endpoint de agente."""
    chunks: list[str] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if not content:
            continue
        if role == "system":
            chunks.append(f"[INSTRUCOES]\n{content}")
        elif role == "assistant":
            chunks.append(f"[CONTEXTO_ASSISTENTE]\n{content}")
        else:
            chunks.append(f"[PERGUNTA]\n{content}")
    return "\n\n".join(chunks)


def _clean_answer_text(text: str) -> str:
    """Remove blocos <think> e cercas markdown comuns da resposta."""
    without_think = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    return without_think.replace("```json", "").replace("```", "").strip()


def _call_agent_conversation_api(
    *,
    base_url: str,
    headers: dict[str, str],
    user_message: str,
    model: str,
    verify: bool | str,
) -> str:
    """Fluxo Toqan por agente: create_conversation + polling get_answer."""
    agent_name = os.environ.get("TOQAN_AGENT_NAME", "GeneralAssistant")
    max_attempts = int(os.environ.get("TOQAN_MAX_ATTEMPTS", "15"))
    poll_interval = float(os.environ.get("TOQAN_POLL_INTERVAL", "3"))

    create_url = f"{base_url.rstrip('/')}/create_conversation"
    create_payload = {
        "user_message": user_message,
        "agent_name": agent_name,
        # Alguns ambientes ignoram esse campo; manter não quebra compatibilidade.
        "model": model,
    }

    create_resp = requests.post(
        create_url,
        json=create_payload,
        headers=headers,
        timeout=120,
        verify=verify,
    )
    create_resp.raise_for_status()
    create_data = create_resp.json()

    conversation_id = create_data.get("conversation_id")
    request_id = create_data.get("request_id")
    if not conversation_id or not request_id:
        raise RuntimeError(f"Resposta Toqan inválida em create_conversation: {create_data}")

    answer_url = f"{base_url.rstrip('/')}/get_answer"
    for _ in range(max_attempts):
        time.sleep(poll_interval)
        answer_resp = requests.get(
            answer_url,
            headers=headers,
            params={"conversation_id": conversation_id, "request_id": request_id},
            timeout=120,
            verify=verify,
        )
        answer_resp.raise_for_status()
        answer_data = answer_resp.json()
        status = str(answer_data.get("status", "")).lower()
        answer_text = answer_data.get("answer")

        if answer_text is not None or status in {"completed", "done", "success"}:
            return _clean_answer_text(str(answer_text or ""))

    raise TimeoutError("Toqan não retornou resposta final dentro do tempo configurado.")


def _call_openai_compatible_api(
    *,
    base_url: str,
    headers: dict[str, str],
    messages: list[dict],
    model: str,
    temperature: float,
    max_tokens: int,
    verify: bool | str,
) -> str:
    """Fluxo OpenAI-compatible: /chat/completions."""
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    resp = requests.post(endpoint, json=payload, headers=headers, timeout=120, verify=verify)
    resp.raise_for_status()
    data = resp.json()
    return _clean_answer_text(data["choices"][0]["message"]["content"].strip())


def call(
    messages: list[dict],
    *,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 2048,
) -> str:
    """Chama a API do Toqan e retorna o texto.

    Suporta dois estilos:
      - `conversation` (padrão): /create_conversation + /get_answer
      - `chat`: /chat/completions
    Configure com `TOQAN_API_STYLE=conversation|chat|auto`.
    """
    import urllib3
    key, url, mdl = _get_config(api_key, base_url, model)
    headers = _build_headers(key)
    api_style = os.environ.get("TOQAN_API_STYLE", "conversation").lower()
    user_message = _messages_to_user_message(messages)

    verify = _get_ssl_verify()
    if verify is False:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    logger.debug("Toqan request style=%s model=%s verify=%s", api_style, mdl, verify)
    if api_style == "conversation":
        return _call_agent_conversation_api(
            base_url=url,
            headers=headers,
            user_message=user_message,
            model=mdl,
            verify=verify,
        )

    if api_style == "chat":
        return _call_openai_compatible_api(
            base_url=url,
            headers=headers,
            messages=messages,
            model=mdl,
            temperature=temperature,
            max_tokens=max_tokens,
            verify=verify,
        )

    # auto: tenta conversation primeiro, depois fallback para chat
    try:
        return _call_agent_conversation_api(
            base_url=url,
            headers=headers,
            user_message=user_message,
            model=mdl,
            verify=verify,
        )
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status in {400, 404, 405}:
            return _call_openai_compatible_api(
                base_url=url,
                headers=headers,
                messages=messages,
                model=mdl,
                temperature=temperature,
                max_tokens=max_tokens,
                verify=verify,
            )
        raise


def generate_sql(
    question: str,
    schema_context: str,
    system_prompt: str,
    *,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """Gera SQL a partir de pergunta em linguagem natural via Toqan."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": (
            f"Schema das tabelas disponíveis:\n{schema_context}\n\n"
            f"Pergunta: {question}"
        )},
    ]

    sql = call(messages, api_key=api_key, base_url=base_url, model=model)

    # Limpa artefatos de markdown
    if sql.startswith("```"):
        lines = sql.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        sql = "\n".join(lines).strip()

    return sql


def select_relevant_tables(
    question: str,
    all_tables: list[str],
    table_selection_prompt: str,
    *,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
) -> list[str]:
    """Usa Toqan para selecionar tabelas relevantes."""
    tables_text = "\n".join(f"- {t}" for t in all_tables)
    messages = [
        {"role": "system", "content": table_selection_prompt},
        {"role": "user", "content": (
            f"Tabelas disponíveis:\n{tables_text}\n\n"
            f"Pergunta do usuário: {question}"
        )},
    ]

    raw = call(messages, api_key=api_key, base_url=base_url, model=model)

    try:
        start = raw.index("[")
        end = raw.rindex("]") + 1
        selected = json.loads(raw[start:end])
        return [t for t in selected if t in all_tables]
    except (ValueError, json.JSONDecodeError):
        logger.warning("Toqan retornou resposta inválida para seleção: %s", raw)
        return all_tables[:10]


def status() -> str:
    """Retorna status de configuração do Toqan."""
    key = os.environ.get("TOQAN_API_KEY")
    url = os.environ.get("TOQAN_BASE_URL")
    mdl = os.environ.get("TOQAN_MODEL") or DEFAULT_MODEL
    auth = os.environ.get("TOQAN_AUTH_TYPE", "x-api-key")
    style = os.environ.get("TOQAN_API_STYLE", "conversation")

    if not key:
        return (
            "toqan: API key NÃO configurada\n"
            "    Configure: $env:TOQAN_API_KEY = 'sua-chave'"
        )
    if not url:
        masked = key[:4] + "..." + key[-4:] if len(key) > 8 else "***"
        return (
            f"toqan: API key OK ({masked}), mas TOQAN_BASE_URL NÃO configurada\n"
            "    Configure: $env:TOQAN_BASE_URL = 'https://toqan.empresa.com.br/v1'"
        )

    masked = key[:4] + "..." + key[-4:] if len(key) > 8 else "***"
    return f"toqan: OK (key: {masked}, url: {url}, model: {mdl}, auth: {auth}, style: {style})"
