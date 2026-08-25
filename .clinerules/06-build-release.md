---
paths:
  - "auto_oficios.spec"
  - "build.py"
  - "pyproject.toml"
  - ".github/**"
  - "*.spec"
---

# Build e Release

## Build local — SEMPRE via `python build.py` (nunca PyInstaller direto)

O `build.py` executa a sequência segura e idempotente:

1. `taskkill /F /IM Z7_OfficeLetters.exe` (finaliza instâncias ativas).
2. Verifica lock do `dist/Z7_OfficeLetters.exe` (10 tentativas × 1s).
3. Regenera `src/z7_officeletters.egg-info` via `pip install . --no-deps --no-build-isolation`.
4. `python -m PyInstaller auto_oficios.spec --noconfirm`.

## Checklist obrigatório ANTES do build

- `python -m pytest` verde.
- `ruff check` + `ruff format --check` + `pyright src/` limpos.
- Versão sincronizada nos 3 pontos (ver `07-git-versioning.md`):
  `pyproject.toml` ↔ `__init__.py` (fallback) ↔ `ai_context.md`.
- `auto_oficios.spec` contém `hiddenimports` de qualquer módulo/diálogo novo.
- `config.json` e templates presentes (o spec embute `config.json` + templates; `ender/` é distribuído à parte).

## Saída e distribuição

- `dist/Z7_OfficeLetters.exe` (~50 MB, single-file, `console=False`).
- Distribuir **junto**: `config.json`, `templates/` (3 docx + 1 xlsx + 1 envelope), `ender/enderecamentos_padrao.docx`.
- `ender/enderecamentos_padrao.docx` **não** é empacotado no exe.

## Erros recorrentes a evitar (causa de retentativas e builds truncados)

1. **Versão dessincronizada** → exe sai com versão errada. Sempre rodar o skill `version-bump`.
2. **Egg-info desatualizado** → `pip install .` não executado antes do PyInstaller; versão embutida fica velha.
3. **Exe travado** → não sobrescrever; `build.py` já mata processo e verifica lock. Se falhar, fechar o app manualmente.
4. **Saída truncada do PyInstaller** → a saída é longa; verificar apenas a última linha
   (`Build complete! The results are available in: …`). Não assumir falha por saída truncada no meio.
5. **`config.json` não encontrado** no log do build é aviso de análise — o spec embute o `config.json`
   correto; não confundir com o `config.json` de runtime do usuário.

## Fluxo completo de build + deploy no GitHub

Usar o skill **`build-release`** — ele padroniza pré-flight → build → verificação → commit/tag →
push → GitHub Release, com verificação de cada etapa antes de prosseguir (evita o ciclo de
"sucesso só após várias tentativas").
