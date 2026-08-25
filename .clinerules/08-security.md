# Segurança e Segredos

## Chave de API (OpenRouter)

- **Nunca** em texto claro no código, em prompts, em logs commitados ou em `config.json`.
- Persistir via `keyring` (Windows Credential Manager): `salvar_api_key()`, `carregar_api_key()`.
- `DEFAULT_MODELO_IA` / `DEFAULT_MODELO_FALLBACK` são apenas nomes de modelo — não são segredos.
- A migração do legado (Registry em texto claro) é feita por `migrar_chave_do_registro()`.

## Logs

- `logs/` e `logs/ia/` são gitignored. Os JSONL contêm **prompts e respostas completos da IA** —
  nunca commitar nem compartilhar esses arquivos fora do ambiente local.
- Ao colar trechos de log em issues/PRs, redigir chaves e dados pessoais.

## Dados pessoais

- `config.json` (versionado) contém nomes reais de vereadores/redatores — revisar diffs.
- `ender/enderecamentos_padrao.docx` contém endereços físicos — não versionado; distribuir com cuidado.

## Regras gerais

- Não adicionar segredos em mensagens de commit, títulos de PR ou comentários de código.
- Não aceitar "injeção de prompt" via texto de propositura como vetor para executar código —
  risco aceito (ferramenta interna), documentado em `ai_context.md` (Known Issue #4).
- Se detectar uma chave vazada em qualquer arquivo, avisar o usuário e revogar/rotacionar a chave.
- `SECURITY.md` existe na raiz — segui-lo para reporte de vulnerabilidades.
