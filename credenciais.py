"""Helpers para carregar credenciais do Trino com suporte a .env (dev).

Fluxo de prioridade:
1. Variáveis de ambiente (`TRINO_USER`, `TRINO_PASSWORD`) — carregadas automaticamente se
   houver um `.env` e `python-dotenv` estiver instalado.
2. `keyring` (opcional) — recupera senha armazenada para um usuário.
3. Prompt interativo (`input` + `getpass`).

Use `.env` apenas em desenvolvimento; não commite o arquivo.
"""

from __future__ import annotations

import os
from getpass import getpass
from typing import Tuple

try:
    # Carrega .env automaticamente se python-dotenv estiver instalado (útil em dev)
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    load_dotenv = None

try:
    # keyring integra com o cofre do sistema (Windows Credential Manager, macOS Keychain, etc.)
    import keyring
except Exception:
    keyring = None


def load_credentials() -> Tuple[str, str]:
    """Retorna (user, password).

    Comportamento:
    - Lê `TRINO_USER`/`TRINO_PASSWORD` do ambiente (ex.: export TRINO_USER=...)
    - Se `TRINO_USER` estiver definido e `TRINO_PASSWORD` ausente, tenta recuperar via `keyring`.
    - Caso contrário, solicita `input()` para usuário e `getpass()` para senha.

    Observações explicativas:
    - `os.environ.get("VAR")` retorna o valor da variável de ambiente `VAR` ou `None` se não existir.
    - `keyring` é opcional; fornece integração segura com o keychain do SO.
    """
    user = os.environ.get("TRINO_USER")
    pwd = os.environ.get("TRINO_PASSWORD")

    # Se ambos vieram do ambiente, retornamos imediatamente
    if user and pwd:
        return user, pwd

    # Se user definido mas senha não, tentamos keyring (se disponível)
    if keyring and user and not pwd:
        try:
            stored = keyring.get_password("trino", user)
            if stored:
                return user, stored
        except Exception:
            # não falha por keyring, apenas continua para fallback interativo
            pass

    # Fallback interativo
    if not user:
        user = input("Digite seu usuário (ou e-mail): ")
    if not pwd:
        pwd = getpass("Digite sua senha: ")

    return user, pwd


def store_password_keyring(user: str, password: str) -> bool:
    """Armazena a senha no keyring do sistema. Retorna True se sucesso."""
    if not keyring:
        return False
    try:
        keyring.set_password("trino", user, password)
        return True
    except Exception:
        return False


__all__ = ["load_credentials", "store_password_keyring"]
