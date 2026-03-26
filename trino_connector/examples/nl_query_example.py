"""Exemplo de uso: consulta em linguagem natural ao Trino via Gemini.

Pré-requisitos:
    pip install google-genai
    $env:GEMINI_API_KEY = "sua-chave"          # https://aistudio.google.com/app/apikey
    $env:TRINO_USER     = "seu.usuario"
    $env:TRINO_PASSWORD  = "sua_senha"

Uso:
    python examples/nl_query_example.py
"""

from trino_connector.credenciais import load_credentials
from trino_connector.trino_connect import TrinoClient
from trino_connector.nl_query import ask, detect_backend


def main():
    # 0. Verificar configuração do Gemini
    print(f"Backend: {detect_backend()}")

    # 1. Conectar ao Trino
    user, pwd = load_credentials()
    client = TrinoClient(host="trino-gateway.dataeng.bigdata.olxbr.io")
    client.connect(user, pwd)

    try:
        # 2. Fazer uma pergunta — auto-descobre tabelas!
        pergunta = input("💬 O que você quer saber? ")

        # Sem precisar especificar tabelas — a IA descobre sozinha.
        # Opcionalmente, limite por catálogos para ser mais rápido:
        df = ask(pergunta, client, catalogs=["ods"])

        # Ou, se você souber exatamente as tabelas:
        # tables = [{"catalog": "ods", "schema": "public", "table": "audience_portals"}]
        # df = ask(pergunta, client, tables)

        if df is not None:
            print("\n📊 Resultado:")
            print(df.to_string(index=False))
    finally:
        client.close()


if __name__ == "__main__":
    main()
