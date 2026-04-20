import os
import re
import json
import sys
import time
import types
import uuid
import logging
import getpass
import winreg
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, cast
# google-genai, docxtpl e openpyxl são importados de forma lazy dentro de main()
# para que o módulo possa ser carregado em testes sem essas dependências.

# =============================================================================
# CONFIGURAÇÕES GERAIS
# =============================================================================
# Configurações de Negócio
PASTA_SAIDA         = "oficios_gerados"
PASTA_LOGS          = "logs"
PASTA_PROPOSITURAS  = "proposituras"
PASTA_PLANILHA      = "planilha_gerada"

# Identificador único desta sessão — incluído em todos os registros de log.
SESSAO_ID = uuid.uuid4().hex[:8]

MESES_PT = {
    1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
    5: "maio", 6: "junho", 7: "julho", 8: "agosto",
    9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro"
}

# Mapeamento de Autores (Vereadores -> Siglas)
MAPA_AUTORES = {
    "Alex Dantas": "ad", "Arnaldo Alves": "aa", "Cabo Dorigon": "cd",
    "Careca do Esporte": "vao", "Carlos Fontes": "capf", "Celso Ávila": "clab",
    "Esther Moraes": "egsbm", "Felipe Corá": "fegc", "Gustavo Bagnoli": "gbg",
    "Isac Sorrillo": "igs", "Joi Fornasari": "jlf", "Juca Bortolucci": "ecbj",
    "Kifú": "jcss", "Lúcio Donizete": "ld", "Marcelo Cury": "mjm",
    "Paulo Monaro": "pcm", "Rony Tavares": "rgt", "Tikinho TK": "eac",
    "Wilson da Engenharia": "war"
}

# =============================================================================
# LOGGING
# =============================================================================
logger = logging.getLogger("auto_oficios")

def configurar_logging(verbose: bool = False) -> str:
    """Configura handlers de log rotativos para arquivo (DEBUG) e console.

    - Arquivo: rotação automática a cada 2 MB, mantendo os últimos 5 arquivos.
    - Console: WARNING+ por padrão; INFO+ quando verbose=True.
    - Cada linha de log inclui o ID único da sessão (SESSAO_ID).
    - Instala sys.excepthook para capturar exceções não tratadas no log.

    Returns:
        Caminho completo do arquivo de log criado.
    """
    # Evita acumulação de handlers em recargas / testes.
    logger.handlers.clear()

    Path(PASTA_LOGS).mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(PASTA_LOGS, f"auto_oficios_{timestamp}_{SESSAO_ID}.log")

    fmt = logging.Formatter(
        f"%(asctime)s [{SESSAO_ID}] [%(levelname)-8s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    fh = RotatingFileHandler(
        log_path, encoding="utf-8",
        maxBytes=2 * 1024 * 1024,  # 2 MB
        backupCount=5,
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    console_level = logging.INFO if verbose else logging.WARNING
    ch = logging.StreamHandler()
    ch.setLevel(console_level)
    ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))

    logger.setLevel(logging.DEBUG)
    logger.addHandler(fh)
    logger.addHandler(ch)

    def _excepthook(exc_type: type[BaseException], exc_value: BaseException, exc_tb: types.TracebackType | None) -> None:  # type: ignore[assignment]
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logger.critical(
            "Exceção não tratada — o processo será encerrado.",
            exc_info=(exc_type, exc_value, exc_tb),
        )

    sys.excepthook = _excepthook
    logger.debug(f"Sessão de log iniciada. ID={SESSAO_ID}")
    return log_path

# =============================================================================
# SEGURANÇA — CHAVE DE API
# =============================================================================
def _salvar_api_key_no_ambiente(chave: str) -> None:
    """Persiste a chave como variável de ambiente do usuário no registro do Windows."""
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, "Environment", access=winreg.KEY_SET_VALUE
    ) as reg:
        winreg.SetValueEx(reg, "GEMINI_API_KEY", 0, winreg.REG_SZ, chave)
    # Atualiza o processo atual sem necessidade de reiniciar
    os.environ["GEMINI_API_KEY"] = chave

def obter_api_key():
    """Lê a chave Gemini da variável de ambiente.
    Na primeira execução (chave ausente), solicita ao usuário e salva
    persistentemente no registro do Windows para uso futuro.
    """
    chave = os.environ.get("GEMINI_API_KEY", "").strip()
    if chave:
        logger.debug("GEMINI_API_KEY carregada da variável de ambiente.")
        return chave

    print("\n⚠  GEMINI_API_KEY não encontrada nas variáveis de ambiente.")
    print("   Esta configuração será solicitada apenas uma vez e salva automaticamente.\n")
    while True:
        chave = getpass.getpass("   Informe a chave da API Gemini: ").strip()
        if chave:
            break
        print("   Erro: a chave não pode ser vazia.")

    _salvar_api_key_no_ambiente(chave)
    logger.info("GEMINI_API_KEY salva como variável de ambiente do usuário.")
    print("   ✔ Chave salva. Nas próximas execuções não será solicitada novamente.\n")
    return chave

# =============================================================================
# LISTAGEM DE PROPOSITURAS
# =============================================================================
def listar_proposituras() -> list[Path]:
    """Varre a pasta PASTA_PROPOSITURAS e retorna os arquivos suportados.

    Quando dois arquivos com o mesmo nome base coexistem (ex: mocoes.txt e
    mocoes.docx), apenas a versão preferencial é incluída na lista, evitando
    duplicatas na escolha do usuário.
    """
    pasta = Path(PASTA_PROPOSITURAS)
    if not pasta.is_dir():
        return []

    formatos = set(_ORDEM_PREFERENCIA)
    vistos: dict[str, Path] = {}  # nome-base -> arquivo preferencial já escolhido

    for arq in sorted(pasta.iterdir()):
        if arq.suffix.lower() not in formatos:
            continue
        pref = Path(resolver_arquivo_preferencial(str(arq)))
        if pref.stem not in vistos:
            vistos[pref.stem] = pref

    return list(vistos.values())


# =============================================================================
# INTERFACE DE LINHA DE COMANDO
# =============================================================================
def solicitar_inputs():
    """Solicita os parâmetros de execução ao usuário via CLI."""
    print("=" * 60)
    print("   AUTO OFÍCIOS - Gerador de Ofícios Legislativos")
    print("=" * 60)

    while True:
        try:
            num_inicial = int(input("\n1. Número do ofício inicial: "))
            break
        except ValueError:
            print("   Erro: digite um número inteiro válido.")

    while True:
        sigla = input("2. Iniciais do redator: ").strip().lower()
        if sigla:
            break
        print("   Erro: as iniciais não podem ser vazias.")

    while True:
        data_str = input("3. Data dos ofícios (dd-mm-aaaa): ").strip()
        try:
            data = datetime.strptime(data_str, "%d-%m-%Y")
            data_extenso = f"{data.day} de {MESES_PT[data.month]} de {data.year}"
            data_iso = data.strftime("%Y-%m-%d")
            break
        except ValueError:
            print("   Erro: formato inválido. Use dd-mm-aaaa (ex: 18-02-2026).")

    # --- Seleção da propositura a partir da pasta proposituras/ ---
    proposituras = listar_proposituras()
    if not proposituras:
        print(f"\n   Erro: nenhum arquivo suportado encontrado em '{PASTA_PROPOSITURAS}/'.")
        print(f"   Adicione arquivos .txt/.docx/.doc/.odt/.pdf e tente novamente.")
        raise SystemExit(1)

    if len(proposituras) == 1:
        arquivo = str(proposituras[0])
        print(f"\n4. Propositura encontrada automaticamente: {proposituras[0].name}")
    else:
        print(f"\n4. Proposituras disponíveis em '{PASTA_PROPOSITURAS}/':")
        for idx, p in enumerate(proposituras, start=1):
            print(f"   [{idx}] {p.name}")
        while True:
            try:
                escolha = int(input(f"   Escolha (1-{len(proposituras)}): "))
                if 1 <= escolha <= len(proposituras):
                    arquivo = str(proposituras[escolha - 1])
                    break
                print(f"   Erro: digite um número entre 1 e {len(proposituras)}.")
            except ValueError:
                print("   Erro: entrada inválida. Digite o número da opção.")

    print("-" * 60)
    return num_inicial, sigla, data_extenso, data_iso, arquivo

# =============================================================================
# RESOLUÇÃO DE FORMATO PREFERENCIAL
# =============================================================================
_ORDEM_PREFERENCIA = (".txt", ".docx", ".doc", ".odt", ".pdf")

def resolver_arquivo_preferencial(caminho: str) -> str:
    """Dado um caminho de arquivo, verifica se existem variantes com o mesmo nome
    base em diferentes extensões suportadas e retorna o caminho de maior prioridade.
    Se não houver variante melhor, retorna o próprio caminho original.
    """
    p = Path(caminho)
    base = p.parent / p.stem
    for ext in _ORDEM_PREFERENCIA:
        candidato = base.with_suffix(ext)
        if candidato.exists():
            return str(candidato)
    return caminho

# =============================================================================
# LEITURA DE ARQUIVOS DE MOÇÕES
# =============================================================================
_ODT_NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"

def _extrair_texto_odt(caminho: str) -> str:
    """Extrai texto de um arquivo .odt usando zipfile + xml.etree (sem dependências extras)."""
    import zipfile
    import xml.etree.ElementTree as ET

    with zipfile.ZipFile(caminho, "r") as z:
        with z.open("content.xml") as f:
            tree = ET.parse(f)

    partes: list[str] = []
    for elem in tree.iter():
        if elem.tag == f"{{{_ODT_NS}}}p" or elem.tag == f"{{{_ODT_NS}}}line-break":
            partes.append("".join(t for t in elem.itertext()))
    return "\n".join(partes)

def ler_arquivo_mocoes(caminho: str) -> str:
    """Lê e extrai o texto de um arquivo .txt, .docx, .doc, .odt ou .pdf."""
    sufixo = Path(caminho).suffix.lower()

    if sufixo == ".txt":
        with open(caminho, "r", encoding="utf-8") as f:
            return f.read()

    if sufixo == ".docx":
        import docx as _docx
        doc = _docx.Document(caminho)
        return "\n".join(p.text for p in doc.paragraphs)

    if sufixo == ".doc":
        try:
            import win32com.client
        except ImportError:
            raise ImportError("Para ler arquivos .doc instale pywin32: pip install pywin32")
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        try:
            doc = word.Documents.Open(str(Path(caminho).resolve()))
            texto = doc.Content.Text
            doc.Close(False)
        finally:
            word.Quit()
        return texto

    if sufixo == ".odt":
        return _extrair_texto_odt(caminho)

    if sufixo == ".pdf":
        try:
            import pypdf as _pypdf
        except ImportError:
            raise ImportError("Para ler arquivos .pdf instale pypdf: pip install pypdf")
        reader = _pypdf.PdfReader(caminho)
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    raise ValueError(f"Formato '{sufixo}' não suportado. Use .txt, .docx, .doc, .odt ou .pdf.")

# =============================================================================
# FUNÇÕES AUXILIARES (testáveis)
# =============================================================================
def normalizar_numero_mocao(numero: str) -> str:
    """Remove sufixo de ano que a IA pode incluir no número da moção.

    Exemplos: '124/2026' → '124', '124-26' → '124', '124' → '124'.
    """
    return re.sub(r'[-/]\d{2,4}$', '', numero).strip()


def construir_nome_arquivo(
    num_oficio_str: str,
    sigla_servidor: str,
    tipo_mocao: str,
    num_mocao: str,
    envio: str,
    nome_dest: str,
    sigla_autores: str,
) -> str:
    """Monta o nome do arquivo de ofício e remove caracteres inválidos no Windows."""
    nome = (
        f"Of. {num_oficio_str} - {sigla_servidor} - "
        f"Moção de {tipo_mocao} nº {num_mocao}-26 - "
        f"{envio.lower()} - {nome_dest} - {sigla_autores}.docx"
    )
    return re.sub(r'[\\/*?:"<>|]', "", nome)


def limpar_json_da_resposta(texto: str) -> str:
    """Remove marcadores de bloco de código Markdown da resposta textual da IA."""
    texto = texto.strip()
    if texto.startswith("```json"):
        texto = texto.split("```json")[1].split("```")[0].strip()
    elif texto.startswith("```"):
        texto = texto.split("```")[1].split("```")[0].strip()
    return texto

def validar_dados_mocao(dados: dict[str, Any]) -> None:
    """Valida campos obrigatórios no dicionário retornado pela IA. Lança ValueError se inválido."""
    for campo in ("tipo_mocao", "numero_mocao", "autores", "destinatarios"):
        if campo not in dados or not dados[campo]:
            raise ValueError(f"Campo obrigatório ausente ou vazio na resposta da IA: '{campo}'")
    if dados["tipo_mocao"] not in ("Aplauso", "Apelo"):
        raise ValueError(f"tipo_mocao inválido recebido da IA: '{dados['tipo_mocao']}'")
    if not isinstance(dados["autores"], list):
        raise ValueError("'autores' deve ser uma lista.")
    if not isinstance(dados["destinatarios"], list):
        raise ValueError("'destinatarios' deve ser uma lista.")
    for i, dest in enumerate(dados["destinatarios"]):  # type: ignore[union-attr]
        if not dest.get("nome"):  # type: ignore[union-attr]
            raise ValueError(f"Destinatário {i + 1} sem campo 'nome'.")

# =============================================================================
# FUNÇÕES DE PROCESSAMENTO E IA
# =============================================================================
def extrair_dados_com_ia(texto_mocao: str, cliente_genai: Any) -> dict[str, Any]:
    """Envia o texto da moção para o Gemini e retorna um JSON estruturado."""
    prompt = f"""
    Atue como um assistente legislativo. Leia o texto da moção abaixo e extraia os dados estritamente no formato JSON.
    Se houver múltiplos destinatários exigidos na moção, retorne todos na lista 'destinatarios'.
    
    Formato JSON esperado:
    {{
        "tipo_mocao": "Aplauso" ou "Apelo",
        "numero_mocao": "124",
        "autores": ["Nome do Vereador 1", "Nome do Vereador 2"],
        "destinatarios": [
            {{
                "nome": "Nome da pessoa ou instituição",
                "cargo_ou_tratamento": "Ex: Presidente da CDHU / Aos cuidados de...",
                "endereco": "Endereço completo se houver no texto, senão vazio",
                "email": "Email se houver, senão vazio",
                "is_prefeito": true ou false,
                "is_instituicao": true ou false
            }}
        ]
    }}
    
    Texto da moção:
    {texto_mocao}
    """
    
    MAX_TENTATIVAS = 5
    logger.debug("Enviando moção à API Gemini.")
    for tentativa in range(MAX_TENTATIVAS):
        try:
            response = cliente_genai.models.generate_content(
                model="gemini-3.1-pro-preview",
                contents=prompt,
            )
            logger.debug(f"Resposta recebida (tentativa {tentativa + 1}).")
        except Exception as e:
            msg = str(e)
            match = re.search(r'retry_delay\s*\{\s*seconds:\s*(\d+)', msg)
            espera = int(match.group(1)) + 2 if match else 60
            if '429' in msg:
                logger.warning(f"Rate limit atingido. Aguardando {espera}s (tentativa {tentativa + 1}/{MAX_TENTATIVAS}).")
                print(f"   Rate limit atingido. Aguardando {espera}s antes de tentar novamente...")
                time.sleep(espera)
                continue
            else:
                logger.error(f"Erro na API Gemini: {e}", exc_info=True)
                raise

        raw_text: str = response.text  # type: ignore[union-attr]
        logger.debug(f"Resposta bruta da IA (tentativa {tentativa + 1}): {raw_text!r}")
        try:
            json_str = limpar_json_da_resposta(raw_text)
            data: Any = json.loads(json_str)
            resultado: dict[str, Any] = cast(dict[str, Any], data[0] if isinstance(data, list) else data)
            validar_dados_mocao(resultado)
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(
                f"Resposta inválida da IA (tentativa {tentativa + 1}/{MAX_TENTATIVAS}): {e}. "
                f"Resposta bruta: {raw_text!r}"
            )
            if tentativa < MAX_TENTATIVAS - 1:
                continue
            raise

        logger.debug(
            f"Dados extraídos — moção nº {resultado.get('numero_mocao')}, "
            f"tipo: {resultado.get('tipo_mocao')}."
        )
        return resultado

    raise Exception("Número máximo de tentativas excedido.")

def formatar_autores(lista_autores: list[str]) -> tuple[str, str]:
    """Formata o texto de autoria (singular/plural) e gera a sigla combinada."""
    siglas: list[str] = []
    nomes_limpos: list[str] = []
    
    for autor in lista_autores:
        # Busca a sigla no mapa ignorando maiúsculas/minúsculas
        sigla = next((s for nome, s in MAPA_AUTORES.items() if nome.lower() in autor.lower()), "indef")
        siglas.append(sigla.upper())
        nomes_limpos.append(autor)
        
    sigla_final = "-".join(siglas)
    
    if len(nomes_limpos) == 1:
        texto_autoria = f"do vereador {nomes_limpos[0]}"
    else:
        nomes_str = ", ".join(nomes_limpos[:-1]) + " e " + nomes_limpos[-1]
        texto_autoria = f"dos vereadores {nomes_str}"
        
    return texto_autoria, sigla_final

def processar_destinatario(dest: dict[str, Any]) -> dict[str, str]:
    """Aplica as regras de negócio para endereço, envio e tratamento."""
    # Regra do Prefeito
    if dest.get("is_prefeito") or "prefeito" in dest.get("nome", "").lower():
        return {
            "tratamento_rodape": "A Sua Excelência, o Senhor",
            "destinatario_nome": "RAFAEL PIOVEZAN",
            "destinatario_endereco": "Prefeito Municipal\nSanta Bárbara d’Oeste/SP",
            "vocativo": "Excelentíssimo Senhor Prefeito",
            "pronome_corpo": "Vossa Excelência",
            "envio": "Protocolo"
        }
    
    # Tratamento Rodapé
    is_inst = dest.get("is_instituicao", False)
    if is_inst:
        tratamento_rodape = "Ao" if not dest["nome"].lower().startswith("a") else "À"
    else:
        tratamento_rodape = "Ao Ilustríssimo Senhor"

    # Endereço
    endereco_final = dest.get("cargo_ou_tratamento", "")
    if dest.get("endereco"):
        endereco_final += f"\n{dest['endereco']}"
    if dest.get("email"):
        endereco_final += f"\n{dest['email']}"
        
    # Forma de Envio
    if dest.get("email"):
        envio = "E-mail"
    elif dest.get("endereco"):
        envio = "Carta"
    else:
        envio = "Em Mãos"

    return {
        "tratamento_rodape": tratamento_rodape,
        "destinatario_nome": dest["nome"].upper(),
        "destinatario_endereco": endereco_final.strip(),
        "vocativo": "Ilustríssimo(a) Senhor(a)",
        "pronome_corpo": "Vossa Senhoria",
        "envio": envio
    }

# =============================================================================
# EXECUÇÃO PRINCIPAL
# =============================================================================
def main():
    # Imports pesados carregados aqui para não bloquear testes unitários.
    from google import genai  # noqa: PLC0415
    from docxtpl import DocxTemplate  # type: ignore[import-untyped]  # noqa: PLC0415
    from openpyxl import Workbook  # noqa: PLC0415

    log_path = configurar_logging()
    NUMERO_OFICIO_INICIAL, SIGLA_SERVIDOR, DATA_EXTENSO, DATA_ISO, ARQUIVO_MOCOES = solicitar_inputs()
    inicio = time.time()

    try:
        api_key = obter_api_key()
    except ValueError as e:
        logger.critical(str(e))
        print(f"Erro fatal: {e}")
        return
    cliente_genai = genai.Client(api_key=api_key)

    logger.info(
        f"Sessão iniciada — ofício inicial: {NUMERO_OFICIO_INICIAL}, "
        f"redator: '{SIGLA_SERVIDOR}', data: '{DATA_EXTENSO}'."
    )
    print(f"   Log salvo em: {log_path}\n")

    Path(PASTA_SAIDA).mkdir(exist_ok=True)

    if not Path("modelo_oficio.docx").exists():
        logger.critical("Arquivo 'modelo_oficio.docx' não encontrado.")
        print("Erro: Arquivo 'modelo_oficio.docx' não encontrado.")
        return

    # 1. Ler o arquivo de moções
    try:
        conteudo_completo = ler_arquivo_mocoes(ARQUIVO_MOCOES)
    except Exception as e:
        logger.critical(f"Erro ao ler arquivo de moções '{ARQUIVO_MOCOES}': {e}")
        print(f"Erro ao ler arquivo: {e}")
        return

    textos_mocoes = re.split(r'(?=MOÇÃO Nº)', conteudo_completo)
    textos_mocoes = [t.strip() for t in textos_mocoes if t.strip()]

    print(f"Foram encontradas {len(textos_mocoes)} moções. Iniciando processamento com IA...")
    logger.info(f"{len(textos_mocoes)} moções encontradas no arquivo.")

    dados_planilha: list[list[str]] = []
    numero_oficio_atual = NUMERO_OFICIO_INICIAL
    erros = 0

    for i, texto in enumerate(textos_mocoes, start=1):
        print(f"Processando moção {i}/{len(textos_mocoes)}...")
        logger.info(f"--- Moção {i}/{len(textos_mocoes)} ---")
        try:
            dados_mocao = extrair_dados_com_ia(texto, cliente_genai)
        except (ValueError, json.JSONDecodeError) as e:
            logger.error(f"Dados inválidos na moção {i}: {e}")
            print(f"   Erro nos dados da moção {i}: {e}")
            erros += 1
            continue
        except Exception as e:
            logger.error(f"Erro ao processar moção {i}: {e}", exc_info=True)
            print(f"   Erro ao processar moção {i}: {e}")
            erros += 1
            continue

        dados_mocao["numero_mocao"] = normalizar_numero_mocao(dados_mocao["numero_mocao"])

        texto_autoria, sigla_autores = formatar_autores(dados_mocao["autores"])

        for dest in dados_mocao["destinatarios"]:
            info_dest = processar_destinatario(dest)
            num_oficio_str = f"{numero_oficio_atual:03d}"

            contexto: dict[str, str] = {
                "num_oficio": num_oficio_str,
                "data_extenso": DATA_EXTENSO,
                "tipo_mocao": str(dados_mocao["tipo_mocao"]),
                "num_mocao": str(dados_mocao["numero_mocao"]),
                "vocativo": info_dest["vocativo"],
                "pronome_corpo": info_dest["pronome_corpo"],
                "texto_autoria": texto_autoria,
                "tratamento_rodape": info_dest["tratamento_rodape"],
                "destinatario_nome": info_dest["destinatario_nome"],
                "destinatario_endereco": info_dest["destinatario_endereco"]
            }

            doc = DocxTemplate("modelo_oficio.docx")
            doc.render(contexto)  # type: ignore[arg-type]

            nome_arquivo = construir_nome_arquivo(
                num_oficio_str, SIGLA_SERVIDOR,
                dados_mocao["tipo_mocao"], dados_mocao["numero_mocao"],
                info_dest["envio"], dest["nome"], sigla_autores,
            )

            caminho_salvar = os.path.join(PASTA_SAIDA, nome_arquivo)
            doc.save(caminho_salvar)  # type: ignore[arg-type]
            logger.info(f"Gerado: {nome_arquivo}")
            print(f" ✔ Gerado: {nome_arquivo}")

            assunto_planilha = f"Encaminha Moção de {dados_mocao['tipo_mocao']} nº {dados_mocao['numero_mocao']}/2026"
            dados_planilha.append([
                num_oficio_str,
                DATA_ISO,
                f"{info_dest['tratamento_rodape']} {info_dest['destinatario_nome']}".strip(),
                assunto_planilha,
                ", ".join(dados_mocao["autores"]),
                info_dest["envio"],
                SIGLA_SERVIDOR
            ])

            numero_oficio_atual += 1

    # 2. Gerar Planilha Excel de Controle
    print("\nGerando planilha de controle Excel...")
    logger.info("Gerando planilha Excel de controle...")
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Controle 2026"

    cabecalhos = ["Of. n.º", "Data", "Destinatário", "Assunto", "Vereador", "Envio", "Autor"]
    ws.append(cabecalhos)
    for linha in dados_planilha:
        ws.append(linha)
    Path(PASTA_PLANILHA).mkdir(exist_ok=True)
    wb.save(os.path.join(PASTA_PLANILHA, "CONTROLE_OFICIOS.xlsx"))

    elapsed = time.time() - inicio
    minutos, segundos = divmod(int(elapsed), 60)
    tempo_str = f"{minutos}m {segundos}s" if minutos else f"{segundos}s"
    resumo = f"{len(dados_planilha)} ofício(s) gerado(s), {erros} erro(s)."

    print(f"\n✨ Processo concluído! Documentos e planilha gerados com sucesso.")
    print(f"   Resumo: {resumo}")
    print(f"⏱ Tempo decorrido: {tempo_str}")
    logger.info(f"Processo concluído. {resumo} Tempo: {tempo_str}.")

if __name__ == "__main__":
    main()