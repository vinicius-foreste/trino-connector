"""Teste rápido de conexão com o Toqan.

Roda isoladamente — não precisa do Trino.
Útil para validar API key, URL e autenticação.

Uso:
  $env:TOQAN_API_KEY = 'sua-chave'
  $env:TOQAN_BASE_URL = 'https://api.toqan.ai/api'
  $env:TOQAN_VERIFY_SSL = 'false'  # se necessário
  python teste_toqan.py
"""

import os
import sys

def main():
    print("=" * 50)
    print("  Teste de conexão com Toqan")
    print("=" * 50)

    # Verificar variáveis
    key = os.environ.get("TOQAN_API_KEY")
    url = os.environ.get("TOQAN_BASE_URL")

    if not key:
        print("\n❌ TOQAN_API_KEY não configurada")
        print("   $env:TOQAN_API_KEY = 'sua-chave'")
        return
    if not url:
        print("\n❌ TOQAN_BASE_URL não configurada")
        print("   $env:TOQAN_BASE_URL = 'https://api.toqan.ai/api'")
        return

    masked = key[:4] + "..." + key[-4:] if len(key) > 8 else "***"
    print(f"\n  API Key:  {masked}")
    print(f"  Base URL: {url}")
    print(f"  Model:    {os.environ.get('TOQAN_MODEL', 'claude-sonnet-4-5 (padrão)')}")
    print(f"  Auth:     {os.environ.get('TOQAN_AUTH_TYPE', 'bearer (padrão)')}")
    print(f"  SSL:      verify={os.environ.get('TOQAN_VERIFY_SSL', 'true (padrão)')}")

    # Testar chamada simples
    print("\n⏳ Enviando pergunta de teste: 'Diga apenas: OK'...")

    try:
        import trino_connector.toqan_backend as toqan_backend
        response = toqan_backend.call(
            [{"role": "user", "content": "Responda apenas com a palavra: OK"}],
        )
        print(f"\n✅ Toqan respondeu: {response}")
        print("\n🎉 Conexão funcionando! Você pode usar:")
        print("   python cli.py ask 'sua pergunta' -t catalog.schema.tabela")
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        print("\nDicas de debug:")
        print("  1. Verifique se a API key está correta e ativa")
        print("  2. Tente outro tipo de autenticação:")
        print("     $env:TOQAN_AUTH_TYPE = 'x-api-key'")
        print("     $env:TOQAN_AUTH_TYPE = 'api-key'")
        print("  3. Verifique se precisa de VPN")
        print("  4. Para SSL: $env:TOQAN_VERIFY_SSL = 'false'")

        # Tenta mostrar o corpo da resposta para mais detalhes
        if hasattr(e, 'response') and e.response is not None:
            print(f"\n  Status: {e.response.status_code}")
            try:
                print(f"  Body:   {e.response.text[:500]}")
            except Exception:
                pass


if __name__ == "__main__":
    main()
