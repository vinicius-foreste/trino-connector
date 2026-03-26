"""Example usage of `TrinoClient` and HTTP Bearer preview.

Run examples after setting `TRINO_HOST` and credentials (env/keyring or `TRINO_BEARER_TOKEN`).

These are small, safe preview helpers — useful for local testing and docs.
"""

from __future__ import annotations

import os
import time
from typing import Optional

import pandas as pd
import requests

from trino_connector.credenciais import load_credentials
from trino_connector.trino_connect import TrinoClient


def preview_with_trinoclient(host: str, table: str, limit: int = 10) -> pd.DataFrame:
    """Preview using the pyhive-based `TrinoClient`.

    host: host[:port] or full host (e.g. 'trino.example.com')
    table: fully-qualified table name `catalog.schema.table`
    """
    user, pwd = load_credentials()
    client = TrinoClient(host=host)
    try:
        client.connect(user, pwd)
        query = f"SELECT * FROM {table} LIMIT {limit}"
        df = client.execute(query)
        print(df.head())
        return df
    finally:
        client.close()


def _follow_next_uri(resp, headers) -> pd.DataFrame:
    while True:
        j = resp.json()
        if "data" in j and j["data"]:
            cols = [c.get("name") for c in j.get("columns", [])] if j.get("columns") else None
            return pd.DataFrame(j["data"], columns=cols)
        if j.get("nextUri"):
            time.sleep(0.2)
            resp = requests.get(j["nextUri"], headers=headers, timeout=10)
            resp.raise_for_status()
            continue
        return pd.DataFrame()


def preview_with_bearer(host: str, table: str, limit: int = 10, bearer: Optional[str] = None) -> pd.DataFrame:
    """Preview using the Trino HTTP API with a Bearer token.

    Use this when you have a service token and prefer not to use a username/password.
    """
    bearer = bearer or os.environ.get("TRINO_BEARER_TOKEN")
    if not bearer:
        raise RuntimeError("TRINO_BEARER_TOKEN is not set")

    if host.startswith("http://") or host.startswith("https://"):
        base = host.rstrip("/")
    else:
        base = f"https://{host.rstrip('/')}"

    headers = {
        "Authorization": f"Bearer {bearer}",
        "X-Trino-User": os.environ.get("TRINO_USER", "integration"),
        "X-Trino-Source": "examples",
    }

    sql = f"SELECT * FROM {table} LIMIT {limit}"
    url = f"{base}/v1/statement"
    resp = requests.post(url, data=sql, headers=headers, timeout=10)
    resp.raise_for_status()
    return _follow_next_uri(resp, headers)


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Example previews for Trino")
    p.add_argument("host")
    p.add_argument("table")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--method", choices=["client", "bearer"], default="client")
    args = p.parse_args()

    if args.method == "client":
        preview_with_trinoclient(args.host, args.table, args.limit)
    else:
        preview_with_bearer(args.host, args.table, args.limit)
