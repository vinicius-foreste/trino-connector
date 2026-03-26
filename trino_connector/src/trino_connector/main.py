"""Orquestrador NL2SQL — fluxo completo de pergunta → resposta.

Fluxo:
  1. Pergunta do usuário
  2. Retriever: busca schemas relevantes no ChromaDB (RAG)
  3. LLM Client: envia schema + pergunta ao Toqan → recebe SQL + lineage
  4. Executor: roda SQL no Trino → DataFrame
  5. Logger: salva auditoria

Uso:
    python main.py                           # modo interativo
    python main.py "quantos anúncios em 2024?"  # pergunta direta
    python main.py --status                  # verifica configuração
"""

from __future__ import annotations

import argparse
import sys
import traceback

from trino_connector import config
from trino_connector import retriever
from trino_connector import llm_client
from trino_connector import trino_executor
from trino_connector import query_logger


def ask(question: str, *, confirm: bool = True) -> None:
    """Executa o fluxo completo NL2SQL para uma pergunta."""

    # 1. Busca semântica no ChromaDB
    print("\n🔍 Buscando schemas relevantes no dicionário de dados...")
    hits, yaml_context = retriever.retrieve(question)

    if not hits:
        print("❌ Nenhum schema relevante encontrado. Execute: python indexer.py")
        return

    tables_found = [h["id"] for h in hits]
    print(f"   Tabelas selecionadas ({len(tables_found)}):")
    for t in tables_found:
        dist = next((h["distance"] for h in hits if h["id"] == t), None)
        dist_str = f" (score: {1 - dist:.2f})" if dist is not None else ""
        print(f"     • {t}{dist_str}")

    # 2. Gera SQL via Toqan
    print("\n🤖 Gerando SQL com IA...")
    try:
        result = llm_client.generate(question, yaml_context)
    except ValueError as exc:
        print(f"\n❌ Erro na resposta da IA: {exc}")
        query_logger.log_query(question, "", [], status="error", error=str(exc))
        return
    except Exception as exc:
        print(f"\n❌ Erro ao chamar Toqan: {exc}")
        query_logger.log_query(question, "", [], status="error", error=str(exc))
        return

    sql = result["sql_query"]
    lineage = result.get("lineage", [])

    # 3. Valida SQL (rejeita escrita)
    try:
        llm_client.validate_sql(sql)
    except ValueError as exc:
        print(f"\n❌ {exc}")
        query_logger.log_query(question, sql, lineage, status="error", error=str(exc))
        return

    print(f"\n📝 SQL gerado:\n{'─' * 60}")
    print(sql)
    print(f"{'─' * 60}")

    if lineage:
        print("\n📊 Lineage:")
        for entry in lineage:
            tbl = entry.get("table", "?")
            cols = ", ".join(entry.get("columns", []))
            print(f"     • {tbl} → [{cols}]")

    # 4. Confirmação
    if confirm:
        resp = input("\n▶ Executar esta query? [S/n]: ").strip().lower()
        if resp and resp not in ("s", "sim", "y", "yes", ""):
            print("Execução cancelada.")
            query_logger.log_query(question, sql, lineage, status="cancelled")
            return

    # 5. Executa no Trino
    print("\n⏳ Executando query no Trino...")
    try:
        df = trino_executor.execute(sql)
    except RuntimeError as exc:
        print(f"\n❌ Erro no Trino: {exc}")
        query_logger.log_query(question, sql, lineage, status="error", error=str(exc))
        return

    rows = len(df)
    print(f"✅ {rows} linhas retornadas.\n")
    print(df.head(20).to_string(index=False))

    if rows > 20:
        print(f"\n... ({rows - 20} linhas omitidas. Use -o para salvar completo)")

    # 6. Log de auditoria
    query_logger.log_query(question, sql, lineage, status="success", rows_returned=rows)


def interactive_mode():
    """Modo interativo — várias perguntas em sequência."""
    print("=" * 60)
    print("  NL2SQL — Trino AI Assistant (RAG)")
    print("  Digite sua pergunta ou 'sair' para encerrar.")
    print("=" * 60)

    while True:
        try:
            question = input("\n💬 Sua pergunta: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not question or question.lower() in ("sair", "exit", "quit"):
            break
        try:
            ask(question, confirm=True)
        except Exception as exc:
            print(f"\n❌ Erro: {exc}")
            traceback.print_exc()

    trino_executor.close()
    print("\n👋 Até mais!")


def show_status():
    """Mostra status da configuração."""
    print("=" * 60)
    print("  NL2SQL — Status")
    print("=" * 60)

    # Config
    problems = config.validate()
    if problems:
        print("\n⚠️  Problemas de configuração:")
        for p in problems:
            print(f"   • {p}")
    else:
        print("\n✅ Configuração OK")

    # Toqan
    masked = config.TOQAN_API_KEY[:4] + "..." + config.TOQAN_API_KEY[-4:] if len(config.TOQAN_API_KEY) > 8 else "***"
    print(f"\n  Toqan API Key:  {masked if config.TOQAN_API_KEY else 'NÃO CONFIGURADA'}")
    print(f"  Toqan Base URL: {config.TOQAN_BASE_URL}")
    print(f"  Toqan Agent:    {config.TOQAN_AGENT_NAME}")
    print(f"  Trino Host:     {config.TRINO_HOST}")
    print(f"  Trino Catalog:  {config.TRINO_CATALOG}")

    # ChromaDB
    try:
        import chromadb
        client = chromadb.PersistentClient(path=config.CHROMA_PERSIST_DIR)
        col = client.get_collection(config.CHROMA_COLLECTION)
        count = col.count()
        print(f"\n  ChromaDB:       ✅ {count} tabelas indexadas")
    except Exception:
        print(f"\n  ChromaDB:       ❌ Não indexado (execute: python indexer.py)")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="NL2SQL — Consulta seu Data Lake em linguagem natural",
    )
    parser.add_argument("question", nargs="*", help="Pergunta em linguagem natural")
    parser.add_argument("--status", action="store_true", help="Mostra status da configuração")
    parser.add_argument("-y", "--yes", action="store_true", help="Executa sem confirmação")
    parser.add_argument("-o", "--output", help="Salva resultado em CSV")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.question:
        question = " ".join(args.question)
        ask(question, confirm=not args.yes)
        trino_executor.close()
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
