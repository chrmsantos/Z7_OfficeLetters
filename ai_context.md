# AI Context — Z7 OfficeLetters

> This file is the single source of truth for any AI assistant or developer working on this project.
> Keep it updated whenever the architecture, business rules, or conventions change.

---

## 1. Project Purpose

**Z7 OfficeLetters** is a Windows desktop app that automates the generation of legislative letters ("ofícios") for the Câmara Municipal de Santa Bárbara d'Oeste/SP.

Workflow:

1. User places a `.txt`/`.docx`/`.pdf`/`.odt` file containing one or more *moções* or *requerimentos de pesar* in `proposituras/`.
2. User fills in the GUI: ofício start number, author initials, date, propositura file, Gemini API key.
3. App calls **OpenRouter AI** (Llama 3.3 70B, with Gemma 2 fallback) to extract structured data from each propositura text (type, number, authors, recipients).
4. App enriches recipient data from a local address database (`ender/enderecamentos_padrao.docx`) — DB data takes priority over AI-extracted data.
5. App generates one `.docx` letter per recipient using a **Word template**.
6. App generates/updates a single **Excel spreadsheet** accumulating all runs.
7. A detailed **AI JSONL log** is written per session to `logs/ia/` for debugging and improvement.

---

## 2. Repository

- **GitHub:** `chrmsantos/Z7_OfficeLetters` — branch `master` (default)
- **Local workspace:** `C:\Users\csantos\AppData\Local\Z7\Apps\Z7_OfficeLetters`
- **Version:** `4.12.0` (in `pyproject.toml`)
- **License:** GNU GPL v3.0

---

## 3. Runtime Environment

| Item | Detail |
| --- | --- |
| OS | Windows 10+ (required — uses `winreg`, `win32com`, `os.startfile`) |
| Python | 3.14.5 (`C:\Users\csantos\AppData\Local\Python\pythoncore-3.14-64\python.exe`) |
| Virtual env | None — system Python is used directly |
| `python` command | Resolves to `pythoncore-3.14-64` in the VS Code terminal |
| Executable | `dist\Z7_OfficeLetters.exe` (single-file, built with PyInstaller 6.20.0) |

---

## 4. Key Dependencies

| Package | Version | Role |
| --- | --- | --- |
| `google-genai` | 1.x | Gemini AI client |
| `customtkinter` | 5.2.2 | Dark/light-mode GUI framework (tkinter-based) |
| `tkcalendar` | 1.6.1 | Date picker widget (`locale="pt_BR"`) |
| `babel` | 2.x | Required by tkcalendar for pt_BR locale data |
| `docxtpl` | 0.x | Jinja2-based Word template rendering |
| `python-docx` | 1.x | Direct `.docx` paragraph reading (address DB) |
| `openpyxl` | 3.x | Excel file generation |
| `pypdf` | 6.x | PDF text extraction |
| `keyring` | 25.x | API key persistence in Windows Credential Manager |
| `send2trash` | 1.x | Safe file deletion to Recycle Bin |
| `PyInstaller` | 6.20.0 | Standalone `.exe` compilation |
| `pytest` | 9.0.3 | Test runner |
| `anyio` | 4.x | Async support (used by google-genai) |

---

## 5. Project Structure

```text
Z7_OfficeLetters/
├── auto_oficios.spec        # PyInstaller build spec
├── pyproject.toml           # Project metadata, ruff, pyright config
├── pytest.ini               # testpaths=tests, pythonpath=["src"]
├── config.json              # Editable: prefeito, autores, redatores
├── ai_context.md            # ← this file
│
├── src/
│   └── z7_officeletters/    # Main package
│       ├── __init__.py      # APP_VERSION, APP_AUTHOR
│       ├── __main__.py      # Entry point + tkinter splash screen
│       ├── constants.py     # All path/regex/locale constants
│       │
│       ├── core/            # Pure business logic (no GUI, testable)
│       │   ├── address_db.py    # Address DB loader + fuzzy lookup
│       │   ├── ai.py            # Gemini AI integration + AI JSONL log
│       │   ├── api_key.py       # keyring-based API key persistence
│       │   ├── authors.py       # Author name → sigla formatting
│       │   ├── config.py        # config.json loader (reloadable)
│       │   ├── documents.py     # .docx/.xlsx generation helpers
│       │   ├── files.py         # Propositura file reading/listing
│       │   ├── logging_setup.py # Logger + AI JSONL log writer
│       │   └── recipients.py    # Recipient honorific/address rules
│       │
│       └── gui/             # GUI layer (customtkinter)
│           ├── app.py           # AutoOficiosApp (root CTk window)
│           ├── constants.py     # Color palette constants
│           ├── dialogs/         # Modal dialogs (api_key, config_editor,
│           │                    #   prompt_editor, date_picker, …)
│           └── workers/
│               └── processor.py # Background processing thread
│
├── ender/
│   └── enderecamentos_padrao.docx  # Address database (not bundled in exe)
│
├── templates/               # Word/Excel templates (not versioned)
│   ├── modelo_mocao.docx
│   ├── modelo_requer_pesar.docx
│   └── modelo_planilha.xlsx
│
├── tests/
│   ├── conftest.py
│   ├── core/                # Unit tests for each core module
│   └── gui/
│       └── test_processor.py
│
├── logs/                    # App log files (rotating, per-session)
│   └── ia/                  # AI JSONL log files (one per session)
│
└── dist/
    └── Z7_OfficeLetters.exe # Compiled standalone executable
```

**User data** (created automatically) lives under `%USERPROFILE%\AppData\Local\Z7\Tmp\OfficeLetters\`:

| Constant | Path |
| --- | --- |
| `PASTA_PROPOSITURAS` | `…\proposituras\` |
| `PASTA_SAIDA` | `…\oficios_gerados\` |
| `PASTA_PLANILHA` | `…\planilha_gerada\` |

**Logs** live inside the project tree in dev mode or next to the exe when frozen:

| Constant | Dev path | Frozen path |
| --- | --- | --- |
| `PASTA_LOGS` | `<project_root>/logs/` | `<exe_dir>/logs/` |
| `PASTA_LOG_IA` | `<project_root>/logs/ia/` | `<exe_dir>/logs/ia/` |

---

## 6. Architecture

### `constants.py` — Application-wide constants

Single source of truth. No runtime mutations. Key exports:

```python
MESES_PT           # Portuguese month names (1-indexed dict)
ORDEM_PREFERENCIA  # (".txt", ".docx", ".doc", ".odt", ".pdf")
MODELO_OFICIO      # "templates/modelo_mocao.docx"
MODELO_REQUERIMENTO_PESAR  # "templates/modelo_requer_pesar.docx"
MODELO_PLANILHA    # "templates/modelo_planilha.xlsx"
ENDERECAMENTO_PADRAO  # "ender/enderecamentos_padrao.docx"
BASE_DIR, PASTA_SAIDA, PASTA_PROPOSITURAS, PASTA_PLANILHA
PASTA_LOGS, PASTA_LOG_IA
MAX_TENTATIVAS_IA  # 5
RETRY_DELAY_PADRAO_S  # 60 seconds
RE_PROPOSITURA_SPLIT  # splits multi-propositura text at each header
RE_TIPO_PROPOSITURA   # identifies mocao vs requerimento_pesar
detectar_tipo_propositura(texto) -> "mocao" | "requerimento_pesar"
numero_propositura(texto) -> int
```

---

### `core/logging_setup.py` — Logging + AI log

Sets up the Python `logging` infrastructure and the per-session AI JSONL log.

```python
SESSAO_ID: str          # 8-char hex, unique per process start
logger: logging.Logger  # name "z7_officeletters"
ia_log_path: str        # empty until configurar_logging() is called
log_file_path: str      # empty until configurar_logging() is called

configurar_logging(verbose=False) -> str
    # Creates PASTA_LOGS + PASTA_LOG_IA dirs.
    # Sets up RotatingFileHandler (2 MB, 5 backups) + StreamHandler.
    # Adds _ContextFilter (sessao_id, python_version, is_frozen).
    # Installs sys.excepthook + threading.excepthook.
    # Returns main log file path.

log_operation(nome, nivel=DEBUG) -> contextmanager
    # Measures and logs wall-clock duration of a code block.

registrar_chamada_ia(record: dict) -> None
    # Thread-safe append of one JSON line to ia_log_path.

registrar_conferencia_ia(relatorio) -> None
    # Thread-safe append of verification record to ia_log_path.
```

---

### `core/ai.py` — Gemini AI integration

Manages the full lifecycle of a single AI extraction call.

**Public exports:** `extrair_dados_com_ia`, `limpar_json_da_resposta`, `validar_dados_mocao`, `validar_dados_requerimento_pesar`, `PROMPT_TEMPLATE`, `PROMPT_TEMPLATE_PESAR`, `MODELO_IA`

**`extrair_dados_com_ia(texto_mocao, cliente_genai, tipo_propositura, cancel_event) -> dict`**

- Selects prompt template and validation function based on `tipo_propositura`.
- Retries up to `MAX_TENTATIVAS_IA` times; handles HTTP 429 rate-limits with `time.sleep`.
- Always calls `registrar_chamada_ia()` in a `finally` block — success or failure.
- Returns validated dict with `_usage` key (`prompt_tokens`, `candidates_tokens`, `total_tokens`).

**Module-level state:**
```python
_chamada_lock: threading.Lock   # protects _chamada_n
_chamada_n: list[int] = [0]     # sequential AI call counter within the session
MODELO_IA: str                  # loaded from keyring; default "gemini-2.5-flash"
PROMPT_TEMPLATE: str            # active moção prompt (overridable via GUI)
PROMPT_TEMPLATE_PESAR: str      # active requerimento de pesar prompt
```

**`_gerar_alertas(tipo_propositura, resultado, tentativas) -> list[str]`** (private)

Produces soft-warning strings stored in the AI log, including:
- Number of failed/rate-limited attempts before a successful result
- Missing `falecido` field in requerimento de pesar
- Recipients without `cargo/tratamento`
- Recipients without `endereco` nor `email`

---

### `core/address_db.py` — Address database

Loads and caches address blocks from `ender/enderecamentos_padrao.docx`.

```python
EntradaEndereco(NamedTuple):
    tratamento: str  # e.g. "A Sua Excelência o Senhor"
    nome: str        # canonical recipient name (usually all-caps)
    cargo: str       # position/title
    endereco: str    # physical address
    email: str       # contact e-mail, or ""

carregar_db(path: Path) -> list[EntradaEndereco]
buscar_endereco(nome, db_path=None) -> EntradaEndereco | None
    # Accent-insensitive, two-pass fuzzy lookup; minimum 4 chars to match.
resetar_cache() -> None
```

The `.docx` file contains one block per recipient. Each block starts with a *tratamento* line matching `_RE_TRATAMENTO_START` (e.g. `"A Sua Excelência"`, `"Ao "`, `"À "`).

---

### `core/recipients.py` — Recipient processing rules

Applies Brazilian legislative honorific/address rules to a recipient dict.

**`processar_destinatario(dest: dict) -> DestinatarioProcessado`**

Returns: `tratamento_rodape`, `destinatario_nome`, `destinatario_endereco`, `vocativo`, `pronome_corpo`, `envio`

| Condition | `envio` |
| --- | --- |
| Has `email` | `"E-mail"` |
| Has `endereco` (no email) | `"Carta"` |
| Neither | `"Em Mãos"` |
| `is_prefeito=true` | `"Protocolo"` |

---

### `core/config.py` — Runtime configuration

Reads `config.json` at import time. The GUI calls `reload_config()` after the config editor saves changes.

```python
MAPA_AUTORES: dict[str, str]    # author name → sigla (lowercase)
MAPA_REDATORES: dict[str, str]  # drafter name → sigla
PREFEITO: PrefeitoConfig        # {"nome": "...", "endereco": "..."}
```

---

### `core/api_key.py` — API key and model persistence

Stores the OpenRouter API key encrypted in **Windows Credential Manager** via `keyring` (replaces the legacy plain-text Registry entry). Provides one-time migration with `migrar_chave_do_registro()`.

```python
DEFAULT_MODELO_IA = "deepseek/deepseek-v4-pro"
DEFAULT_MODELO_FALLBACK = "deepseek/deepseek-v4-flash"
salvar_api_key(chave: str) -> None
carregar_api_key() -> str
salvar_modelo_ia(modelo: str) -> None
carregar_modelo_ia() -> str
salvar_modelo_fallback(modelo: str) -> None
carregar_modelo_fallback() -> str
migrar_chave_do_registro() -> None
```

---

### `gui/workers/processor.py` — Background processing worker

Runs the full pipeline in a daemon thread. Communicates via `queue.Queue` with the main thread.

**Pipeline phases:**

1. **Init** — resolve templates, load address DB, warm cache, connect to Gemini.
2. **Phase 1: AI extraction** — for each propositura, send text to `extrair_dados_com_ia`. Accumulates token totals.
3. **Phase 2: Grouping** — merge proposituras sharing the same recipient. For each recipient:
   - Look up `_addr_db.buscar_endereco(dest["nome"], db_path=_db_path)`.
   - If found, **DB takes priority**: override `nome`, `cargo_ou_tratamento`, `endereco`, `email` from the DB entry.
   - Call `processar_destinatario(dest_proc)`.
   - Apply `_aplicar_tratamento_db(info, db_entry.tratamento)` to override honorifics.
4. **Phase 3: Generation** — one `.docx` letter per group, written to `PASTA_SAIDA`.
5. **Phase 4: Spreadsheet** — append/create `CONTROLE_OFICIOS.xlsx` in `PASTA_PLANILHA`.

**Message types emitted to the queue:**

| Tag | Payload | Meaning |
| --- | --- | --- |
| `"log"` | `text, tag` | Append line to log panel |
| `"progress"` | `current, total` | Update progress bar |
| `"done"` | `generated, errors, elapsed_s` | Finished successfully |
| `"cancelled"` | `done_so_far, total, ctx` | User cancelled |
| `"error"` | `message` | Fatal unrecoverable error |

---

### `gui/app.py` — Main window

**Class:** `AutoOficiosApp(ctk.CTk)`

Appearance: dark/light toggle (saved per session). Window: 1140×680 (min 920×580). Maximises on startup.

**Layout:** 3-row grid — header bar | left panel (inputs) + right panel (log + progress) | footer.

**Left panel inputs:**
1. Número do ofício inicial — entry + `−`/`+` steppers
2. Iniciais do redator — combobox (from `MAPA_REDATORES`)
3. Data dos ofícios — button opens `tkcalendar.Calendar` (pt_BR)
4. Propositura — combobox (readonly) + refresh `↺` + browse `📂`
5. Chave Gemini API — masked entry + toggle `👁` + Advanced (model selection)
6. "⚡ GERAR OFÍCIOS" button

**Cancel:** `threading.Event` checked between proposituras. Cancel button replaces "GERAR" during processing.

**Polling:** `_poll_queue()` runs every 100 ms via `self.after(100, …)`.

---

### `__main__.py` — Entry point

Shows a borderless tkinter **splash screen** (stdlib only, appears before heavy imports load), then imports and starts `AutoOficiosApp`. Used as PyInstaller entry point.

---

## 7. AI JSONL Log

Every call to `extrair_dados_com_ia` appends one JSON record to the per-session AI log at:

- **Dev:** `<project_root>/logs/ia/ia_TIMESTAMP_SESSAOID.jsonl`
- **Frozen:** `<exe_dir>/logs/ia/ia_TIMESTAMP_SESSAOID.jsonl`

The filename timestamp and `SESSAOID` match the main application log for cross-referencing.

### Record schema

```jsonc
{
  "timestamp":       "2026-05-13T14:30:00.123",   // ISO 8601 with milliseconds
  "sessao_id":       "a1b2c3d4",                   // matches main log filename
  "chamada":         3,                             // sequential call number in this session
  "tipo_propositura": "mocao",                     // "mocao" | "requerimento_pesar"
  "prompt":          "...",                         // full prompt sent to Gemini
  "tentativas": [
    {
      "tentativa":     1,
      "resposta_bruta": "...",                      // full raw API response (untruncated)
      "status":        "resposta_invalida",         // see status values below
      "erro":          "Campo obrigatório ausente…"
    },
    {
      "tentativa":     2,
      "resposta_bruta": "```json\n{…}\n```",
      "status":        "sucesso"
    }
  ],
  "dados_extraidos": { … },   // final validated JSON (without _usage)
  "usage": {
    "prompt_tokens":     540,
    "candidates_tokens": 120,
    "total_tokens":      660
  },
  "alertas": [                // soft warnings — do not abort processing
    "1 tentativa(s) inválida(s)/rate-limit antes do resultado final",
    "Destinatário 2 sem endereço nem e-mail"
  ],
  "erro": null                // non-null only when the call failed entirely
}
```

### `tentativas[].status` values

| Value | Meaning |
| --- | --- |
| `"sucesso"` | Response parsed and validated successfully |
| `"resposta_invalida"` | Invalid JSON or failed schema validation |
| `"rate_limit"` | HTTP 429 — waited `espera_s` seconds before retry |
| `"erro_api"` | Non-429 API error — call aborted immediately |

### `alertas` generated by `_gerar_alertas()`

- `"N tentativa(s) inválida(s)/rate-limit antes do resultado final"`
- `"Campo 'falecido' vazio no requerimento de pesar"`
- `"Destinatário N sem cargo/tratamento"`
- `"Destinatário N sem endereço nem e-mail"`

### Usage for debugging

Open any `.jsonl` file with a JSON viewer or process it with Python:

```python
import json, pathlib

for line in pathlib.Path("logs/ia/ia_20260513_143000_a1b2c3d4.jsonl").read_text("utf-8").splitlines():
    rec = json.loads(line)
    if rec["alertas"] or rec["erro"]:
        print(rec["chamada"], rec["alertas"], rec["erro"])
    # Inspect full AI response for a specific call:
    for t in rec["tentativas"]:
        print(f"  Tentativa {t['tentativa']} [{t['status']}]:", t.get("resposta_bruta", "")[:200])
```

---

## 8. Business Rules

### Propositura splitting

Input text is split at each `MOÇÃO Nº` / `REQUERIMENTO Nº` header using `RE_PROPOSITURA_SPLIT`. Each chunk is sent to the AI independently. Type is detected by `detectar_tipo_propositura()`.

### AI extraction (Gemini)

- Default model: `deepseek/deepseek-v4-pro`
- Fallback model: `deepseek/deepseek-v4-flash` — tried immediately when primary model fails with transient errors (429/503) (stored in `keyring`; overridable per-session via Advanced dialog).
- Schema returned by AI (moção):

```json
{
  "propositura":  "moção",
  "tipo_mocao":   "Aplauso | Apelo | Apoio | Protesto",
  "numero_mocao": "432",
  "autores":      ["Nome Vereador"],
  "destinatarios": [{
    "nome":               "...",
    "cargo_ou_tratamento": "...",
    "endereco":           "...",
    "email":              "...",
    "is_prefeito":        true,
    "is_instituicao":     false,
    "genero":             "M | F"
  }]
}
```

- Requerimento de pesar adds: `numero_requerimento`, `falecido`; omits `tipo_mocao`.
- Up to 5 retries. 429 → sleep `retry_delay_seconds + 2`. Invalid JSON or validation failure → retry silently.
- Raw responses logged (untruncated) in the AI JSONL log; truncated to 500 chars in the Python DEBUG log.

### Address database priority

When a recipient is found in `ender/enderecamentos_padrao.docx`, that data overrides AI output:

| DB field | Overrides |
| --- | --- |
| `nome` | AI recipient name |
| `cargo` | AI `cargo_ou_tratamento` |
| `endereco` | AI `endereco` |
| `email` | AI `email` |
| `tratamento` | honorifics (`tratamento_rodape`, `vocativo`, `pronome_corpo`) |

The DB file is **not bundled** in the exe — it must be distributed alongside `Z7_OfficeLetters.exe`.

### Recipient grouping

Proposituras sharing the same recipient (same normalised name + same `tipo_propositura`) are merged into one letter. The merged letter lists all motion numbers together.

### Filename format

```text
Of. {num:03d} - {sigla} - Moção de {tipo} nº {num_mocao}-{year_2digit} - {envio_lower} - {dest_nome} - {sigla_autores}.docx
```

Windows-illegal characters (`\/*?:"<>|`) are stripped from the name.

### Excel spreadsheet

Columns: `Of. n.º | Data | Destinatário | Assunto | Vereador | Envio | Autor`  
File: `CONTROLE_OFICIOS.xlsx` — appended on every run (rows added, never overwritten).  
Sheet name: `Controle {year}`.

---

## 9. Testing

**Run all tests:**

```powershell
python -m pytest
```

**Stats:** 222 collected, 221 passing, 1 skipped. All AI interactions are mocked.

**Key helpers in `tests/conftest.py`:**

```python
make_dados_mocao_validos(**overrides) -> dict
make_dados_requerimento_validos(**overrides) -> dict
make_dest_simples(**overrides) -> dict
make_ai_response(payload: dict) -> MagicMock  # fake Gemini response with usage_metadata
```

| Test module | What it covers |
| --- | --- |
| `test_address_db.py` | DB parsing, fuzzy lookup, accent normalization, cache |
| `test_ai.py` | Happy path, retries, rate-limit, invalid JSON, logging, alertas |
| `test_api_key.py` | keyring save/load, model persistence, registry migration |
| `test_authors.py` | Siglas, plural text, case-insensitive lookup, unknown authors |
| `test_documents.py` | Filename building, illegal char removal, spreadsheet helpers |
| `test_files.py` | Dir scanning, format preference, deduplication, .gitkeep |
| `test_logging.py` | Handlers, levels, excepthook, file content, ia_log_path init |
| `test_recipients.py` | Prefeito rule, envio logic, gendered tratamento, institutions |
| `test_processor.py` | Full pipeline, grouping, DB priority, cancellation |

---

## 10. Building the Executable

```powershell
# From workspace root:
python -m PyInstaller auto_oficios.spec --noconfirm
```

Output: `dist\Z7_OfficeLetters.exe` (~50 MB, single file, no console window).

**To distribute**, give users a folder with:

```text
Z7_OfficeLetters.exe
config.json
templates/
    modelo_mocao.docx
    modelo_requer_pesar.docx
    modelo_planilha.xlsx
ender/
    enderecamentos_padrao.docx
```

The app creates `proposituras/`, `oficios_gerados/`, `planilha_gerada/`, `logs/`, `logs/ia/` automatically on first run in the same directory.

**Spec notes:**

- Entry point: `src/z7_officeletters/__main__.py`
- Bundled data: `customtkinter/`, `babel/locale-data/`, `babel/global.dat`, `config.json`, 3 docx + 1 xlsx templates
- `ender/enderecamentos_padrao.docx` is **not bundled** — must be distributed separately
- `console=False` — no terminal window
- `pytest`, `_pytest`, `unittest`, `tests` excluded from bundle

---

## 11. Known Issues & Pending Work

| # | Issue | Priority | Status |
| --- | --- | --- | --- |
| 1 | `.doc` reading: `word.Quit()` in `finally` crashes if `Dispatch()` threw | Medium | Pending |
| 2 | Author not in `MAPA_AUTORES` → silent `"INDEF"` with no user warning | Medium | Pending |
| 3 | Gemini model name may drift from available models per release | Medium | Verify on each release |
| 4 | AI prompt injection via crafted moção text | Low (internal tool) | Accepted risk |
| 5 | `ender/enderecamentos_padrao.docx` must be manually distributed with exe | Operational | Documented above |

---

## 12. Conventions & Gotchas

- **`from __future__ import annotations`** is used in every module (PEP 563 style).
- **All user data paths are absolute** (under `BASE_DIR`). Template paths are relative to the app root, resolved via `_resolve_template()` in `processor.py`.
- **`SESSAO_ID`** is set once at `logging_setup` import. It appears in every log line and in both the main log and AI log filenames. Do not reload the module mid-session.
- **`configurar_logging()` clears handlers** before adding new ones — safe to call multiple times (tests do this).
- **`ia_log_path`** is an empty string until `configurar_logging()` is called. `registrar_chamada_ia()` silently no-ops when empty, so tests that do not call `configurar_logging()` are unaffected.
- **`extrair_dados_com_ia`** raises the last exception after 5 failed attempts — could be `ValueError`, `json.JSONDecodeError`, or the original API exception. The `finally` block always writes the AI log record regardless.
- **`buscar_endereco`** minimum match length is 4 characters to avoid spurious matches on short names.
- **PowerShell 5.1 gotcha:** never use `Set-Content` to write Python source — it re-encodes UTF-8 as cp1252→UTF-8 (double-encoding). Use the VS Code file API instead.
- **pip:** always invoke as `python -m pip …` using the `pythoncore-3.14-64` interpreter.
- **Config reload:** `config.reload_config()` re-reads `config.json` at runtime without restarting. The GUI config editor calls this after saving.

