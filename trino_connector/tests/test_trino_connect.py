import pandas as pd

from trino_connect import TrinoClient


def test_execute_returns_dataframe(monkeypatch):
    class FakeCursor:
        def __init__(self):
            # mimic cursor.description as a sequence of 2-tuples (name, type)
            self.description = [("col1",), ("col2",)]

        def execute(self, query):
            self._q = query

        def fetchall(self):
            return [(1, "a"), (2, "b")]

    class FakeConn:
        def cursor(self):
            return FakeCursor()

    def fake_connect(**kwargs):
        return FakeConn()

    # patch the underlying pyhive connect used by trino_connect.TrinoClient
    monkeypatch.setattr('trino_connect.trino.connect', fake_connect)

    client = TrinoClient(host='example', port='443')
    client.connect(username='u', password='p')
    df = client.execute('SELECT 1')

    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ['col1', 'col2']
    assert df.shape[0] == 2
