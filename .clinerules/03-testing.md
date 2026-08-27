---
paths:
  - "tests/**"
  - "src/**"
---

# Padrões de Teste

## Como rodar

- Todos: `python -m pytest` (da raiz; `pythonpath = ["src"]`).
- Um módulo: `python -m pytest tests/core/test_ai.py -q`.
- Um teste: `python -m pytest tests/core/test_ai.py::TestX::test_y -q`.
- `addopts = -v --tb=short` já configurado em `pyproject.toml` e `pytest.ini`.

## Convenções

- Testes em `tests/core/` (um por módulo) e `tests/gui/`.
- Nome: `test_<modulo>.py`; funções `test_<o_que_e_testado>`; classes `Test<Modulo>`.
- **Toda interação com IA é mockada** — nunca fazer chamadas reais à API nos testes.
- Usar factories de `tests/conftest.py`:
  `make_dados_mocao_validos()`, `make_dados_requerimento_validos()`, `make_dest_simples()`,
  `make_ai_response(payload)`.

## Regras

- Para qualquer lógica nova em `core/`, escrever ou atualizar o teste correspondente.
- Não quebrar os testes existentes (referência: 222 coletados, 221 passam, 1 skip).
- Ao mexer em `logging_setup`, lembrar: `configurar_logging()` limpa handlers antes de adicionar —
  seguro re-chamar em testes; `ia_log_path` vazio → `registrar_chamada_ia()` faz no-op.
- Testes não devem depender de ordem de execução nem de estado global compartilhado.

## Após falha

- Rodar `python -m pytest -x -q` para falhar rápido no primeiro erro.
- Ler o traceback (`--tb=short`) e corrigir a causa raiz — não silenciar o teste.
- Para o fluxo completo de diagnóstico, usar o skill `run-tests`.

## Mapa de cobertura de testes

| Módulo de teste | O que cobre |
|---|---|
| `test_address_db.py` | Parsing do DB, fuzzy lookup, normalização de acentos, cache |
| `test_ai.py` | Happy path, retries, rate-limit, JSON inválido, logging, alertas |
| `test_api_key.py` | keyring save/load, persistência de modelo, migração do registry |
| `test_authors.py` | Siglas, texto plural, lookup case-insensitive, autores desconhecidos |
| `test_documents.py` | Construção de nome de arquivo, remoção de chars ilegais, helpers de planilha |
| `test_files.py` | Scan de diretório, preferência de formato, deduplicação, .gitkeep |
| `test_logging.py` | Handlers, níveis, excepthook, conteúdo de arquivo, init de ia_log_path |
| `test_recipients.py` | Regra de prefeito, lógica de envio, tratamento por gênero, instituições |
| `test_processor.py` | Pipeline completo, agrupamento, prioridade do DB, cancelamento |
