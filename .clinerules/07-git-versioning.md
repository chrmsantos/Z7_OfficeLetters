# Git e Versionamento

## Repositório

- Remote: `https://github.com/chrmsantos/Z7_OfficeLetters.git`; branch **`master`** (default).
- CI (`ci.yml`) roda em push/PR para `master`: ruff check, ruff format --check, pyright, pytest (Python 3.12).
- Pre-commit: ruff (--fix) + ruff-format + pyright.

## Convenções

- Nunca `git push --force` para `master`.
- Commits concisos e descritivos (ex.: `fix(core): corrige busca de endereço sem acento`).
- Antes de push: testes + lint verdes.

## Sincronização de versão (CRÍTICA — já esteve dessincronizada)

A versão vive em **3 lugares** e todos devem estar em sincronia:

1. `pyproject.toml` → `version = "X.Y.Z"` (fonte da verdade).
2. `src/z7_officeletters/__init__.py` → fallback hardcoded no fim de `_read_version()`
   (`return "X.Y.Z"`).
3. `.clinerules/01-project-context.md` → seção "Identidade", campo "Versão corrente".

Ao alterar a versão, usar o skill **`version-bump`** (atualiza os 3 pontos de uma vez e confere o resultado).
Não mudar a versão sem pedido explícito do usuário.

## Arquivos fora do controle de versão (`.gitignore`)

- `local/` (dados do usuário), `logs/` (inclui `logs/ia/*.jsonl`), `dist/`, `build/`,
  `.venv/`, `templates/` (binários), `build_out*.txt`, `build_err*.txt`, `.cline/`.

> Nota: `.cline/` está no `.gitignore` — a configuração de Cline (regras/skills/plugins) é local.
> Se quiser versionar a configuração para o time, remova `.cline/` do `.gitignore`.

## `config.json`

- **É versionado** e contém dados editáveis (autores, redatores, prefeito). Não é segredo,
  mas contém nomes reais — revisar diffs antes de commitar mudanças nele.
