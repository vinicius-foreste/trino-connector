# trino_connector — NL2SQL com RAG para Trino

Permite consultar o Data Lake em linguagem natural. O usuário digita uma pergunta em português; o sistema busca os schemas relevantes no ChromaDB (RAG), envia o contexto ao Toqan (LLM gateway corporativo), recebe o SQL gerado, executa no Trino e exibe o resultado como tabela.

```
Pergunta → ChromaDB (RAG) → Toqan (LLM) → Trino → DataFrame
```

## Arquitetura

| Módulo | Responsabilidade |
|---|---|
| `src/trino_connector/config.py` | Carrega variáveis de ambiente (`.env`) e expõe constantes centralizadas |
| `src/trino_connector/indexer.py` | Extrai metadados do Trino via `information_schema` e indexa no ChromaDB |
| `src/trino_connector/retriever.py` | Busca semântica no ChromaDB; retorna top-K schemas em YAML |
| `src/trino_connector/llm_client.py` | Chama o Toqan com o contexto YAML e retorna `{sql_query, lineage}` |
| `src/trino_connector/trino_executor.py` | Executa o SQL no Trino e retorna `pandas.DataFrame` |
| `src/trino_connector/query_logger.py` | Grava log de auditoria em JSON (pergunta, SQL, lineage, status) |
| `src/trino_connector/main.py` | Orquestrador — modo interativo e pergunta direta via CLI |
| `src/trino_connector/trino_connect.py` | `TrinoClient` com retry/backoff (base) |
| `src/trino_connector/credenciais.py` | Carrega credenciais: `env` → `keyring` → prompt |
| `src/trino_connector/diagnostics.py` | Probes de rede/HTTP/TLS para troubleshooting |

## Instalação

```powershell
cd trino_connector
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

## Configuração

Copie `.env.example` para `.env` e preencha os valores:

```powershell
Copy-Item .env.example .env
```

Variáveis obrigatórias:

```env
# Toqan (LLM Gateway corporativo)
TOQAN_API_KEY=sk_...          # gere em https://toqan.ai
TOQAN_BASE_URL=https://api.toqan.ai/api
TOQAN_VERIFY_SSL=false        # necessário em redes corporativas com proxy SSL

# Trino
TRINO_HOST=trino-gateway.dataeng.bigdata.olxbr.io
TRINO_PORT=443
TRINO_USER=seu.usuario
TRINO_PASSWORD=sua_senha
TRINO_CATALOG=hive
```

## Uso — fluxo completo

### 1. Indexar o catálogo (uma vez, ou quando o schema mudar)

Requer VPN ativa.

```powershell
# Catálogo padrão (TRINO_CATALOG do .env)
python -m trino_connector.indexer

# Catálogo específico
python -m trino_connector.indexer --catalogs hive

# Múltiplos catálogos
python -m trino_connector.indexer --catalogs hive iceberg

# Descobrir e indexar todos os catálogos
python -m trino_connector.indexer --all-catalogs
```

O indexador extrai metadados via `information_schema.columns` (bulk, sem SHOW TABLES loop) e grava o banco vetorial em `.chroma_db/`.

### 2. Verificar status

```powershell
python -m trino_connector.main --status
```

Saída esperada após indexação:

```
✅ Configuração OK
  ChromaDB: ✅ 2887 tabelas indexadas
```

### 3. Fazer perguntas

```powershell
# Pergunta direta
python -m trino_connector.main "quantos anúncios foram criados em 2024?"

# Executar sem confirmação
python -m trino_connector.main -y "qual o total de receita por categoria em março?"

# Modo interativo (várias perguntas)
python -m trino_connector.main
```

O sistema vai mostrar:
- Tabelas selecionadas pelo RAG e score de relevância
- SQL gerado pela IA
- Lineage (tabelas e colunas usadas)
- Confirmação antes de executar
- Resultado como tabela

## Segurança

- Nunca commite `.env`. O `.gitignore` já o exclui.
- `.env.example` é apenas um modelo — **sem credenciais reais**.
- O LLM é instruído para gerar apenas `SELECT`. O `main.py` rejeita qualquer SQL que modifique dados (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `CREATE`, etc.).
- Toda execução é gravada em `query_audit_log.json` com timestamp, SQL e status.
- Use `keyring` para armazenar senhas localmente:
  ```powershell
python -m trino_connector.keyring_store
  ```

## Utilities originais

### Diagnóstico de conexão

```powershell
python -m trino_connector.diagnostics --host trino-gateway.dataeng.bigdata.olxbr.io
```

Faz probes TCP/HTTP no gateway e retorna informações de autenticação.

### Relatório de credenciais

```powershell
python -m trino_connector.cred_report
```

Inspeciona onde as credenciais estão configuradas (env, keyring) e emite recomendações.

### TrinoClient (uso programático)

```python
from trino_connector.credenciais import load_credentials
from trino_connector.trino_connect import TrinoClient

user, pwd = load_credentials()
client = TrinoClient(host="trino-gateway.dataeng.bigdata.olxbr.io", port="443")
client.connect(user, pwd)
df = client.execute("SELECT * FROM hive.ods.minha_tabela LIMIT 10")
print(df.head())
client.close()
```

Ver mais exemplos em `examples/trino_client_examples.py`.

## Testes

```powershell
pytest -q
```

## Lint

```powershell
ruff check .
```
