import os
import builtins
import types

import pytest

import trino_connector.credenciais as credenciais


def test_load_credentials_from_env(monkeypatch):
    monkeypatch.setenv('TRINO_USER', 'env_user')
    monkeypatch.setenv('TRINO_PASSWORD', 'env_pass')

    user, pwd = credenciais.load_credentials()

    assert user == 'env_user'
    assert pwd == 'env_pass'


def test_load_credentials_from_keyring(monkeypatch):
    monkeypatch.setenv('TRINO_USER', 'env_user2')
    monkeypatch.delenv('TRINO_PASSWORD', raising=False)

    class FakeKeyring:
        def get_password(self, service, user):
            assert service == 'trino'
            assert user == 'env_user2'
            return 'kr_pass'

    monkeypatch.setattr(credenciais, 'keyring', FakeKeyring())

    user, pwd = credenciais.load_credentials()

    assert user == 'env_user2'
    assert pwd == 'kr_pass'


def test_load_credentials_interactive(monkeypatch):
    monkeypatch.delenv('TRINO_USER', raising=False)
    monkeypatch.delenv('TRINO_PASSWORD', raising=False)

    monkeypatch.setattr(builtins, 'input', lambda prompt='': 'input_user')
    monkeypatch.setattr(credenciais, 'getpass', lambda prompt='': 'input_pass')

    user, pwd = credenciais.load_credentials()

    assert user == 'input_user'
    assert pwd == 'input_pass'
