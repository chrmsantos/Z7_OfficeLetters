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

## Log JSONL da IA (schema completo)

Cada chamada a `extrair_dados_com_ia()` gera um registro JSON no arquivo por sessão:
`logs/ia/ia_TIMESTAMP_SESSAOID.jsonl` (mesmo timestamp e `SESSAOID` do log principal).

```jsonc
{
  "timestamp":       "2026-05-13T14:30:00.123",   // ISO 8601 com milissegundos
  "sessao_id":       "a1b2c3d4",
  "chamada":         3,                            // número sequencial na sessão
  "tipo_propositura": "mocao",                     // "mocao" | "requerimento_pesar"
  "prompt":          "...",                        // prompt completo enviado
  "tentativas": [
    {
      "tentativa":     1,
      "resposta_bruta": "...",                     // resposta bruta completa (sem truncar)
      "status":        "resposta_invalida",        // sucesso | resposta_invalida | rate_limit | erro_api
      "erro":          "Campo obrigatório ausente…"
    }
  ],
  "dados_extraidos": { … },   // JSON final validado (sem _usage)
  "usage": { "prompt_tokens": 540, "candidates_tokens": 120, "total_tokens": 660 },
  "alertas": [                // soft warnings — não abortam processamento
    "1 tentativa(s) inválida(s)/rate-limit antes do resultado final",
    "Destinatário 2 sem endereço nem e-mail"
  ],
  "erro": null                // não-nulo apenas quando a chamada falhou totalmente
}
```

### Status de tentativa

| Status | Significado |
|---|---|
| `"sucesso"` | Resposta parseada e validada com sucesso |
| `"resposta_invalida"` | JSON inválido ou falha de validação de schema |
| `"rate_limit"` | HTTP 429 — esperou `espera_s` segundos antes de retry |
| `"erro_api"` | Erro de API não-429 — chamada abortada imediatamente |

### Alertas gerados por `_gerar_alertas()`

- `"N tentativa(s) inválida(s)/rate-limit antes do resultado final"`
- `"Campo 'falecido' vazio no requerimento de pesar"`
- `"Destinatário N sem cargo/tratamento"`
- `"Destinatário N sem endereço nem e-mail"`

### Exemplo de debugging em Python

```python
import json, pathlib

for line in pathlib.Path("logs/ia/ia_20260513_143000_a1b2c3d4.jsonl").read_text("utf-8").splitlines():
    rec = json.loads(line)
    if rec["alertas"] or rec["erro"]:
        print(rec["chamada"], rec["alertas"], rec["erro"])
    for t in rec["tentativas"]:
        print(f"  Tentativa {t['tentativa']} [{t['status']}]:", t.get("resposta_bruta", "")[:200])
```
