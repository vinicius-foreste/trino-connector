# Oswaldo — Repositório de Ferramentas e Ideias

Workspace centralizado para desenvolvimento de ferramentas internas, experimentos e automações.

## Projetos

| Pasta | Descrição | Status |
|---|---|---|
| [`trino_connector/`](trino_connector/) | NL2SQL com RAG — consulta o Data Lake em linguagem natural via Trino | ✅ Ativo |
| [`sandbox/`](sandbox/) | Scripts exploratórios e experimentos rápidos | 🧪 Laboratório |

## Estrutura

```
Oswaldo/
├── trino_connector/       ← Ferramenta NL2SQL com RAG para Trino
│   ├── src/trino_connector/   ← Pacote Python instalável
│   ├── tests/                 ← Testes unitários e de integração
│   ├── examples/              ← Exemplos de uso
│   └── pyproject.toml         ← Configuração do projeto
│
├── sandbox/               ← Experimentos e scripts descartáveis
│
├── _template/             ← Esqueleto para novos projetos
│
└── README.md              ← Este arquivo
```

## Como criar um novo projeto

1. Copie a pasta `_template/` com o nome do seu projeto:
   ```powershell
   Copy-Item -Recurse _template meu_projeto
   ```
2. Renomeie `src/project_name/` para `src/meu_projeto/`
3. Edite `pyproject.toml` com o nome, descrição e dependências
4. Crie seu `requirements.txt` e `README.md`
5. Comece a desenvolver em `src/meu_projeto/`

## Convenções

- **Um projeto por pasta** no nível raiz
- Cada projeto tem seu próprio `pyproject.toml`, `requirements.txt` e `venv`
- Layout `src/` para pacotes Python (PEP 517)
- Testes em `tests/`, exemplos em `examples/`
- Experimentos rápidos vão para `sandbox/`— quando amadurecem, viram projetos
- CI/CD centralizado em `.github/workflows/` com `working-directory` por projeto
