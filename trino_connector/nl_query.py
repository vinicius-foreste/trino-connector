"""Módulo de consulta em linguagem natural (Text-to-SQL) usando LLM.

Converte perguntas em português/inglês para SQL Trino, executa e
retorna os resultados como DataFrame.

Backends suportados (auto-detectados em ordem de prioridade):
  1. Toqan (gateway corporativo) — requer TOQAN_API_KEY + TOQAN_BASE_URL
  2. Gemini (API Google)         — requer GEMINI_API_KEY
  3. Local (llama-cpp-python)    — requer LOCAL_MODEL_PATH
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

import pandas as pd

from trino_connect import TrinoClient
from schema_discovery import build_schema_context, discover_all_tables

logger = logging.getLogger(__name__)

# ─── Backend ativo ──────────────────────────────────────────────
# "toqan" | "gemini" | "local" | None
_active_backend: Optional[str] = None

SYSTEM_PROMPT = """\
Você é um assistente especialista em SQL Trino. Seu trabalho é:
1. Receber uma pergunta em linguagem natural.
2. Receber o schema das tabelas disponíveis.
3. Gerar APENAS a query SQL Trino que responde a pergunta.

Regras:
- Retorne SOMENTE o SQL, sem explicações, sem markdown, sem ```sql.
- Use nomes completos de tabelas (catalog.schema.tabela).
- Use aspas duplas para colunas com espaços ou caracteres especiais apenas se necessário.
- Quando a pergunta mencionar datas, use funções de data do Trino (DATE, TIMESTAMP, etc).
- Limite os resultados a 1000 linhas por padrão, a menos que o usuário peça algo diferente.
- Gere SQL somente de leitura (SELECT). Nunca gere INSERT, UPDATE, DELETE, DROP, etc.
- Se não conseguir gerar a query, retorne: -- ERRO: <motivo>
"""

TABLE_SELECTION_PROMPT = """\
Você recebe uma lista de tabelas disponíveis em um banco Trino e uma pergunta do usuário.
Selecione APENAS as tabelas relevantes para responder a pergunta.

Retorne SOMENTE um JSON array com os nomes completos das tabelas selecionadas.
Exemplo: ["catalog.schema.tabela1", "catalog.schema.tabela2"]

Se nenhuma tabela parecer relevante, retorne um array com as que mais se aproximam.
Retorne no máximo 10 tabelas. Não inclua explicações, apenas o JSON array.
"""

# ─── Backend Gemini ─────────────────────────────────────────────

DEFAULT_MODEL = "gemini-2.0-flash"


def _get_api_key(api_key: Optional[str] = None) -> str:
    """Retorna a API key do Gemini, checando parâmetro e variáveis de ambiente."""
    key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError(
            "API key do Gemini não encontrada.\n"
            "Configure uma das variáveis de ambiente:\n"
            "  $env:GEMINI_API_KEY = 'sua-chave'\n"
            "  $env:GOOGLE_API_KEY = 'sua-chave'\n"
            "\n"
            "Obtenha sua chave em: https://aistudio.google.com/app/apikey"
        )
    return key


def _call_gemini(
    messages: list[dict],
    *,
    api_key: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.0,
) -> str:
    """Chama a API do Google Gemini e retorna o texto da resposta."""
    from google import genai

    client = genai.Client(api_key=_get_api_key(api_key))

    # Converte formato OpenAI-style messages → Gemini contents
    # Gemini usa system_instruction separado e contents para user/model
    system_text = None
    contents = []
    for msg in messages:
        role = msg["role"]
        text = msg["content"]
        if role == "system":
            system_text = text
        elif role == "user":
            contents.append({"role": "user", "parts": [{"text": text}]})
        elif role == "assistant":
            contents.append({"role": "model", "parts": [{"text": text}]})

    config = {
        "temperature": temperature,
        "max_output_tokens": 2048,
    }
    if system_text:
        config["system_instruction"] = system_text

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=config,
    )
    return response.text.strip()


def _detect_active_backend(model_path: Optional[str] = None) -> str:
    """Detecta o melhor backend disponível. Retorna 'toqan', 'gemini', 'local', ou levanta erro."""
    global _active_backend

    # 1. Toqan (gateway corporativo — prioridade máxima)
    try:
        import toqan_backend
        if toqan_backend.is_available():
            _active_backend = "toqan"
            return "toqan"
    except ImportError:
        pass

    # 2. Gemini
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if key:
        _active_backend = "gemini"
        return "gemini"

    # 3. Local llama-cpp-python
    try:
        import local_llm
        if local_llm.is_available():
            path = model_path or os.environ.get("LOCAL_MODEL_PATH")
            if path and os.path.isfile(path):
                _active_backend = "local"
                return "local"
    except ImportError:
        pass

    raise RuntimeError(
        "Nenhum backend LLM disponível.\n"
        "Configure uma das opções:\n"
        "  1. Toqan:  $env:TOQAN_API_KEY = 'chave'  +  $env:TOQAN_BASE_URL = 'url'\n"
        "  2. Gemini: $env:GEMINI_API_KEY = 'sua-chave'\n"
        "  3. Local:  $env:LOCAL_MODEL_PATH = 'C:\\caminho\\modelo.gguf'"
    )


def detect_backend(model_path: Optional[str] = None) -> str:
    """Retorna string descritiva do status de todos os backends."""
    lines = []

    # Toqan
    try:
        import toqan_backend
        lines.append(f"  toqan:  {toqan_backend.status()}")
    except ImportError:
        lines.append("  toqan:  módulo não encontrado")

    # Gemini
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if key:
        masked = key[:4] + "..." + key[-4:] if len(key) > 8 else "***"
        lines.append(f"  gemini: OK (API key: {masked})")
    else:
        lines.append("  gemini: API key NÃO configurada")

    # Local llama-cpp-python
    try:
        import local_llm
        lines.append(f"  local:  {local_llm.status(model_path)}")
    except ImportError:
        lines.append("  local:  llama-cpp-python NÃO instalado")

    # Qual está ativo?
    try:
        active = _detect_active_backend(model_path)
        lines.insert(0, f"Backend ativo: {active}")
    except RuntimeError:
        lines.insert(0, "Backend ativo: NENHUM (configure Toqan, Gemini ou modelo local)")

    return "\n".join(lines)


def select_relevant_tables(
    question: str,
    all_tables: list[str],
    *,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    model_path: Optional[str] = None,
) -> list[str]:
    """Usa o LLM para selecionar tabelas relevantes a partir da pergunta."""
    backend = _detect_active_backend(model_path)

    if backend == "toqan":
        import toqan_backend
        return toqan_backend.select_relevant_tables(
            question, all_tables, TABLE_SELECTION_PROMPT, model=model,
        )

    if backend == "local":
        import local_llm
        return local_llm.select_relevant_tables(
            question, all_tables, TABLE_SELECTION_PROMPT, model_path=model_path,
        )

    # Gemini
    tables_text = "\n".join(f"- {t}" for t in all_tables)
    user_content = (
        f"Tabelas disponíveis:\n{tables_text}\n\n"
        f"Pergunta do usuário: {question}"
    )
    messages = [
        {"role": "system", "content": TABLE_SELECTION_PROMPT},
        {"role": "user", "content": user_content},
    ]

    raw = _call_gemini(messages, api_key=api_key, model=model or DEFAULT_MODEL)

    # Extrai JSON do response (pode vir com texto extra)
    try:
        start = raw.index("[")
        end = raw.rindex("]") + 1
        selected = json.loads(raw[start:end])
        # Filtra apenas tabelas que realmente existem na lista
        return [t for t in selected if t in all_tables]
    except (ValueError, json.JSONDecodeError):
        logger.warning("LLM retornou resposta inválida para seleção de tabelas: %s", raw)
        return all_tables[:10]  # fallback: primeiras 10


def generate_sql(
    question: str,
    schema_context: str,
    *,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    model_path: Optional[str] = None,
) -> str:
    """Converte uma pergunta em linguagem natural para SQL Trino."""
    backend = _detect_active_backend(model_path)

    if backend == "toqan":
        import toqan_backend
        return toqan_backend.generate_sql(
            question, schema_context, SYSTEM_PROMPT, model=model,
        )

    if backend == "local":
        import local_llm
        return local_llm.generate_sql(
            question, schema_context, SYSTEM_PROMPT, model_path=model_path,
        )

    # Gemini
    user_content = (
        f"Schema das tabelas disponíveis:\n{schema_context}\n\n"
        f"Pergunta: {question}"
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    sql = _call_gemini(messages, api_key=api_key, model=model or DEFAULT_MODEL)

    # Limpa possíveis artefatos de markdown
    if sql.startswith("```"):
        lines = sql.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        sql = "\n".join(lines).strip()

    return sql


def _validate_sql(sql: str) -> None:
    """Validação básica de segurança: rejeita operações de escrita."""
    dangerous = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "GRANT", "REVOKE"}
    first_word = sql.lstrip().split()[0].upper() if sql.strip() else ""
    if first_word in dangerous:
        raise ValueError(
            f"Query rejeitada: operação '{first_word}' não é permitida. "
            "Apenas consultas SELECT são aceitas."
        )


def ask(
    question: str,
    client: TrinoClient,
    tables: Optional[list[dict]] = None,
    *,
    catalogs: Optional[list[str]] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    model_path: Optional[str] = None,
    confirm: bool = True,
    use_cache: bool = True,
) -> Optional[pd.DataFrame]:
    """Fluxo completo: pergunta → descoberta → SQL → execução → resultado."""
    if tables is None:
        # Auto-descoberta
        print("\n🔍 Descobrindo tabelas acessíveis no Trino...")
        all_tables = discover_all_tables(client, catalogs=catalogs, use_cache=use_cache)
        print(f"   Encontradas {len(all_tables)} tabelas.")

        if not all_tables:
            print("❌ Nenhuma tabela encontrada. Verifique suas permissões.")
            return None

        print("🤖 Selecionando tabelas relevantes para sua pergunta...")
        selected = select_relevant_tables(
            question, all_tables, api_key=api_key, model=model, model_path=model_path,
        )
        print(f"   Tabelas selecionadas: {', '.join(selected)}")

        tables = []
        for fqn in selected:
            parts = fqn.split(".")
            if len(parts) == 3:
                tables.append({"catalog": parts[0], "schema": parts[1], "table": parts[2]})
    
    print("\n🔍 Descobrindo schema das tabelas...")
    schema_ctx = build_schema_context(client, tables, use_cache=use_cache)

    print("🤖 Gerando SQL com IA...")
    sql = generate_sql(question, schema_ctx, api_key=api_key, model=model, model_path=model_path)

    if sql.startswith("-- ERRO:"):
        print(f"\n❌ A IA não conseguiu gerar a query:\n{sql}")
        return None

    _validate_sql(sql)

    print(f"\n📝 SQL gerado:\n{'─' * 60}")
    print(sql)
    print(f"{'─' * 60}")

    if confirm:
        resp = input("\n▶ Executar esta query? [S/n]: ").strip().lower()
        if resp and resp not in ("s", "sim", "y", "yes"):
            print("Execução cancelada.")
            return None

    print("\n⏳ Executando query no Trino...")
    df = client.execute(sql)
    print(f"✅ {len(df)} linhas retornadas.\n")
    return df
