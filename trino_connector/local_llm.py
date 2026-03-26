"""Backend LLM local usando llama-cpp-python (modelos GGUF).

Permite rodar text-to-SQL sem depender de APIs externas.
Funciona com qualquer modelo GGUF compatível (ex: CodeLlama, SQLCoder, Mistral).

Uso:
  1. Baixe um modelo GGUF (ex: sqlcoder-7b-2.Q4_K_M.gguf)
  2. Configure a variável de ambiente LOCAL_MODEL_PATH ou passe via CLI:
       $env:LOCAL_MODEL_PATH = 'C:\\models\\sqlcoder-7b-2.Q4_K_M.gguf'
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_llm_instance = None


def is_available() -> bool:
    """Retorna True se llama-cpp-python está instalado."""
    try:
        import llama_cpp  # noqa: F401
        return True
    except ImportError:
        return False


def _get_model_path(model_path: Optional[str] = None) -> Optional[str]:
    """Retorna o caminho do modelo GGUF."""
    return model_path or os.environ.get("LOCAL_MODEL_PATH")


def _load_model(model_path: str):
    """Carrega o modelo GGUF (singleton)."""
    global _llm_instance
    if _llm_instance is not None:
        return _llm_instance

    from llama_cpp import Llama

    logger.info("Carregando modelo GGUF: %s", model_path)
    _llm_instance = Llama(
        model_path=model_path,
        n_ctx=4096,
        n_threads=os.cpu_count() or 4,
        verbose=False,
    )
    logger.info("Modelo carregado com sucesso.")
    return _llm_instance


def _complete(
    prompt: str,
    *,
    model_path: str,
    max_tokens: int = 1024,
    temperature: float = 0.0,
    stop: Optional[list[str]] = None,
) -> str:
    """Gera texto usando o modelo GGUF local."""
    llm = _load_model(model_path)
    output = llm(
        prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        stop=stop or ["```", "\n\n\n"],
        echo=False,
    )
    return output["choices"][0]["text"].strip()


def _chat_complete(
    messages: list[dict],
    *,
    model_path: str,
    max_tokens: int = 1024,
    temperature: float = 0.0,
) -> str:
    """Gera texto usando a API de chat do llama-cpp-python."""
    llm = _load_model(model_path)
    try:
        response = llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response["choices"][0]["message"]["content"].strip()
    except Exception:
        # Fallback: converte messages em prompt simples
        prompt = _messages_to_prompt(messages)
        return _complete(prompt, model_path=model_path, max_tokens=max_tokens, temperature=temperature)


def _messages_to_prompt(messages: list[dict]) -> str:
    """Converte lista de messages em prompt textual simples."""
    parts = []
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if role == "system":
            parts.append(f"### System:\n{content}\n")
        elif role == "user":
            parts.append(f"### User:\n{content}\n")
        elif role == "assistant":
            parts.append(f"### Assistant:\n{content}\n")
    parts.append("### Assistant:\n")
    return "\n".join(parts)


def generate_sql(
    question: str,
    schema_context: str,
    system_prompt: str,
    *,
    model_path: Optional[str] = None,
) -> str:
    """Gera SQL a partir de pergunta em linguagem natural usando modelo GGUF local."""
    path = _get_model_path(model_path)
    if not path:
        raise RuntimeError("Caminho do modelo GGUF não configurado (LOCAL_MODEL_PATH).")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": (
            f"Schema das tabelas disponíveis:\n{schema_context}\n\n"
            f"Pergunta: {question}"
        )},
    ]

    sql = _chat_complete(messages, model_path=path)

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
    model_path: Optional[str] = None,
) -> list[str]:
    """Usa modelo GGUF local para selecionar tabelas relevantes."""
    path = _get_model_path(model_path)
    if not path:
        raise RuntimeError("Caminho do modelo GGUF não configurado (LOCAL_MODEL_PATH).")

    tables_text = "\n".join(f"- {t}" for t in all_tables)
    messages = [
        {"role": "system", "content": table_selection_prompt},
        {"role": "user", "content": (
            f"Tabelas disponíveis:\n{tables_text}\n\n"
            f"Pergunta do usuário: {question}"
        )},
    ]

    raw = _chat_complete(messages, model_path=path)

    try:
        start = raw.index("[")
        end = raw.rindex("]") + 1
        selected = json.loads(raw[start:end])
        return [t for t in selected if t in all_tables]
    except (ValueError, json.JSONDecodeError):
        logger.warning("Modelo local retornou resposta inválida para seleção de tabelas: %s", raw)
        return all_tables[:10]


def status(model_path: Optional[str] = None) -> str:
    """Retorna status do backend llama-cpp-python."""
    if not is_available():
        return "local (llama-cpp-python NÃO instalado — pip install llama-cpp-python)"

    path = _get_model_path(model_path)
    if not path:
        return (
            "local (llama-cpp-python instalado, modelo NÃO configurado)\n"
            "  Configure: $env:LOCAL_MODEL_PATH = 'C:\\caminho\\modelo.gguf'\n"
            "  Baixe modelos em: https://huggingface.co/models?search=gguf+sql"
        )

    if not os.path.isfile(path):
        return f"local (arquivo de modelo não encontrado: {path})"

    size_mb = os.path.getsize(path) / (1024 * 1024)
    return f"local (llama-cpp-python OK, modelo: {os.path.basename(path)} [{size_mb:.0f}MB])"


def unload_model():
    """Descarrega o modelo da memória."""
    global _llm_instance
    _llm_instance = None
