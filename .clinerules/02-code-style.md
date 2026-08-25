# Padrões de Código Python

Validados por **ruff** + **pyright** no CI (`.github/workflows/ci.yml`) e no pre-commit.
Se o código passar neles, está no padrão do projeto.

## Estilo obrigatório

- `from __future__ import annotations` em **todo** módulo (PEP 563).
- Nomes `snake_case` (funções/variáveis), `UPPER_SNAKE_CASE` (constantes), `PascalCase` (classes).
- Docstrings em **português brasileiro**, convenção **Google** (`pydocstyle convention = "google"`).
- Type hints em funções públicas (pyright `strict`). `Any` só quando inevitável (ex.: respostas da IA),
  com `# type: ignore[...]` pontual quando necessário.
- `line-length = 100`. Aspas duplas (`ruff.format quote-style = "double"`).
- Rodar antes de commitar: `ruff check`, `ruff format`, `pyright src/`.

## Logging — nunca `print`

- Usar o logger do pacote (`logging.getLogger("z7_officeletters")`), mensagens em pt-BR.
- `print` é aceitável **apenas** em `scripts/` de linha de comando (`build.py`, `run_cli.py`, `generate_icon.py`).

## Imports lazy (performance + resiliência)

- **Não** importar dependências pesadas no topo do módulo — importar dentro da função.
- Isso mantém os testes rápidos e impede que dependências ausentes quebrem a importação do módulo.
- Exceção: módulos da stdlib e o próprio pacote `z7_officeletters`.

## Padrões estruturais

- Constantes de caminho/regex centralizadas em `constants.py` — nunca hardcoded em outros módulos.
- Configuração de runtime via `core/config.py`; `reload_config()` recarrega sem reiniciar.
- Helpers de teste reutilizáveis em `tests/conftest.py` (factories `make_*`).
- Exports públicos declarados em `__all__` nos módulos que os possuem.

## O que NÃO fazer

- Não adicionar regra de negócio em `gui/app.py` (apenas interface).
- Não mudar `version`/`APP_VERSION` sem pedido explícito — usar o skill `version-bump`.
- Não quebrar a superfície de testes existente em `tests/` (222+ testes).
- Não usar `Set-Content` do PowerShell para editar fontes Python (re-codificação UTF-8).
