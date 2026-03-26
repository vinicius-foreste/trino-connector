# trino_connector — NL2SQL com RAG para Trino

Permite consultar o Data Lake em linguagem natural. O usuário digita uma pergunta em português; o sistema busca os schemas relevantes no ChromaDB (RAG), envia o contexto ao Toqan (LLM gateway corporativo), recebe o SQL gerado, executa no Trino e exibe o resultado como tabela.

```
Pergunta → ChromaDB (RAG) → Toqan (LLM) → Trino → DataFrame
```

## Arquitetura

| Módulo | Responsabilidade |
|---|---|
| `config.py` | Carrega variáveis de ambiente (`.env`) e expõe constantes centralizadas |
| `indexer.py` | Extrai metadados do Trino via `information_schema` e indexa no ChromaDB |
| `retriever.py` | Busca semântica no ChromaDB; retorna top-K schemas em YAML |
| `llm_client.py` | Chama o Toqan com o contexto YAML e retorna `{sql_query, lineage}` |
| `trino_executor.py` | Executa o SQL no Trino e retorna `pandas.DataFrame` |
| `query_logger.py` | Grava log de auditoria em JSON (pergunta, SQL, lineage, status) |
| `main.py` | Orquestrador — modo interativo e pergunta direta via CLI |
| `trino_connect.py` | `TrinoClient` com retry/backoff (base) |
| `credenciais.py` | Carrega credenciais: `env` → `keyring` → prompt |
| `diagnostics.py` | Probes de rede/HTTP/TLS para troubleshooting |

## Instalação

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
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
python indexer.py

# Catálogo específico
python indexer.py --catalogs hive

# Múltiplos catálogos
python indexer.py --catalogs hive iceberg

# Descobrir e indexar todos os catálogos
python indexer.py --all-catalogs
```

O indexador extrai metadados via `information_schema.columns` (bulk, sem SHOW TABLES loop) e grava o banco vetorial em `.chroma_db/`.

### 2. Verificar status

```powershell
python main.py --status
```

Saída esperada após indexação:

```
✅ Configuração OK
  ChromaDB: ✅ 2887 tabelas indexadas
```

### 3. Fazer perguntas

```powershell
# Pergunta direta
python main.py "quantos anúncios foram criados em 2024?"

# Executar sem confirmação
python main.py -y "qual o total de receita por categoria em março?"

# Modo interativo (várias perguntas)
python main.py
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
  python keyring_store.py
  ```

## Utilities originais

### Diagnóstico de conexão

```powershell
python teste_trino.py
```

Faz probes TCP/HTTP no gateway, testa autenticação e executa uma query de exemplo (`TRINO_RUN_EXAMPLE=1`).

### Relatório de credenciais

```powershell
python cred_report.py
```

Inspeciona onde as credenciais estão configuradas (env, keyring) e emite recomendações.

### TrinoClient (uso programático)

```python
from credenciais import load_credentials
from trino_connect import TrinoClient

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
