# Z7 OfficeLetters

Ferramenta de automação para geração de ofícios legislativos da Câmara Municipal de Santa Bárbara d'Oeste/SP.

Utiliza a API **Google Gemini** para extrair dados estruturados a partir do texto de moções legislativas e gera automaticamente os documentos Word e uma planilha de controle.

## Funcionalidades

- Leitura de moções a partir de arquivo de texto (`mocoes.txt`)
- Extração automática de dados via IA (Google Gemini 2.0 Flash)
- Geração de ofícios em `.docx` a partir de modelo Word
- Suporte a múltiplos destinatários por moção
- Aplicação de regras de negócio para endereçamento, tratamento e forma de envio
- Geração de planilha de controle (`.xlsx`)
- Log detalhado por sessão
- Armazenamento seguro da chave de API no registro do Windows

## Pré-requisitos

- Windows 10 ou superior
- Python 3.11+
- Chave de API Google Gemini ([obter aqui](https://aistudio.google.com/app/apikey))

## Instalação

```bash
# Clone o repositório
git clone https://github.com/chrmsantos/Z7_OfficeLetters.git
cd Z7_OfficeLetters

# Crie e ative o ambiente virtual
python -m venv .venv
.venv\Scripts\activate

# Instale as dependências
pip install google-genai docxtpl openpyxl pytest
```

## Uso

### Arquivos necessários antes de executar

| Arquivo | Descrição |
| --- | --- |
| `mocoes.txt` | Texto completo das moções, uma após a outra |
| `modelo_oficio.docx` | Template Word com as variáveis de contexto |

### Executar

```bash
python auto_oficios.py
```

O programa solicitará interativamente:

1. **Número do ofício inicial** — número inteiro para o primeiro ofício da sequência
2. **Iniciais do redator** — sigla do servidor responsável
3. **Data dos ofícios** — no formato `dd-mm-aaaa`

Na primeira execução, a chave da API Gemini será solicitada e salva automaticamente como variável de ambiente do usuário no Windows — nas execuções seguintes não será pedida novamente.

### Saídas geradas

```text
oficios_gerados/          # Documentos .docx gerados
logs/                     # Logs de cada sessão
CONTROLE_OFICIOS_FINAL.xlsx  # Planilha de controle consolidada
```

## Estrutura do projeto

```text
Z7_OfficeLetters/
├── auto_oficios.py           # Código principal
├── ui.py                     # Interface gráfica
├── config.json               # Configuração (autores, prefeito)
├── auto_oficios.spec         # Spec PyInstaller
├── tests/
│   └── test_auto_oficios.py  # Testes unitários
└── README.md
```

## Testes

```bash
pytest tests/ -v
```

## Licença

Este projeto é licenciado sob a [GNU General Public License v3.0](LICENSE).
