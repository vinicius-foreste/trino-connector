"""CLI entrypoint for the trino_connector package.

Expõe o console script `trino-connector` com subcomandos:
- ask: consulta em linguagem natural (text-to-SQL via Toqan/Gemini/local)
- chat: modo interativo contínuo
- status: verifica configuração dos backends LLM
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def _cmd_status(args: argparse.Namespace) -> None:
    """Subcomando 'status': verifica qual backend LLM está disponível."""
    from nl_query import detect_backend
    model_path = getattr(args, 'model_path', None)
    print(f"Backend LLM:\n{detect_backend(model_path=model_path)}")


def _cmd_ask(args: argparse.Namespace) -> None:
    """Subcomando 'ask': pergunta em linguagem natural → SQL → resultado."""
    from credenciais import load_credentials
    from trino_connect import TrinoClient
    from nl_query import ask

    host = args.host or os.environ.get("TRINO_HOST", "trino-gateway.dataeng.bigdata.olxbr.io")
    user, pwd = load_credentials()

    client = TrinoClient(host=host)
    client.connect(user, pwd)

    tables = None
    if args.tables:
        tables = [
            {"catalog": t.split(".")[0], "schema": t.split(".")[1], "table": t.split(".")[2]}
            for t in args.tables
        ]

    question = " ".join(args.question) if isinstance(args.question, list) else args.question

    try:
        df = ask(
            question,
            client,
            tables,
            catalogs=args.catalogs,
            model=args.model,
            model_path=getattr(args, 'model_path', None),
            confirm=not args.yes,
            use_cache=not args.no_cache,
        )
        if df is not None:
            print(df.to_string(index=False))
            if args.output:
                df.to_csv(args.output, index=False)
                print(f"\n💾 Resultado salvo em {args.output}")
    finally:
        client.close()


def _cmd_interactive(args: argparse.Namespace) -> None:
    """Subcomando 'chat': modo interativo contínuo."""
    from credenciais import load_credentials
    from trino_connect import TrinoClient
    from nl_query import ask

    host = args.host or os.environ.get("TRINO_HOST", "trino-gateway.dataeng.bigdata.olxbr.io")
    user, pwd = load_credentials()

    client = TrinoClient(host=host)
    client.connect(user, pwd)

    tables = None
    if args.tables:
        tables = [
            {"catalog": t.split(".")[0], "schema": t.split(".")[1], "table": t.split(".")[2]}
            for t in args.tables
        ]

    print("=" * 60)
    print("  Trino AI Assistant — modo interativo")
    print("  Digite sua pergunta ou 'sair' para encerrar.")
    if not tables:
        print("  (auto-descoberta de tabelas ativada)")
    print("=" * 60)

    try:
        while True:
            try:
                question = input("\n💬 Sua pergunta: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not question or question.lower() in ("sair", "exit", "quit"):
                break
            try:
                df = ask(
                    question,
                    client,
                    tables,
                    catalogs=args.catalogs,
                    model=args.model,
                    model_path=getattr(args, 'model_path', None),
                    confirm=not args.yes,
                )
                if df is not None:
                    print(df.to_string(index=False))
            except Exception as exc:
                print(f"\n❌ Erro: {exc}")
    finally:
        client.close()
        print("\n👋 Até mais!")


def main():
    parser = argparse.ArgumentParser(
        prog="trino-connector",
        description="Trino connector CLI com consultas em linguagem natural",
    )
    parser.add_argument("--version", action="store_true", help="Mostra a versão")
    sub = parser.add_subparsers(dest="command")

    # Argumentos compartilhados entre ask e chat
    _shared = argparse.ArgumentParser(add_help=False)
    _shared.add_argument(
        "-t", "--tables", nargs="+",
        help="Tabelas para contexto (formato: catalog.schema.tabela). Se omitido, auto-descobre.",
    )
    _shared.add_argument(
        "-c", "--catalogs", nargs="+",
        help="Catálogos onde buscar tabelas (ex: ods analytics). Se omitido, descobre todos.",
    )
    _shared.add_argument("--host", help="Host do Trino (padrão: TRINO_HOST ou gateway)")
    _shared.add_argument("--model", help="Modelo LLM (ex: claude-sonnet-4-5, gpt-5.3, gemini-2.0-flash). Padrão depende do backend.")
    _shared.add_argument(
        "--model-path",
        help="Caminho para modelo GGUF local (ou $env:LOCAL_MODEL_PATH)",
    )
    _shared.add_argument("-y", "--yes", action="store_true", help="Executa sem pedir confirmação")

    # --- status ---
    status_p = sub.add_parser("status", help="Verifica qual backend LLM está disponível", parents=[_shared])
    status_p.set_defaults(func=_cmd_status)

    # --- ask ---
    ask_p = sub.add_parser("ask", help="Faz uma pergunta em linguagem natural", parents=[_shared])
    ask_p.add_argument("question", nargs="+", help="Pergunta em linguagem natural")
    ask_p.add_argument("-o", "--output", help="Salva resultado em CSV")
    ask_p.add_argument("--no-cache", action="store_true", help="Não usa cache de schema")
    ask_p.set_defaults(func=_cmd_ask)

    # --- chat (interativo) ---
    chat_p = sub.add_parser("chat", help="Modo interativo — faça várias perguntas", parents=[_shared])
    chat_p.set_defaults(func=_cmd_interactive)

    args = parser.parse_args()

    if args.version:
        print("trino_connector 0.1.0")
        return

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()