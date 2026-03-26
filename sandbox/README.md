# Sandbox — Experimentos e Scripts Exploratórios

Área para scripts de teste rápido, provas de conceito e debugging.

**Regras:**
- Scripts aqui são descartáveis — não dependem de estabilidade
- Quando um experimento amadurece, crie um projeto próprio em `../`
- Não coloque credenciais diretamente nos scripts — use variáveis de ambiente

## Scripts

| Arquivo | Propósito |
|---|---|
| `teste_query.py` | Teste rápido de conexão e query no Trino via `TrinoClient` |
| `teste_toqan.py` | Valida API key e conexão com o Toqan (isolado do Trino) |
| `teste_trino.py` | Diagnóstico completo: TCP probes, HTTP auth, pyhive, Bearer token |

## Como usar

Instale o pacote `trino_connector` primeiro:

```powershell
cd ../trino_connector
pip install -e .
```

Depois execute os scripts:

```powershell
cd ../sandbox
python teste_toqan.py
python teste_trino.py
```
