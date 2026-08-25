# Contexto do Projeto — Z7 OfficeLetters

> Fonte única de verdade: **`ai_context.md`** na raiz. Leia-o no início de qualquer tarefa
> não trivial. Se arquitetura, regras de negócio ou convenções mudarem, **atualize `ai_context.md`**
> na mesma tarefa — nunca o deixe defasado.

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

## Arquitetura em camadas

- `src/z7_officeletters/core/` — lógica de negócio pura (sem GUI, 100% testável).
- `src/z7_officeletters/gui/` — interface (customtkinter). **Nunca** colocar regra de negócio aqui.
- `src/z7_officeletters/constants.py` — constantes globais, sem mutação em runtime.
- `config.json` — editável sem recompilar (autores, redatores, prefeito). Recarregável via `reload_config()`.

## Regras de negócio essenciais

- Texto dividido em `MOÇÃO Nº` / `REQUERIMENTO Nº` via `RE_PROPOSITURA_SPLIT`.
- Extração via OpenRouter (DeepSeek primário, Gemini fallback), até `MAX_TENTATIVAS_IA` (5).
- Banco de endereços (`ender/enderecamentos_padrao.docx`) tem **prioridade** sobre dados da IA.
- Um `.docx` por destinatário (via `docxtpl` + template) + `CONTROLE_OFICIOS.xlsx` acumulativo (`openpyxl`).

## Gotchas críticos (memorizar)

1. **PowerShell 5.1**: nunca usar `Set-Content` para escrever código Python — re-codifica UTF-8 → cp1252.
   Usar a API de arquivos do editor (ou `Out-File -Encoding utf8` se realmente necessário).
2. `SESSAO_ID` é definido **uma única vez** no import de `logging_setup` — não recarregar o módulo.
3. `configurar_logging()` limpa handlers antes de adicionar — seguro chamar múltiplas vezes (testes fazem isso).
4. `ia_log_path` é string vazia até `configurar_logging()`; `registrar_chamada_ia()` faz no-op silencioso.
5. `buscar_endereco()` exige no mínimo 4 caracteres para casar — evita match espúrio em nomes curtos.
