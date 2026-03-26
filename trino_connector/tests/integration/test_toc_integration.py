"""Integration tests for DataShare / Trino Table-of-Contents (TOC).

These tests are gated and will be skipped unless you explicitly enable
them by setting the environment variable `TRINO_INTEGRATION=1`.

Usage (local):

PowerShell:
  $env:TRINO_INTEGRATION='1'; $env:TRINO_HOST='your-trino-host'; python -m pytest tests/integration -q

Linux/macOS:
  TRINO_INTEGRATION=1 TRINO_HOST=your-trino-host python -m pytest tests/integration -q

Environment variables used:
- `TRINO_INTEGRATION` — enable integration tests when set to '1'
- `TRINO_HOST` — host (or host:port) of the Trino gateway
- `TRINO_USER` / `TRINO_PASSWORD` or `TRINO_BEARER_TOKEN` — credentials (use `cred_report.py` to inspect)

The test performs a lightweight query against `information_schema.tables` and
verifies a small preview can be retrieved. Keep these tests small to avoid
heavy load and leaking credentials in CI logs.
"""

import os

import pytest

import pandas as pd
import requests
import time

from trino_connector.trino_connect import TrinoClient
from trino_connector.credenciais import load_credentials


def _run_query_via_trino_http(host: str, sql: str, bearer: str, user: str = "integration") -> pd.DataFrame:
  """Run a SQL statement against Trino HTTP API using a Bearer token.

  This follows `nextUri` links until rows are returned or there is no more data.
  """
  # normalize host to include scheme
  if host.startswith("http://") or host.startswith("https://"):
    base = host.rstrip("/")
  else:
    base = f"https://{host.rstrip('/') }"

  headers = {
    "Authorization": f"Bearer {bearer}",
    "X-Trino-User": user,
    "X-Trino-Source": "dataeng-trino-api",
  }

  # initial POST
  url = f"{base}/v1/statement"
  resp = requests.post(url, data=sql, headers=headers, timeout=10)
  resp.raise_for_status()

  # follow nextUri until we get data or exhaust
  while True:
    j = resp.json()
    if "data" in j and j["data"]:
      cols = [c.get("name") for c in j.get("columns", [])] if j.get("columns") else None
      return pd.DataFrame(j["data"], columns=cols)
    if j.get("nextUri"):
      next_uri = j["nextUri"]
      # poll nextUri
      time.sleep(0.2)
      resp = requests.get(next_uri, headers=headers, timeout=10)
      resp.raise_for_status()
      continue
    # no data and no nextUri -> empty result
    return pd.DataFrame()


@pytest.mark.integration
def test_toc_preview():
  if os.environ.get("TRINO_INTEGRATION") != "1":
    pytest.skip("Integration tests disabled — set TRINO_INTEGRATION=1 to enable")

  host = os.environ.get("TRINO_HOST")
  assert host, "Please set TRINO_HOST to run integration tests"

  # prefer bearer token when provided (safer for CI/service accounts)
  bearer = os.environ.get("TRINO_BEARER_TOKEN")
  if bearer:
    df = _run_query_via_trino_http(
      host,
      "SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema') LIMIT 5",
      bearer=bearer,
      user=os.environ.get("TRINO_USER", "integration"),
    )
    assert df is not None
    assert not df.empty
    assert "table_name" in df.columns or (df.shape[1] >= 2)
    return

  # fallback to pyhive-based client using env/keyring creds
  user, pwd = load_credentials()

  client = TrinoClient(host=host,source="dataeng-trino-api")
  try:
    client.connect(user, pwd)

    query = "SELECT * FROM ods.ad WHERE year=2019 AND month=12 AND day=25 LIMIT 5"
    df = client.execute(query)

    assert df is not None
    assert not df.empty
    assert "ad_id_pk" in df.columns
  finally:
    client.close()
