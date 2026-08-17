# Z7 OfficeLetters

Ferramenta de automação para geração de ofícios legislativos municipais.

Utiliza a API **OpenRouter** (com modelos como Llama 3.3 e Gemma 2) para extrair dados estruturados a partir do texto de moções legislativas e gera automaticamente os documentos Word e uma planilha de controle.

## Funcionalidades

- Leitura de moções a partir de arquivos `.txt`, `.docx`, `.odt` ou `.pdf`
- Extração automática de dados via IA (OpenRouter — múltiplos modelos configuráveis)
- Sistema de fallback automático entre modelos de IA
- Geração de ofícios em `.docx` a partir de modelo Word
- Suporte a múltiplos destinatários por moção
- Aplicação de regras de negócio para endereçamento, tratamento e forma de envio
- Geração de planilha de controle (`.xlsx`)
- Geração de envelopes
- Conferência e autocorreção automática dos documentos gerados
- Log detalhado por sessão com contexto estruturado
- Armazenamento seguro da chave de API no Credential Manager do Windows
- Atualização automática via GitHub Releases

## Pré-requisitos

- Windows 10 ou superior
- Python 3.12+
- Chave de API OpenRouter ([obter aqui](https://openrouter.ai/keys))

## Instalação

```bash
# Clone o repositório
git clone https://github.com/chrmsantos/Z7_OfficeLetters.git
cd Z7_OfficeLetters

# Crie e ative o ambiente virtual
python -m venv .venv
.venv\Scripts\activate

# Instale as dependências
pip install openai docxtpl openpyxl pypdf python-docx keyring send2trash customtkinter tkcalendar
```

## Uso

### Arquivos necessários antes de executar

| Arquivo | Descrição |
| --- | --- |
| `proposituras/*.txt` | Texto das moções/requerimentos (um ou mais arquivos) |
| `templates/modelo_mocao.docx` | Template Word para moções |
| `templates/modelo_requer_pesar.docx` | Template Word para requerimentos de pesar |
| `templates/modelo_planilha.xlsx` | Template da planilha de controle |
| `templates/modelo_envelope.docx` | Template de envelope |
| `ender/enderecamentos_padrao.docx` | Base de endereços dos destinatários |

### Executar

```bash
python -m z7_officeletters
```

A interface gráfica permite configurar número do ofício inicial, redator, data, chave de API e modelo de IA.

### Saídas geradas

```text
local/
├── oficios_gerados/          # Documentos .docx gerados
├── planilha_gerada/          # Planilha de controle
└── envelopes_gerados/        # Envelopes gerados
```

## Estrutura do projeto

```text
Z7_OfficeLetters/
├── pyproject.toml           # Metadados, ruff, pyright, pytest
├── config.json              # Configuração (autores, prefeito, redatores)
├── auto_oficios.spec        # Spec PyInstaller
├── build.py                 # Script de compilação segura
├── icon.ico                 # Ícone da aplicação
├── ai_context.md            # Documentação de referência
├── src/
│   └── z7_officeletters/
│       ├── __main__.py      # Ponto de entrada
│       ├── constants.py     # Constantes globais
│       ├── core/            # Lógica de negócio
│       └── gui/             # Interface gráfica
├── templates/               # Templates Word/Excel
├── ender/                   # Base de endereços
└── tests/                   # Testes unitários
```

## Testes

```bash
python -m pytest tests/ -v
```

## Compilação

```bash
python build.py
```

O executável será gerado em `dist/Z7_OfficeLetters.exe`.

## Licença

GNU GPL v3.0
