# trino_connector — utilitários para Trino (DataShare)

Resumo
- Conjunto pequeno e reutilizável de utilitários para conectar, diagnosticar e executar consultas no gateway Trino (DataShare).
- Contém:
	- diagnósticos de rede/HTTP (`diagnostics.py`),
	- carregamento seguro de credenciais (`credenciais.py`),
	- wrapper `TrinoClient` para executar queries e retornar `pandas.DataFrame` (`trino_connect.py`),
	- script interativo de troubleshooting (`teste_trino.py`).

Arquivos principais
- [teste_trino.py](teste_trino.py): script de troubleshooting — probes `/v1/info` e `/v1/statement`, tenta conexão via `pyhive`, fallback automático em caso de `PERMISSION_DENIED` e execução de query de exemplo quando `TRINO_RUN_EXAMPLE` está ativo.
- [diagnostics.py](diagnostics.py): utilitários `tcp_probe()`, `http_head_probe()` e `summarize_probe()` para distinguir problemas de rede, TLS e autenticação.
- [credenciais.py](credenciais.py): carrega credenciais por `env` → `keyring` → prompt interativo; helper para gravar senha no keyring.
- [trino_connect.py](trino_connect.py): `TrinoClient` com política simples de retry e retorno em `pandas.DataFrame`.
- [.env.example](.env.example): modelo de variáveis de ambiente.
- [requirements.txt](requirements.txt): dependências do projeto (inclui linters e test tools).

Instalação
1. Crie e ative um ambiente virtual (Windows PowerShell):
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```
2. Instale dependências:
```powershell
pip install -r requirements.txt
```

Configuração (variáveis)
- Use `.env` local (a partir de `.env.example`) ou defina variáveis no ambiente:
	- `TRINO_HOST`, `TRINO_PORT`, `TRINO_PROTOCOL` (https/http)
	- `TRINO_USER`, `TRINO_PASSWORD` (ou use `keyring`)
	- `TRINO_BEARER_TOKEN` (se usar Bearer tokens)
	- `TRINO_SOURCE`, `TRINO_SAFE_COLUMNS`, `TRINO_RUN_EXAMPLE`

Execução rápida
- Rodar o script de diagnóstico/teste:
```powershell
$env:TRINO_HOST = "trino-gateway.dataeng.bigdata.olxbr.io"
$env:TRINO_USER = "seu_usuario"
python teste_trino.py
```
- Para executar a query de exemplo (antigo `test.py`), defina `TRINO_RUN_EXAMPLE=1`.

Testes
- Os testes usam `pytest` e estão em `tests/`. Para rodar:
```powershell
pytest -q
```

Lint
- O projeto inclui `ruff` e `flake8`. Para rodar localmente:
```powershell
ruff check .
flake8 .
```

CI
- Workflow de CI (GitHub Actions) fica em `.github/workflows/ci.yml` — roda lint e testes em pushes/PRs.

Segurança
- Nunca commite `.env` com segredos. Use `.env.example` apenas como modelo.
- Prefira `keyring` para armazenar senhas localmente: `python -c "import keyring; keyring.set_password('trino','usuario','senha')"`.

Boas práticas antes de push
- Verifique com `ruff`/`flake8` e rode `pytest`.
- Confirme que não há arquivos sensíveis no commit (ex.: `git status --porcelain` e `git diff --staged`).

Contribuição
- Abra uma branch por feature/cleanup. Faça PRs pequenos e inclua testes para novas funcionalidades.

Ajuda adicional
- Posso: adicionar exemplos de uso do `TrinoClient`, criar scripts de inicialização (`make_venv.ps1`) ou configurar o CI para falhar quando o lint detectar problemas (atualmente o workflow apenas reporta). Diga qual prefere.

Credential report
-----------------
Um utilitário simples para inspecionar rapidamente onde credenciais estão configuradas e receber recomendações:

- `cred_report.py` — gera um relatório legível indicando:
	- se `TRINO_USER`, `TRINO_PASSWORD` e `TRINO_BEARER_TOKEN` estão definidos no ambiente;
	- se o `keyring` está disponível e se existe senha armazenada para o usuário configurado;
	- recomendações rápidas (usar `keyring`, rotacionar tokens, etc.).

Exemplo de uso:
```powershell
python cred_report.py
```

O script é apenas informativo e não envia credenciais a lugar nenhum. Recomenda-se rodá-lo localmente antes de preparar commits/pushes para confirmar que não há segredos em variáveis de ambiente.

Keyring helper
--------------
Para facilitar o armazenamento seguro de senhas locais, o projeto inclui duas formas de gravar no keyring do sistema:

- função programática: `store_password_keyring(user, password)` em `credenciais.py` — retorna `True` em caso de sucesso.
- script CLI: `keyring_store.py` — prompt interativo para usuário e senha e grava no keyring.

Exemplo de uso (script):
```powershell
python keyring_store.py
# ou usando variável de ambiente para usuário
$env:TRINO_USER='meu_usuario'
python keyring_store.py
```

Exemplo programático:
```python
from credenciais import store_password_keyring
store_password_keyring('meu_usuario', 'minha_senha')
```

Notas de segurança:
- `keyring` integra com o cofre do sistema (Windows Credential Manager, macOS Keychain ou equivalente). Use-o para evitar colocar senhas em `.env`.
- Verifique se `keyring` está instalado no ambiente (`pip install keyring`).

CLI
---
O projeto expõe um ponto de entrada mínimo via `trino-connector` (definido em `pyproject.toml`).

Uso básico:

- Mostrar versão:
```powershell
trino-connector --version
```

- Mensagem de ajuda/entrada principal:
```powershell
trino-connector
```

Comandos recomendados (planejados)
- `discover` — listar catálogos/schemas/tables disponíveis via DataShare
- `preview` — buscar um `LIMIT` pequeno de uma tabela (ex.: `trino-connector preview catalog.schema.table --limit 10`)
- `extract` — extrair dados incrementalmente (por coluna de watermark)
- `diagnose` — executar os checks de `diagnostics.py` e exibir recomendações

Exemplo (conceitual) — pré-configure `TRINO_HOST` e credenciais via `keyring` ou `TRINO_BEARER_TOKEN`:
```powershell
$env:TRINO_HOST='trino-gateway.example.com'
$env:TRINO_BEARER_TOKEN='<token>'
trino-connector preview my_catalog.my_schema.my_table --limit 5
```

Nota: o `cli.py` atual é uma entrada mínima; se quiser, eu implemento esses subcomandos (`discover|preview|extract|diagnose`) com `argparse` ou `click` e exemplos concretos no README.

TrinoClient examples
--------------------
Below are concrete example snippets showing how to use `TrinoClient` and an HTTP Bearer-token preview. A runnable script with these examples is included at `examples/trino_client_examples.py`.

1) Using `TrinoClient` (pyhive)

```python
from credenciais import load_credentials
from trino_connect import TrinoClient

host = "trino.example.com"
table = "my_catalog.my_schema.my_table"
user, pwd = load_credentials()

client = TrinoClient(host=host)
client.connect(user, pwd)
try:
	df = client.execute(f"SELECT * FROM {table} LIMIT 10")
	print(df.head())
finally:
	client.close()
```

2) Using HTTP Bearer token (recommended for service accounts)

```python
import os
import requests
import pandas as pd

host = "https://trino.example.com"
table = "my_catalog.my_schema.my_table"
token = os.environ.get("TRINO_BEARER_TOKEN")
headers = {"Authorization": f"Bearer {token}", "X-Trino-User": "integration", "X-Trino-Source": "examples"}

resp = requests.post(f"{host}/v1/statement", data=f"SELECT * FROM {table} LIMIT 5", headers=headers)
resp.raise_for_status()
data = resp.json()
print(data.get("data", [])[:5])
```

Run the full, runnable examples script:
```powershell
python examples/trino_client_examples.py <TRINO_HOST> <catalog.schema.table> --method client
python examples/trino_client_examples.py <TRINO_HOST> <catalog.schema.table> --method bearer
```
