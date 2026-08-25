---
paths:
  - "src/z7_officeletters/gui/**"
---

# Padrões de GUI (customtkinter)

## Arquitetura

- `gui/app.py` — janela principal `AutoOficiosApp(ctk.CTk)`. **Apenas interface**; sem regra de negócio.
- `gui/workers/processor.py` — pipeline completo em thread daemon; comunica via `queue.Queue`.
- `gui/dialogs/` — diálogos modais (api_key, config_editor, prompt_editor, date_picker, confirmation).
- `gui/constants.py` — paleta de cores.

## Comunicação worker → GUI (mensagens na fila)

- `log` (text, tag) · `progress` (current, total) · `done` (generated, errors, elapsed_s) ·
  `cancelled` (done_so_far, total, ctx) · `error` (message).
- GUI faz polling a cada 100 ms via `self.after(100, …)`.
- Cancelamento: `threading.Event` verificado entre proposituras; botão "Cancelar" substitui "GERAR" durante o processamento.

## Convenções

- `tkcalendar.Calendar(locale="pt_BR")` — requer locale data do `babel` (já embutido no spec).
- Textos de UI, labels e logs em **pt-BR**.
- Widgets CTk expõem atributos dinâmicos — pyright já suprime `reportUnknownMemberType` em `gui/`.
- Janela: 1140×680 (min 920×580); dark/light toggle salvo por sessão; maximiza ao iniciar.
- Ao adicionar um **novo** diálogo/módulo, registrar o `hiddenimport` correspondente no `auto_oficios.spec`.

## Fases do pipeline (`processor.py`) — manter íntegro

1. Init (resolver templates, carregar banco de endereços, warm cache, conectar IA).
2. Extração via IA (por propositura; acumula tokens).
3. Agrupamento (merge por destinatário; banco de endereços tem prioridade).
4. Geração (um `.docx` por grupo em `PASTA_SAIDA`).
5. Planilha (`CONTROLE_OFICIOS.xlsx` em `PASTA_PLANILHA`).
