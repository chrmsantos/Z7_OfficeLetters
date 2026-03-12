import os
import re
import json
import time
import logging
import getpass
import winreg
from datetime import datetime
from pathlib import Path
from google import genai
from docxtpl import DocxTemplate
from openpyxl import Workbook

# =============================================================================
# CONFIGURAÇÕES GERAIS
# =============================================================================
# Configurações de Negócio
PASTA_SAIDA = "oficios_gerados"
PASTA_LOGS  = "logs"

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

def configurar_logging():
    """Configura handlers de log para arquivo (DEBUG) e console (WARNING+)."""
    Path(PASTA_LOGS).mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(PASTA_LOGS, f"auto_oficios_{timestamp}.log")

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))

    logger.setLevel(logging.DEBUG)
    logger.addHandler(fh)
    logger.addHandler(ch)
    return log_path

# =============================================================================
# SEGURANÇA — CHAVE DE API
# =============================================================================
def _salvar_api_key_no_ambiente(chave):
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

    print("-" * 60)
    return num_inicial, sigla, data_extenso, data_iso

# =============================================================================
# FUNÇÕES AUXILIARES (testáveis)
# =============================================================================
def limpar_json_da_resposta(texto):
    """Remove marcadores de bloco de código Markdown da resposta textual da IA."""
    texto = texto.strip()
    if texto.startswith("```json"):
        texto = texto.split("```json")[1].split("```")[0].strip()
    elif texto.startswith("```"):
        texto = texto.split("```")[1].split("```")[0].strip()
    return texto

def validar_dados_mocao(dados):
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
    for i, dest in enumerate(dados["destinatarios"]):
        if not dest.get("nome"):
            raise ValueError(f"Destinatário {i + 1} sem campo 'nome'.")

# =============================================================================
# FUNÇÕES DE PROCESSAMENTO E IA
# =============================================================================
def extrair_dados_com_ia(texto_mocao, cliente_genai):
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
    
    logger.debug("Enviando moção à API Gemini.")
    for tentativa in range(5):
        try:
            response = cliente_genai.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            logger.debug(f"Resposta recebida (tentativa {tentativa + 1}).")
            break
        except Exception as e:
            msg = str(e)
            match = re.search(r'retry_delay\s*\{\s*seconds:\s*(\d+)', msg)
            espera = int(match.group(1)) + 2 if match else 60
            if '429' in msg:
                logger.warning(f"Rate limit atingido. Aguardando {espera}s (tentativa {tentativa + 1}/5).")
                print(f"   Rate limit atingido. Aguardando {espera}s antes de tentar novamente...")
                time.sleep(espera)
            else:
                logger.error(f"Erro na API Gemini: {e}", exc_info=True)
                raise
    else:
        raise Exception("Número máximo de tentativas excedido por rate limit.")

    json_str = limpar_json_da_resposta(response.text)
    resultado = json.loads(json_str)
    if isinstance(resultado, list):
        resultado = resultado[0]

    validar_dados_mocao(resultado)
    logger.debug(
        f"Dados extraídos — moção nº {resultado.get('numero_mocao')}, "
        f"tipo: {resultado.get('tipo_mocao')}."
    )
    return resultado

def formatar_autores(lista_autores):
    """Formata o texto de autoria (singular/plural) e gera a sigla combinada."""
    siglas = []
    nomes_limpos = []
    
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

def processar_destinatario(dest):
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
    log_path = configurar_logging()
    NUMERO_OFICIO_INICIAL, SIGLA_SERVIDOR, DATA_EXTENSO, DATA_ISO = solicitar_inputs()
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
        with open("mocoes.txt", "r", encoding="utf-8") as f:
            conteudo_completo = f.read()
    except FileNotFoundError:
        logger.critical("Arquivo 'mocoes.txt' não encontrado.")
        print("Erro: Arquivo 'mocoes.txt' não encontrado.")
        return

    textos_mocoes = re.split(r'(?=MOÇÃO Nº)', conteudo_completo)
    textos_mocoes = [t.strip() for t in textos_mocoes if t.strip()]

    print(f"Foram encontradas {len(textos_mocoes)} moções. Iniciando processamento com IA...")
    logger.info(f"{len(textos_mocoes)} moções encontradas no arquivo.")

    dados_planilha = []
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

        texto_autoria, sigla_autores = formatar_autores(dados_mocao["autores"])

        for dest in dados_mocao["destinatarios"]:
            info_dest = processar_destinatario(dest)
            num_oficio_str = f"{numero_oficio_atual:03d}"

            contexto = {
                "num_oficio": num_oficio_str,
                "data_extenso": DATA_EXTENSO,
                "tipo_mocao": dados_mocao["tipo_mocao"],
                "num_mocao": dados_mocao["numero_mocao"],
                "vocativo": info_dest["vocativo"],
                "pronome_corpo": info_dest["pronome_corpo"],
                "texto_autoria": texto_autoria,
                "tratamento_rodape": info_dest["tratamento_rodape"],
                "destinatario_nome": info_dest["destinatario_nome"],
                "destinatario_endereco": info_dest["destinatario_endereco"]
            }

            doc = DocxTemplate("modelo_oficio.docx")
            doc.render(contexto)

            nome_arquivo = (
                f"Of. {num_oficio_str} - {SIGLA_SERVIDOR} - "
                f"Moção de {dados_mocao['tipo_mocao']} nº {dados_mocao['numero_mocao']}-26 - "
                f"{info_dest['envio'].lower()} - {dest['nome']} - {sigla_autores}.docx"
            )
            nome_arquivo = re.sub(r'[\\/*?:"<>|]', "", nome_arquivo)

            caminho_salvar = os.path.join(PASTA_SAIDA, nome_arquivo)
            doc.save(caminho_salvar)
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
    ws.title = "Controle 2026"

    cabecalhos = ["Of. n.º", "Data", "Destinatário", "Assunto", "Vereador", "Envio", "Autor"]
    ws.append(cabecalhos)
    for linha in dados_planilha:
        ws.append(linha)
    wb.save("CONTROLE_OFICIOS_FINAL.xlsx")

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