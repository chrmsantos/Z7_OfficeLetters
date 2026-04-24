# AI Context — Z7 OfficeLetters

> This file is the single source of truth for any AI assistant or developer working on this project.
> Keep it updated whenever the architecture, business rules, or conventions change.

---

## 1. Project Purpose

**Z7 OfficeLetters** is a Windows desktop app that automates the generation of legislative letters ("ofícios") for the Câmara Municipal de Santa Bárbara d'Oeste/SP.

Workflow:

1. User places a `.txt`/`.docx`/`.pdf`/`.odt` file containing one or more *moções* (legislative motions) in `proposituras/`.
2. User fills in the GUI: ofício start number, author initials, date, propositura file, Gemini API key.
3. App calls **Google Gemini AI** to extract structured data from each moção text (type, number, authors, recipients).
4. App generates one `.docx` letter per recipient using a **Word template** (`modelo_oficio.docx`).
5. App generates/overwrites a single **Excel spreadsheet** (`planilha_gerada/CONTROLE_OFICIOS.xlsx`) accumulating all runs.
6. All output and logs are written relative to the **current working directory** at runtime.

---

## 2. Repository

- **GitHub:** `chrmsantos/Z7_OfficeLetters` — branch `master` (default)
- **Local workspace:** `C:\Users\csantos\AppData\Local\ZWave\Apps\officeletters`
- **License:** GNU GPL v3.0

---

## 3. Runtime Environment

| Item | Detail |
| --- | --- |
| OS | Windows 10+ (required — uses `winreg`, `win32com`, `os.startfile`) |
| Python | 3.14.4 (in-workspace venv at `.venv`) |
| Virtual env | `.venv\Scripts\activate` |
| Executable | `dist\Z7_OfficeLetters.exe` (single-file, built with PyInstaller 6.20.0) |

---

## 4. Key Dependencies

| Package | Version | Role |
| --- | --- | --- |
| `google-genai` | 1.67.0 | Gemini AI client |
| `customtkinter` | 5.2.2 | Dark-mode GUI framework (tkinter-based) |
| `tkcalendar` | 1.6.1 | Date picker widget (`locale="pt_BR"`) |
| `babel` | 2.18.0 | Required by tkcalendar for pt_BR locale data |
| `docxtpl` | 0.20.2 | Jinja2-based Word template rendering |
| `openpyxl` | 3.1.5 | Excel file generation |
| `pypdf` | 6.9.1 | PDF text extraction |
| `winreg` | stdlib | API key persistence in Windows Registry |
| `win32com` (pywin32) | — | `.doc` file reading via Word COM automation |
| `PyInstaller` | 6.19.0 | Standalone `.exe` compilation |
| `pytest` | 8.3.4 | Test runner |
| `pytest-cov` | 5.0.0 | Coverage reporting |
| `anyio` | 4.12.1 | Async support (used by google-genai) |

---

## 5. Project Structure

```text
officelatters/
├── auto_oficios.py          # Core business logic — the only module with unit tests
├── ui.py                    # Full customtkinter GUI — sole entry point for users
├── config.json              # Editable config: prefeito name/address + MAPA_AUTORES
├── auto_oficios.spec        # PyInstaller build spec
├── pytest.ini               # testpaths=tests, addopts=-v --tb=short
├── LICENSE                  # GNU GPL v3.0
├── README.md
├── ai_context.md            # ← this file
│
├── templates/
│   ├── modelo_oficio.docx   # Word template (NOT versioned)
│   └── modelo_planilha.xlsx # Excel template (auto-generated if missing)
│
├── proposituras/            # Input folder — user places moção files here
├── oficios_gerados/         # Output folder — generated .docx letters
├── planilha_gerada/         # Output folder — CONTROLE_OFICIOS.xlsx (overwritten each run)
├── logs/                    # Log files (rotating, per-session)
│
├── tests/
│   └── test_auto_oficios.py # 122 unit tests
│
├── dist/
│   └── Z7_OfficeLetters.exe # Compiled standalone executable
│
└── .venv/                   # Python 3.14.4 virtual environment
```

---

## 6. Architecture

### `auto_oficios.py` — Business Logic Module

Pure business logic. **No GUI, no CLI.** Fully importable in tests without side effects.

**Module-level constants (used across both files):**

```python
PASTA_SAIDA        = "oficios_gerados"
PASTA_LOGS         = "logs"
PASTA_PROPOSITURAS = "proposituras"
PASTA_PLANILHA     = "planilha_gerada"
SESSAO_ID          = uuid.uuid4().hex[:8]   # 8-char hex, unique per process start
MESES_PT           = {1: "janeiro", ..., 12: "dezembro"}
```

**`MAPA_AUTORES` and `prefeito` data are loaded from `config.json` at import time**, not hardcoded. This allows updating councillor names and the mayor without recompiling. If `config.json` is missing, the module raises `FileNotFoundError` at import.

**Public functions:**

| Function | Signature | Description |
| --- | --- | --- |
| `configurar_logging` | `(verbose=False) -> str` | Sets up `RotatingFileHandler` (2 MB, 5 backups) + `StreamHandler`. Installs `sys.excepthook`. Returns log file path. |
| `_salvar_api_key_no_ambiente` | `(chave: str) -> None` | Writes API key to `HKCU\Environment` registry + `os.environ`. |
| `listar_proposituras` | `() -> list[Path]` | Scans `PASTA_PROPOSITURAS`, deduplicates by format preference. |
| `resolver_arquivo_preferencial` | `(caminho: str) -> str` | Given a path, returns the highest-priority variant: `.txt > .docx > .doc > .odt > .pdf`. |
| `ler_arquivo_mocoes` | `(caminho: str) -> str` | Reads `.txt`/`.docx`/`.doc`/`.odt`/`.pdf`. `.doc` uses `win32com`. |
| `limpar_json_da_resposta` | `(texto: str) -> str` | Strips ` ```json ` / ` ``` ` markdown fences from AI response. |
| `validar_dados_mocao` | `(dados: dict) -> None` | Validates required fields. Raises `ValueError` on failure. |
| `extrair_dados_com_ia` | `(texto_mocao, cliente_genai) -> dict` | Sends text to Gemini, retries up to 5×. Handles rate-limit (429) with `time.sleep`. |
| `normalizar_numero_mocao` | `(numero: str) -> str` | Strips year suffixes: `"124/2026" → "124"`. |
| `construir_nome_arquivo` | `(num_oficio_str, sigla_servidor, tipo_mocao, num_mocao, envio, nome_dest, sigla_autores) -> str` | Builds `.docx` filename. Strips Windows-illegal chars (`\/*?:"<>\|`). Appends `-{year_2digit}` to moção number. |
| `formatar_autores` | `(lista_autores: list[str]) -> tuple[str, str]` | Returns `(text_autoria, sigla_combinada)`. Unknown authors get sigla `"INDEF"`. |
| `processar_destinatario` | `(dest: dict) -> dict` | Applies business rules for address/envio/tratamento. Mayor override is hardcoded via `config.json`. |

**`__main__` block:**

```python
if __name__ == "__main__":
    from ui import AutoOficiosApp
    app = AutoOficiosApp()
    app.mainloop()
```

---

### `ui.py` — GUI Entry Point

**Class:** `AutoOficiosApp(ctk.CTk)`

Appearance: dark mode only (`ctk.set_appearance_mode("dark")`), blue accent. Window: 1140×720 (min 920×620).

**Layout:** 3-row grid.

- Row 0: header bar
- Row 1 col 0: left panel (inputs, 370px fixed width)
- Row 1 col 1: right panel (log + progress, flexible)
- Row 2: footer

**Left panel input fields:**

1. Número do ofício inicial — entry + `−`/`+` steppers
2. Iniciais do redator — text entry
3. Data dos ofícios — button opens `tkcalendar.Calendar` (pt_BR, dd-mm-yyyy)
4. Propositura — combobox (readonly) + refresh `↺` + browse `📂`
5. Chave Gemini API — masked entry + toggle visibility `👁`
6. "⚡ GERAR OFÍCIOS" button (disabled during processing)

**Right panel:**

- Progress bar + label + percentage
- CTkTextbox log with colored tags: `success` (green), `error` (red), `warn` (yellow), `dim` (gray), `accent` (blue), `bold`
- Summary bar + "📁 Abrir Pasta de Saída" button

**Threading model:**

- `_start_processing()` validates inputs on main thread, then spawns a daemon `threading.Thread`
- `_worker(inputs)` runs in background; communicates via `queue.Queue` with typed message tuples
- `_poll_queue()` drains the queue every 100ms via `self.after(100, ...)`
- Message types: `("log", text, tag)`, `("progress", current, total)`, `("done", generated, errors, elapsed)`, `("error", msg)`

**Cancel:**  `self._cancel_event = threading.Event()` — worker checks `_cancel_event.is_set()` between moções. Cancel button appears during processing, replacing "GERAR OFÍCIOS".

**Lazy imports** (to keep module loadable without optional deps installed):

```python
from tkcalendar import Calendar          # in _open_date_picker()
from auto_oficios import listar_proposituras  # in _refresh_proposituras()
from auto_oficios import PASTA_SAIDA     # in _open_output_folder()
from auto_oficios import MESES_PT        # in _start_processing()
from google import genai                 # in _worker()
from docxtpl import DocxTemplate         # in _worker()
from openpyxl import Workbook            # in _worker()
import auto_oficios as _ao               # in _worker()
```

---

### `config.json` — Runtime Configuration

Editable without recompiling. Loaded by `auto_oficios.py` at import.

```json
{
  "prefeito": {
    "nome": "RAFAEL PIOVEZAN",
    "endereco": "Prefeito Municipal\nSanta Bárbara d'Oeste/SP"
  },
  "autores": {
    "Alex Dantas": "ad",
    "Arnaldo Alves": "aa",
    ...
  }
}
```

**When the mayor changes:** edit `nome` and `endereco` in this file.  
**When a new councillor joins:** add an entry to `autores` (lowercase sigla — the code calls `.upper()` when formatting).  
**For the distributed exe:** `config.json` must be placed alongside `AutoOficios.exe`, and `templates/modelo_oficio.docx` inside a `templates/` subfolder.

---

## 7. Business Rules

### Moção splitting

The input file can contain multiple moções. They are split by regex: `re.split(r'(?=MOÇÃO Nº)', conteudo)`. Each chunk is sent to the AI independently.

### AI extraction (Gemini)

- Model: configured via `extrair_dados_com_ia` — check the `model=` argument for the current model name.
- Schema returned by AI:

```json
{
  "tipo_mocao": "Aplauso" | "Apelo",
  "numero_mocao": "124",
  "autores": ["Nome Vereador"],
  "destinatarios": [{
    "nome": "...",
    "cargo_ou_tratamento": "...",
    "endereco": "...",
    "email": "...",
    "is_prefeito": true|false,
    "is_instituicao": true|false
  }]
}
```

- Up to 5 retry attempts for API errors (429→sleep) and invalid/unparseable JSON.
- Raw response logged at DEBUG level, truncated to 500 chars.

### Recipient processing (`processar_destinatario`)

| Condition | Result |
| --- | --- |
| `is_prefeito=true` OR `"prefeito" in nome.lower()` | Fixed data from `config.json`: name, address, "Vossa Excelência", envio="Protocolo" |
| `is_instituicao=true`, name starts with "a/A" | `tratamento_rodape = "À"` |
| `is_instituicao=true`, otherwise | `tratamento_rodape = "Ao"` |
| Person (not institution) | `tratamento_rodape = "Ao Ilustríssimo Senhor"` |
| Has `email` | `envio = "E-mail"` |
| Has `endereco` (no email) | `envio = "Carta"` |
| Neither | `envio = "Em Mãos"` |

### Filename format

```text
Of. {num:03d} - {sigla} - Moção de {tipo} nº {num_mocao}-{year_2digit} - {envio_lower} - {dest_nome} - {sigla_autores}.docx
```

`year_2digit` is derived from the selected date year at runtime (not hardcoded).

### Excel spreadsheet

Columns: `Of. n.º | Data | Destinatário | Assunto | Vereador | Envio | Autor`  
File: `planilha_gerada/CONTROLE_OFICIOS.xlsx` — **overwritten on every run** (intentional).  
Sheet name: `Controle {year}` (dynamic).

---

## 8. Testing

**Run all tests:**

```powershell
& ".venv\Scripts\python.exe" -m pytest
```

**Stats:** 112 tests, all passing. No external network calls — all AI interactions are mocked.

**Test file:** `tests/test_auto_oficios.py` (769 lines)

| Class | Tests | What it covers |
| --- | --- | --- |
| `TestLimparJsonDaResposta` | 6 | JSON markdown fence stripping |
| `TestValidarDadosMocao` | 12 | Required fields, type checks, multi-recipient |
| `TestNormalizarNumeroMocao` | 10 | Year suffix variants (parametrize) |
| `TestConstruirNomeArquivo` | 9 | Filename building, illegal char removal |
| `TestFormatarAutores` | 10 | Siglas, plural text, case-insensitive lookup |
| `TestProcessarDestinatario` | 13 | Prefeito rule, envio logic, tratamento |
| `TestResolverArquivoPreferencial` | 7 | Format preference chain, no cross-dir |
| `TestListarProposituras` | 9 | Dir scanning, deduplication, .gitkeep |
| `TestLerArquivoMocoes` | 5 | txt/docx/pdf reading, unsupported format |
| `TestConfigurarLogging` | 13 | Handlers, levels, excepthook, file content |
| `TestSalvarApiKey` | 3 | Registry + environ write, logging |
| `TestExtrairDadosComIA` | 12 | Happy path, retry, rate-limit, truncated log |

**Key test helpers:**

```python
def _dados_mocao_validos(**overrides) -> dict   # valid AI response dict
def _dest_simples(**overrides) -> dict           # minimal recipient dict
def _make_ai_response(payload: dict) -> MagicMock  # fake Gemini response
```

---

## 9. Building the Executable

```powershell
# From workspace root, with venv active:
& ".venv\Scripts\python.exe" -m PyInstaller auto_oficios.spec --clean
```

Output: `dist\Z7_OfficeLetters.exe` (~50 MB, single file, no console window).

**To distribute**, give users a folder with:

```text
Z7_OfficeLetters.exe
config.json
templates/
    modelo_oficio.docx
```

The app creates `proposituras/`, `oficios_gerados/`, `planilha_gerada/`, `logs/` automatically on first run in the same directory.

**Spec notes:**

- Entry point: `ui.py`
- Bundled data: `customtkinter/` themes, `babel/locale-data/` (pt_BR calendar), `babel/global.dat`
- `console=False` — no terminal window appears
- `pytest`, `_pytest`, `unittest`, `tests` are excluded from the bundle

---

## 10. Known Issues & Pending Work

| # | Issue | Priority | Status |
| --- | --- | --- | --- |
| 1 | `año` suffix in filename hardcoded: `-26` | High | **Pending** — must use `year % 100` from selected date |
| 2 | `.doc` reading: `word.Quit()` in `finally` crashes if `Dispatch()` threw | Medium | **Pending** |
| 3 | Author not in `MAPA_AUTORES` → silent `"INDEF"` with no user warning | Medium | **Pending** |
| 4 | Cancel button during processing | Medium | **Pending** (threading.Event scaffolding exists in plan) |
| 5 | API key stored as plaintext in `HKCU\Environment` registry | Low (single-user machine) | Accepted risk — could migrate to `keyring`/DPAPI |
| 6 | AI prompt injection via crafted moção text | Low (internal tool) | Accepted risk |
| 7 | Gemini model name in `extrair_dados_com_ia` may drift from available models | Medium | Verify on each release |
| 8 | `config.json` must be manually distributed with exe | Operational | Documented above |

---

## 11. Conventions & Gotchas

- **All paths are relative to CWD.** When running from source, CWD must be the workspace root. When running the exe, CWD is the folder containing `AutoOficios.exe`.
- **`SESSAO_ID`** is set once at module import. It is included in every log line and in the log filename. Do not reload `auto_oficios` mid-session.
- **`configurar_logging()` clears handlers** before adding new ones to prevent accumulation across test runs or repeated calls.
- **`extrair_dados_com_ia`** raises the last exception after 5 failed attempts — not a custom exception type, could be `ValueError`, `json.JSONDecodeError`, or the original API exception.
- **`ler_arquivo_mocoes`** for `.doc` files requires Microsoft Word installed and `pywin32`. The `.exe` bundles `pywin32` but Word must be present on the target machine.
- **Tests must run from the workspace root** (enforced by `pytest.ini` `testpaths = tests`). The test file inserts the parent dir into `sys.path` for direct `import auto_oficios`.
- **PowerShell 5.1 gotcha:** never use `Set-Content` to write Python source — it re-encodes UTF-8 as cp1252→UTF-8 (double-encoding). Use `python -c "open(..., 'wb').write(b'...')"` or the VS Code file API instead.
- **pip in this venv:** always invoke as `& ".venv\Scripts\python.exe" -m pip ...` — the `pip.exe` launcher has a stale path from a previous install location.
