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
