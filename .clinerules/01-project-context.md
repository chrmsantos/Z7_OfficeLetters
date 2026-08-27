# Contexto do Projeto — Z7 OfficeLetters

> Fonte única de verdade: este arquivo e os demais em `.clinerules/`. Mantenha-os
> atualizados quando arquitetura, regras de negócio ou convenções mudarem.

## Identidade

- App desktop **Windows** que automatiza a geração de ofícios legislativos para a
  Câmara Municipal de Santa Bárbara d'Oeste/SP.
- Repositório: `chrmsantos/Z7_OfficeLetters` — branch padrão `master`.
- Licença GPL-3.0. Versão corrente em `pyproject.toml` (`4.17.0`).

## Runtime

- Windows 10+ (usa `winreg`, `win32com`, `os.startfile`). **Não** introduzir abstrações
  multiplataforma — o projeto é intencionalmente Windows-only.
- Python `>=3.12` (CI usa 3.12; build local usa 3.14.5). `python` aponta para `pythoncore-3.14-64`.
- Sem venv obrigatório. Invocar sempre `python -m pip …` e `python -m pytest …`.

## Dependências principais

| Pacote | Versão | Função |
|---|---|---|
| `google-genai` | 1.x | Cliente da API Gemini |
| `customtkinter` | 5.2.2 | Framework GUI dark/light (tkinter) |
| `tkcalendar` | 1.6.1 | Date picker (`locale="pt_BR"`) |
| `babel` | 2.x | Locale data pt_BR exigida pelo tkcalendar |
| `docxtpl` | 0.x | Renderização de templates Word com Jinja2 |
| `python-docx` | 1.x | Leitura de parágrafos `.docx` (banco de endereços) |
| `openpyxl` | 3.x | Geração de planilhas Excel |
| `pypdf` | 6.x | Extração de texto de PDFs |
| `keyring` | 25.x | Persistência de API key no Windows Credential Manager |
| `send2trash` | 1.x | Exclusão segura para a Lixeira |
| `PyInstaller` | 6.20.0 | Compilação standalone `.exe` |
| `pytest` | 9.0.3 | Runner de testes |
| `anyio` | 4.x | Suporte async (usado pelo google-genai) |

## Estrutura do projeto

```text
Z7_OfficeLetters/
├── auto_oficios.spec        # Spec de build do PyInstaller
├── pyproject.toml           # Metadata, ruff, pyright config
├── pytest.ini               # testpaths=tests, pythonpath=["src"]
├── config.json              # Editável: prefeito, autores, redatores
│
├── src/
│   └── z7_officeletters/    # Pacote principal
│       ├── __init__.py      # APP_VERSION, APP_AUTHOR
│       ├── __main__.py      # Entry point + splash screen tkinter
│       ├── constants.py     # Constantes de path/regex/locale
│       │
│       ├── core/            # Lógica de negócio pura (sem GUI, testável)
│       │   ├── address_db.py    # Carregador do banco de endereços + fuzzy lookup
│       │   ├── ai.py            # Integração Gemini + log JSONL da IA
│       │   ├── api_key.py       # Persistência de API key via keyring
│       │   ├── authors.py       # Formatação de nome → sigla
│       │   ├── config.py        # Leitura de config.json (recarregável)
│       │   ├── documents.py     # Helpers de geração .docx/.xlsx
│       │   ├── files.py         # Leitura/listagem de arquivos de propositura
│       │   ├── logging_setup.py # Logger + gravador de log JSONL da IA
│       │   └── recipients.py    # Regras de honoríficos/endereçamento
│       │
│       └── gui/             # Camada GUI (customtkinter)
│           ├── app.py           # AutoOficiosApp (janela raiz CTk)
│           ├── constants.py     # Paleta de cores
│           ├── dialogs/         # Diálogos modais
│           └── workers/
│               └── processor.py # Thread de processamento em background
│
├── ender/
│   └── enderecamentos_padrao.docx  # Banco de endereços (não vai no exe)
│
├── templates/               # Templates Word/Excel (não versionados)
│   ├── modelo_mocao.docx
│   ├── modelo_requer_pesar.docx
│   └── modelo_planilha.xlsx
│
├── tests/
│   ├── conftest.py
│   ├── core/                # Testes unitários (um por módulo)
│   └── gui/
│       └── test_processor.py
│
├── logs/                    # Logs da app (rotativos, por sessão)
│   └── ia/                  # Logs JSONL da IA (um por sessão)
│
└── dist/
    └── Z7_OfficeLetters.exe # Executável standalone compilado
```

### Pastas de dados do usuário (criadas automaticamente)

| Constante | Caminho |
|---|---|
| `PASTA_SAIDA` | `<BASE_DIR>/local/oficios_gerados/` |
| `PASTA_PLANILHA` | `<BASE_DIR>/local/planilha_gerada/` |
| `PASTA_ENVELOPES` | `<BASE_DIR>/local/envelopes_gerados/` |
| `PASTA_PROPOSITURAS_FONTE` | `<BASE_DIR>/local/proposituras_fonte/` |

### Pastas de logs

| Constante | Dev | Frozen |
|---|---|---|
| `PASTA_LOGS` | `<project_root>/logs/` | `<exe_dir>/logs/` |
| `PASTA_LOG_IA` | `<project_root>/logs/ia/` | `<exe_dir>/logs/ia/` |

## Arquitetura em camadas

- `src/z7_officeletters/core/` — lógica de negócio pura (sem GUI, 100% testável).
- `src/z7_officeletters/gui/` — interface (customtkinter). **Nunca** colocar regra de negócio aqui.
- `src/z7_officeletters/constants.py` — constantes globais, sem mutação em runtime.
- `config.json` — editável sem recompilar (autores, redatores, prefeito). Recarregável via `reload_config()`.

### Resumo dos módulos core

| Módulo | Responsabilidade |
|---|---|
| `constants.py` | Paths, regexes, nomes de meses pt-BR, ordem de preferência de arquivos, `detectar_tipo_propositura()`, `numero_propositura()`. |
| `logging_setup.py` | Infra de logging Python + log JSONL da IA. `SESSAO_ID` único por processo. `configurar_logging()`, `registrar_chamada_ia()`. |
| `ai.py` | Extração via Gemini: `extrair_dados_com_ia()`. Retry até `MAX_TENTATIVAS_IA` (5). Sempre grava log JSONL no `finally`. |
| `address_db.py` | Banco de endereços: `carregar_db()`, `buscar_endereco()` (fuzzy, accent-insensitive, min 4 chars). |
| `recipients.py` | Honoríficos brasileiros: `processar_destinatario()` → tratamento, vocativo, pronome, envio. |
| `config.py` | `config.json`: `MAPA_AUTORES`, `MAPA_REDATORES`, `PREFEITO`. `reload_config()` sem reiniciar. |
| `api_key.py` | keyring: `salvar_api_key()`, `carregar_api_key()`. Modelos: `DEFAULT_MODELO_IA`, `DEFAULT_MODELO_FALLBACK`. `migrar_chave_do_registro()`. |
| `documents.py` | Helpers de geração .docx/.xlsx, formatação de nome de arquivo (stripa caracteres ilegais do Windows). |
| `files.py` | Leitura/listagem de proposituras (.txt/.docx/.pdf/.odt), ordem de preferência, deduplicação. |

## Regras de negócio essenciais

- Texto dividido em `MOÇÃO Nº` / `REQUERIMENTO Nº` via `RE_PROPOSITURA_SPLIT`.
- Extração via OpenRouter (DeepSeek primário, Gemini fallback), até `MAX_TENTATIVAS_IA` (5).
- Banco de endereços (`ender/enderecamentos_padrao.docx`) tem **prioridade** sobre dados da IA.
- Um `.docx` por destinatário (via `docxtpl` + template) + `CONTROLE_OFICIOS.xlsx` acumulativo (`openpyxl`).
- Agrupamento: proposituras com mesmo destinatário (nome normalizado + mesmo tipo) são mescladas em um ofício.
- Formato de nome de arquivo: `Of. {num:03d} - {sigla} - Moção de {tipo} nº {num_mocao}-{year_2digit} - {envio} - {dest_nome} - {sigla_autores}.docx`
- Planilha Excel: colunas `Of. n.º | Data | Destinatário | Assunto | Vereador | Envio | Autor`. Aba `Controle {year}`. Acrescenta linhas, nunca sobrescreve.

## Known Issues

| # | Problema | Prioridade | Status |
|---|---|---|---|
| 1 | `.doc` reading: `word.Quit()` no `finally` crasha se `Dispatch()` lançou exceção | Média | Pendente |
| 2 | Autor não mapeado em `MAPA_AUTORES` → `"INDEF"` silencioso, sem warning ao usuário | Média | Pendente |
| 3 | Nome do modelo Gemini pode divergir dos modelos disponíveis por release | Média | Verificar a cada release |
| 4 | AI prompt injection via texto de moção craftado | Baixa (ferramenta interna) | Risco aceito |
| 5 | `ender/enderecamentos_padrao.docx` deve ser distribuído manualmente com o exe | Operacional | Documentado |

## Gotchas críticos (memorizar)

1. **PowerShell 5.1**: nunca usar `Set-Content` para escrever código Python — re-codifica UTF-8 → cp1252.
   Usar a API de arquivos do editor (ou `Out-File -Encoding utf8` se realmente necessário).
2. `SESSAO_ID` é definido **uma única vez** no import de `logging_setup` — não recarregar o módulo.
3. `configurar_logging()` limpa handlers antes de adicionar — seguro chamar múltiplas vezes (testes fazem isso).
4. `ia_log_path` é string vazia até `configurar_logging()`; `registrar_chamada_ia()` faz no-op silencioso.
5. `buscar_endereco()` exige no mínimo 4 caracteres para casar — evita match espúrio em nomes curtos.
6. `extrair_dados_com_ia()` levanta a última exceção após 5 falhas — pode ser `ValueError`, `json.JSONDecodeError` ou exceção original da API. O `finally` sempre grava o log JSONL.
7. **pip:** sempre invocar como `python -m pip …` usando o interpretador `pythoncore-3.14-64`.
8. **Config reload:** `config.reload_config()` relê `config.json` em runtime sem reiniciar. O editor de config da GUI chama isso após salvar.
9. **Todos os paths de dados são absolutos** (sob `BASE_DIR`). Paths de template são relativos à raiz da app, resolvidos via `_resolve_template()` no `processor.py`.
