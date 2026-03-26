"""Small helper to store a Trino password in the OS keyring.

This script uses the `store_password_keyring` helper from `credenciais.py`.
It prompts for the username and password (safely) and writes the password
to the OS keyring under the service name `trino`.

Usage:
  python keyring_store.py

The script will prompt for `TRINO_USER` if not set in the environment.
"""

from __future__ import annotations

import os
from getpass import getpass

from trino_connector.credenciais import store_password_keyring


def main():
    user = os.environ.get("TRINO_USER")
    if not user:
        user = input("Trino user: ")
    pwd = getpass("Password (will be saved to keyring): ")

    ok = store_password_keyring(user, pwd)
    if ok:
        print("Password stored in keyring for user:", user)
    else:
        print("Failed to store password in keyring. Is keyring installed and available?")


if __name__ == "__main__":
    main()
