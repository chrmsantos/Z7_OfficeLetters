---
paths:
  - "src/z7_officeletters/core/ai.py"
  - "src/z7_officeletters/core/api_key.py"
  - "src/z7_officeletters/core/address_db.py"
  - "src/z7_officeletters/core/recipients.py"
---

# Integração com IA (OpenRouter / Gemini)

## Fluxo

- Modelo primário `deepseek/deepseek-chat`; fallback `google/gemini-2.5-flash`
  (persistido via keyring, sobrescrevível por sessão no diálogo "Advanced").
- `extrair_dados_com_ia()` tenta até `MAX_TENTATIVAS_IA` (5). HTTP 429 → `time.sleep(RETRY_DELAY_PADRAO_S + 2)`.
- Respostas inválidas (JSON/schema) → retry silencioso. O bloco `finally` **sempre** grava o log JSONL.

## Regras

- Chaves **nunca** em texto claro no código — persistir via `keyring` (Windows Credential Manager);
  `migrar_chave_do_registro()` cobre a migração do legado.
- Todo registro de chamada vai para `logs/ia/*.jsonl` via `registrar_chamada_ia()` — preservar o schema.
- Prompts sobrescrevíveis via GUI (Prompt Editor) — usar `PROMPT_TEMPLATE` / `PROMPT_TEMPLATE_PESAR`.
- Banco de endereços tem prioridade sobre dados extraídos (nome, cargo, endereço, e-mail, tratamento).
- Validação por `validar_dados_mocao` / `validar_dados_requerimento_pesar`.
- Alertas via `_gerar_alertas()` são **soft warnings** — não abortam o processamento.

## Schema esperado (moção)

```json
{
  "propositura": "moção",
  "tipo_mocao": "Aplauso | Apelo | Apoio | Protesto",
  "numero_mocao": "432",
  "autores": ["Nome Vereador"],
  "destinatarios": [{
    "nome": "...", "cargo_ou_tratamento": "...", "endereco": "...",
    "email": "...", "is_prefeito": false, "is_instituicao": false, "genero": "M|F"
  }]
}
```

Requerimento de pesar adiciona `numero_requerimento` e `falecido`, e omite `tipo_mocao`.

## Debug

- Resposta bruta: truncada a 500 chars no log Python (DEBUG), **completa** no JSONL.
- Para analisar o log JSONL, usar o skill `debug-ai-log`.
