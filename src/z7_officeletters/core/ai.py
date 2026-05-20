"""Gemini AI integration and prompt management.

Handles the full lifecycle of a single AI extraction call:
loading the prompt template, sending the request with exponential-back-off
retry on rate limits, parsing the response JSON, and validating the schema.

The prompt template can be overridden by placing a ``prompt_template.txt``
file next to the executable (frozen) or next to this module (dev mode).

Public exports:
    PROMPT_TEMPLATE_PADRAO: Built-in prompt template string (read-only).
    PROMPT_TEMPLATE: Active template (may be replaced by a user file or GUI).
    carregar_prompt_template: Load the template from disk or return the default.
    limpar_json_da_resposta: Strip Markdown code fences from an AI response.
    validar_dados_mocao: Validate required fields in the AI response dict.
    extrair_dados_com_ia: Send a motion text to Gemini and return parsed data.
"""

from __future__ import annotations

import json
import re
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from z7_officeletters.constants import MAX_TENTATIVAS_IA, RETRY_DELAY_PADRAO_S
from z7_officeletters.core.logging_setup import SESSAO_ID, logger, registrar_chamada_ia

__all__ = [
    "PROMPT_TEMPLATE_PADRAO",
    "PROMPT_TEMPLATE",
    "PROMPT_TEMPLATE_PESAR_PADRAO",
    "PROMPT_TEMPLATE_PESAR",
    "MODELO_IA",
    "carregar_prompt_template",
    "carregar_prompt_template_pesar",
    "limpar_json_da_resposta",
    "validar_dados_mocao",
    "validar_dados_requerimento_pesar",
    "extrair_dados_com_ia",
]

# ── Built-in prompt (shipped with the application) ───────────────────────────
PROMPT_TEMPLATE_PADRAO: str = (
    "    Atue como um assistente legislativo. Leia o texto da(s) propositura(s) (moção(ões) e/ou requerimento(s) de pesar) abaixo e extraia os dados estritamente no formato JSON.\n"
    "    Cada propositura pode conter um ou mais destinatários. Para cada destinatário, classifique o tipo e extraia apenas os campos efetivamente presentes no texto.\n"
    "    REGRA FUNDAMENTAL: Omita do JSON qualquer campo que não esteja presente no texto da propositura. Não inclua campos vazios, não deixe valores em branco e não mencione ausência de dados.\n"
    "    Se houver múltiplos destinatários exigidos em uma propositura, retorne todos na lista 'destinatarios'.\n"
    "    Se o texto mencionar que o destinatário é o prefeito ou a prefeitura, marque 'is_prefeito' como true.\n"
    "    O campo 'numero_mocao' deve conter apenas o número sequencial da moção, sem sufixos de ano ou outros caracteres. Ex: '432' em vez de '432/2026'.\n"
    "    O campo 'tipo_mocao' deve ser classificado como 'Aplauso', 'Apelo', 'Apoio' ou 'Protesto' com base no conteúdo da moção.\n"
    "    O campo 'autores' deve ser uma lista de nomes completos dos vereadores autores da moção, conforme mencionados no texto. Se o texto mencionar apenas o cargo (ex: 'os vereadores'), use 'Vereador(a) Indefinido(a)'.\n"
    "    O campo 'destinatarios' deve ser uma lista de objetos identificados a partir do trecho de encaminhamento da cópia (ex: 'Solicito... que seja encaminhada cópia...') ou do cabeçalho/título da propositura.\n"
    "    REGRA DE DESTINATÁRIOS: Inclua como destinatário apenas quem (a) estiver mencionado na ementa da propositura, ou (b) o texto indicar expressamente que a propositura deve ser encaminhada. Pessoas ou instituições meramente citadas no corpo do texto, sem instrução explícita de encaminhamento e sem menção na ementa, nunca devem ser incluídas na lista 'destinatarios'.\n"
    "    REGRA DE APELIDO: Quando o texto mencionar uma pessoa pelo nome completo e também por um apelido ou nome de guerra (ex.: policiais militares e civis, agentes públicos), trate-os como UM ÚNICO destinatário. Inclua ambos no campo 'nome' no formato \"NOME COMPLETO (APELIDO)\". Nunca crie dois destinatários separados para a mesma pessoa por causa de um apelido ou nome de guerra.\n"
    "    Classifique cada destinatário pelo campo 'tipo':\n"
    "      - 'PF': pessoa física individual.\n"
    "      - 'PJ': pessoa jurídica (empresa, órgão público, fundação etc.).\n"
    "      - 'Coletivo': agrupamento de PFs e/ou PJs (comissão, associação, torcida etc.).\n"
    "    Campos comuns a todos os tipos (incluir apenas se presentes no texto):\n"
    "      - 'nome': nome completo do destinatário (pessoa, instituição ou coletivo).\n"
    "      - 'endereco': endereço de correspondência extraído literalmente do texto. Não infira endereços a partir de localizações mencionadas indiretamente.\n"
    "      - 'email': endereço de e-mail do destinatário.\n"
    "      - 'is_prefeito': true se o destinatário for o prefeito ou a prefeitura; omita o campo nos demais casos.\n"
    '      - \'genero\': "M" para masculino ou "F" para feminino. Para PF: infira pelo nome ou cargo do destinatário. Para PJ e Coletivo: infira pelo gênero do representante (se explicitamente mencionado no texto) — NUNCA pelo gênero gramatical do nome da instituição; use "M" como padrão para instituições. Sempre inclua este campo.\n'
    "    Campos exclusivos de PF (incluir apenas se presentes no texto):\n"
    "      - 'funcao_profissao': função ou profissão da pessoa física.\n"
    "      - 'nivel_protocolo': nível de protocolo da PF. Use 'VE' para autoridades federais e estaduais que recebem tratamento 'A Sua Excelência' (Presidente da República, Ministros de Estado, Governadores, Deputados Federais/Estaduais, Senadores, Secretários de Estado, Embaixadores etc.); use 'VE_M' para autoridades municipais que recebem tratamento 'À Sua Excelência' (Prefeitos, Vereadores e altos cargos municipais eleitos ou de alto protocolo). Omita o campo para as demais pessoas (tratamento padrão 'Ao Ilustríssimo Senhor' ou 'À Ilustríssima Senhora').\n"
    "    Campos exclusivos de PJ e Coletivo (incluir apenas se presentes no texto):\n"
    "      - 'objeto_atividade': objeto social ou atividade da PJ/Coletivo.\n"
    "      - 'representante': nome do representante da PJ/Coletivo.\n"
    "      - 'funcao_representante': função ou cargo do representante.\n"
    "    \n"
    "    Formato JSON esperado:\n"
    "    {\n"
    '        "propositura": "moção" ou "requerimento_pesar",\n'
    '        "tipo_mocao": "Ex.: Aplauso",\n'
    '        "numero_mocao": "Ex: 432",\n'
    '        "autores": ["Nome do Vereador 1", "Nome do Vereador 2"],\n'
    '        "destinatarios": [\n'
    "            {\n"
    '                "tipo": "PF",\n'
    '                "nome": "LUIZ INÁCIO LULA DA SILVA",\n'
    '                "nivel_protocolo": "VE",\n'
    '                "funcao_profissao": "Presidente da República Federativa do Brasil",\n'
    '                "endereco": "Endereço literal (omitir se ausente)",\n'
    '                "email": "Email (omitir se ausente)",\n'
    '                "genero": "M"\n'
    "            },\n"
    "            {\n"
    '                "tipo": "PF",\n'
    '                "nome": "RAFAEL PIOVEZAN",\n'
    '                "nivel_protocolo": "VE_M",\n'
    '                "funcao_profissao": "Prefeito Municipal",\n'
    '                "is_prefeito": true,\n'
    '                "genero": "M"\n'
    "            },\n"
    "            {\n"
    '                "tipo": "PF",\n'
    '                "nome": "MARCUS PENSUTI",\n'
    '                "funcao_profissao": "Secretário Municipal de Saúde",\n'
    '                "genero": "M"\n'
    "            },\n"
    "            {\n"
    '                "tipo": "PJ",\n'
    '                "nome": "NOME DA INSTITUIÇÃO",\n'
    '                "objeto_atividade": "Atividade/objeto (omitir se ausente)",\n'
    '                "representante": "Nome do representante (omitir se ausente)",\n'
    '                "funcao_representante": "Cargo do representante (omitir se ausente)",\n'
    '                "endereco": "Endereço literal (omitir se ausente)",\n'
    '                "email": "Email (omitir se ausente)",\n'
    '                "genero": "M"\n'
    "            },\n"
    "            {\n"
    '                "tipo": "Coletivo",\n'
    '                "nome": "NOME DO COLETIVO",\n'
    '                "objeto_atividade": "Atividade/objeto (omitir se ausente)",\n'
    '                "representante": "Nome do representante (omitir se ausente)",\n'
    '                "funcao_representante": "Cargo do representante (omitir se ausente)",\n'
    '                "endereco": "Endereço literal (omitir se ausente)",\n'
    '                "email": "Email (omitir se ausente)",\n'
    '                "genero": "M"\n'
    "            }\n"
    "        ]\n"
    "    }\n"
    "    \n"
    "    Texto da propositura:\n"
    "    {texto_mocao}\n"
)

# ── Built-in prompt for requerimentos de pesar ───────────────────────────────
PROMPT_TEMPLATE_PESAR_PADRAO: str = (
    "    Atue como um assistente legislativo. Leia o texto do(s) requerimento(s) de pesar abaixo e extraia os dados estritamente no formato JSON.\n"
    "    Cada requerimento pode conter um ou mais destinatários. Para cada destinatário, classifique o tipo e extraia apenas os campos efetivamente presentes no texto.\n"
    "    REGRA FUNDAMENTAL: Omita do JSON qualquer campo que não esteja presente no texto do requerimento. Não inclua campos vazios, não deixe valores em branco e não mencione ausência de dados.\n"
    "    O campo 'numero_requerimento' deve conter apenas o número sequencial do requerimento, sem sufixos de ano. Ex: '45' em vez de '45/2026'.\n"
    "    O campo 'falecido' deve conter o nome completo da pessoa homenageada/falecida mencionada no requerimento. Se não houver nome explícito, omita o campo.\n"
    "    O campo 'autores' deve ser uma lista de nomes completos dos vereadores autores do requerimento.\n"
    "    O campo 'destinatarios' deve ser uma lista de objetos identificados a partir do trecho de encaminhamento da cópia (ex: 'Solicito... que seja encaminhada cópia...').\n"
    "    REGRA DE DESTINATÁRIOS: Inclua como destinatário apenas quem (a) estiver mencionado na ementa do requerimento, ou (b) o texto indicar expressamente que o requerimento deve ser encaminhado. Pessoas ou instituições meramente citadas no corpo do texto, sem instrução explícita de encaminhamento e sem menção na ementa, nunca devem ser incluídas na lista 'destinatarios'.\n"
    "    REGRA DE APELIDO: Quando o texto mencionar uma pessoa pelo nome completo e também por um apelido ou nome de guerra (ex.: policiais militares e civis, agentes públicos), trate-os como UM ÚNICO destinatário. Inclua ambos no campo 'nome' no formato \"NOME COMPLETO (APELIDO)\". Nunca crie dois destinatários separados para a mesma pessoa por causa de um apelido ou nome de guerra.\n"
    "    Classifique cada destinatário pelo campo 'tipo':\n"
    "      - 'PF': pessoa física individual (incluindo familiares do falecido).\n"
    "      - 'PJ': pessoa jurídica (empresa, órgão público, fundação etc.).\n"
    "      - 'Coletivo': agrupamento de PFs e/ou PJs (comissão, associação etc.).\n"
    "    Campos comuns a todos os tipos (incluir apenas se presentes no texto):\n"
    "      - 'nome': nome completo do destinatário. Se o texto mencionar apenas um endereço de entrega sem nomear o destinatário, use 'Familiares de [nome do falecido]' como nome.\n"
    "      - 'endereco': endereço de correspondência extraído literalmente do texto. Não infira endereços a partir de localizações mencionadas indiretamente.\n"
    "      - 'email': endereço de e-mail do destinatário.\n"
    "      - 'is_prefeito': true se o destinatário for o prefeito ou a prefeitura; omita o campo nos demais casos.\n"
    '      - \'genero\': "M" para masculino ou "F" para feminino. Para PF: infira pelo nome ou cargo do destinatário. Para PJ e Coletivo: infira pelo gênero do representante (se explicitamente mencionado no texto) — NUNCA pelo gênero gramatical do nome da instituição; use "M" como padrão para instituições. Sempre inclua este campo.\n'
    "    Campos exclusivos de PF (incluir apenas se presentes no texto):\n"
    "      - 'funcao_profissao': função ou profissão da pessoa física.\n"
    "      - 'nivel_protocolo': nível de protocolo da PF. Use 'VE' para autoridades federais e estaduais que recebem tratamento 'A Sua Excelência' (Presidente da República, Ministros de Estado, Governadores, Deputados Federais/Estaduais, Senadores, Secretários de Estado, Embaixadores etc.); use 'VE_M' para autoridades municipais que recebem tratamento 'À Sua Excelência' (Prefeitos, Vereadores e altos cargos municipais eleitos ou de alto protocolo). Omita o campo para as demais pessoas (tratamento padrão 'Ao Ilustríssimo Senhor' ou 'À Ilustríssima Senhora').\n"
    "    Campos exclusivos de PJ e Coletivo (incluir apenas se presentes no texto):\n"
    "      - 'objeto_atividade': objeto social ou atividade da PJ/Coletivo.\n"
    "      - 'representante': nome do representante da PJ/Coletivo.\n"
    "      - 'funcao_representante': função ou cargo do representante.\n"
    "    \n"
    "    Formato JSON esperado:\n"
    "    {\n"
    '        "numero_requerimento": "Ex: 45",\n'
    '        "falecido": "Nome completo do falecido (omitir se ausente)",\n'
    '        "autores": ["Nome do Vereador 1"],\n'
    '        "destinatarios": [\n'
    "            {\n"
    '                "tipo": "PF",\n'
    '                "nome": "NOME DA PESSOA OU FAMILIARES DE [FALECIDO]",\n'
    '                "funcao_profissao": "Função ou profissão (omitir se ausente)",\n'
    '                "endereco": "Endereço literal (omitir se ausente)",\n'
    '                "email": "Email (omitir se ausente)",\n'
    '                "genero": "M"\n'
    "            },\n"
    "            {\n"
    '                "tipo": "PJ",\n'
    '                "nome": "NOME DA INSTITUIÇÃO",\n'
    '                "objeto_atividade": "Atividade/objeto (omitir se ausente)",\n'
    '                "representante": "Nome do representante (omitir se ausente)",\n'
    '                "funcao_representante": "Cargo do representante (omitir se ausente)",\n'
    '                "endereco": "Endereço literal (omitir se ausente)",\n'
    '                "email": "Email (omitir se ausente)",\n'
    '                "genero": "M"\n'
    "            }\n"
    "        ]\n"
    "    }\n"
    "    \n"
    "    Texto do requerimento:\n"
    "    {texto_mocao}\n"
)

# Pre-compiled patterns used in retry logic.
_RE_RETRY_DELAY: re.Pattern[str] = re.compile(r"retry_delay\s*\{\s*seconds:\s*(\d+)")

# Thread-safe counter so each AI call gets a unique sequential number in the log.
_chamada_lock: threading.Lock = threading.Lock()
_chamada_n: list[int] = [0]


def _gerar_alertas(
    tipo_propositura: str,
    resultado: dict[str, Any] | None,
    tentativas: list[dict[str, Any]],
) -> list[str]:
    """Return soft-warning strings about the AI extraction result."""
    alertas: list[str] = []

    n_invalidas = sum(1 for t in tentativas if t.get("status") != "sucesso")
    if n_invalidas:
        alertas.append(
            f"{n_invalidas} tentativa(s) inválida(s)/rate-limit antes do resultado final"
        )

    if resultado is None:
        return alertas

    if tipo_propositura == "requerimento_pesar" and not resultado.get("falecido"):
        alertas.append("Campo 'falecido' vazio no requerimento de pesar")

    _PALAVRAS_FAMILIA = ("família", "familiares", "familia", "herdeiro", "viúva", "viuvo")

    for i, dest in enumerate(resultado.get("destinatarios") or [], start=1):
        tipo_dest = dest.get("tipo") or ""
        is_inst = tipo_dest in ("PJ", "Coletivo") or dest.get("is_instituicao", False)
        tem_cargo = bool(
            dest.get("funcao_profissao")
            or dest.get("objeto_atividade")
            or dest.get("cargo_ou_tratamento")
        )
        if not tem_cargo:
            alertas.append(f"Destinatário {i} sem função/profissão ou objeto/atividade")
        if not dest.get("endereco") and not dest.get("email"):
            alertas.append(f"Destinatário {i} sem endereço nem e-mail")
        nome_lower = (dest.get("nome") or "").lower()
        if is_inst and any(p in nome_lower for p in _PALAVRAS_FAMILIA):
            alertas.append(
                f"Destinatário {i}: possível classificação incorreta — "
                f"'{dest.get('nome')}' parece ser família, não instituição (tipo={tipo_dest!r})"
            )

    return alertas


def _prompt_file_path() -> Path:
    """Return the path to the user-editable prompt template file.

    Returns:
        Path next to the executable (frozen) or next to the package root (dev).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "prompt_template.txt"
    # Resolve relative to the project root (four levels up from this file)
    return Path(__file__).parent.parent.parent.parent / "prompt_template.txt"


def _prompt_pesar_file_path() -> Path:
    """Return the path to the user-editable *requerimento de pesar* prompt file.

    Returns:
        Path next to the executable (frozen) or next to the package root (dev).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "prompt_template_pesar.txt"
    return Path(__file__).parent.parent.parent.parent / "prompt_template_pesar.txt"


def carregar_prompt_template() -> str:
    """Load the prompt template from disk, falling back to the built-in default.

    Returns:
        Active prompt template string with a ``{texto_mocao}`` placeholder.
    """
    p = _prompt_file_path()
    if p.exists():
        try:
            return p.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Falha ao ler prompt template '%s': %s. Usando template padrão.", p, exc)
    return PROMPT_TEMPLATE_PADRAO


def carregar_prompt_template_pesar() -> str:
    """Load the *requerimento de pesar* prompt template, falling back to built-in.

    Returns:
        Active prompt template string with a ``{texto_mocao}`` placeholder.
    """
    p = _prompt_pesar_file_path()
    if p.exists():
        try:
            return p.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Falha ao ler prompt template pesar '%s': %s. Usando template padrão.", p, exc)
    return PROMPT_TEMPLATE_PESAR_PADRAO


# Active template (can be replaced at runtime via the GUI prompt editor).
PROMPT_TEMPLATE: str = carregar_prompt_template()

# Active requerimento de pesar template (can be replaced at runtime).
PROMPT_TEMPLATE_PESAR: str = carregar_prompt_template_pesar()

# Active AI model name (can be replaced at runtime via the GUI advanced dialog).
def _load_modelo_ia() -> str:
    try:
        from z7_officeletters.core.api_key import carregar_modelo_ia  # noqa: PLC0415
        return carregar_modelo_ia()
    except Exception as exc:  # noqa: BLE001
        from z7_officeletters.core.api_key import DEFAULT_MODELO_IA  # noqa: PLC0415
        logger.warning("Falha ao carregar modelo IA: %s. Usando modelo padrão '%s'.", exc, DEFAULT_MODELO_IA)
        return DEFAULT_MODELO_IA


MODELO_IA: str = _load_modelo_ia()


def limpar_json_da_resposta(texto: str) -> str:
    """Strip Markdown code fences from an AI text response.

    Handles both ````json ... ```` and generic ```` ``` ... ``` ```` fences.

    Args:
        texto: Raw text from the Gemini API response.

    Returns:
        JSON string with surrounding whitespace and fences removed.
    """
    texto = texto.strip()
    if texto.startswith("```json"):
        return texto.split("```json")[1].split("```")[0].strip()
    if texto.startswith("```"):
        return texto.split("```")[1].split("```")[0].strip()
    return texto


def validar_dados_requerimento_pesar(dados: dict[str, Any]) -> None:
    """Validate required fields in the AI-returned *requerimento de pesar* dict.

    Args:
        dados: Parsed JSON dict from the Gemini response.

    Raises:
        ValueError: If any required field is missing, empty, or has an
            unexpected type/value.
    """
    for campo in ("numero_requerimento", "autores", "destinatarios"):
        if campo not in dados or not dados[campo]:
            raise ValueError(
                f"Campo obrigatório ausente ou vazio na resposta da IA: '{campo}'"
            )
    if not isinstance(dados["autores"], list):
        raise ValueError("'autores' deve ser uma lista.")
    if not isinstance(dados["destinatarios"], list):
        raise ValueError("'destinatarios' deve ser uma lista.")
    for i, dest in enumerate(dados["destinatarios"]):
        if not dest.get("nome"):
            raise ValueError(f"Destinatário {i + 1} sem campo 'nome'.")


def validar_dados_mocao(dados: dict[str, Any]) -> None:
    """Validate required fields in the AI-returned motion dictionary.

    Args:
        dados: Parsed JSON dict from the Gemini response.

    Raises:
        ValueError: If any required field is missing, empty, or has an
            unexpected type/value.
    """
    for campo in ("tipo_mocao", "numero_mocao", "autores", "destinatarios"):
        if campo not in dados or not dados[campo]:
            raise ValueError(
                f"Campo obrigatório ausente ou vazio na resposta da IA: '{campo}'"
            )
    if dados["tipo_mocao"] not in ("Aplauso", "Apelo", "Apoio", "Protesto"):
        raise ValueError(f"tipo_mocao inválido recebido da IA: '{dados['tipo_mocao']}'")
    if not isinstance(dados["autores"], list):
        raise ValueError("'autores' deve ser uma lista.")
    if not isinstance(dados["destinatarios"], list):
        raise ValueError("'destinatarios' deve ser uma lista.")
    for i, dest in enumerate(dados["destinatarios"]):
        if not dest.get("nome"):
            raise ValueError(f"Destinatário {i + 1} sem campo 'nome'.")


def extrair_dados_com_ia(
    texto_mocao: str,
    cliente_genai: Any,
    tipo_propositura: str = "mocao",
    cancel_event: "threading.Event | None" = None,
) -> dict[str, Any]:
    """Send a propositura text to Gemini and return validated structured data.

    Retries up to ``MAX_TENTATIVAS_IA`` times on rate-limit (HTTP 429) errors,
    honouring the ``retry_delay`` value in the error response when available.

    Args:
        texto_mocao: Raw text of one propositura extracted from the input file.
        cliente_genai: Initialised ``google.genai.Client`` instance.
        tipo_propositura: Either ``"mocao"`` (default) or
            ``"requerimento_pesar"``.  Selects the prompt template and
            validation function accordingly.

    Returns:
        Validated dict.  For moções: keys ``tipo_mocao``, ``numero_mocao``,
        ``autores``, ``destinatarios``.  For requerimentos de pesar: keys
        ``numero_requerimento``, ``falecido``, ``autores``, ``destinatarios``.

    Raises:
        Exception: After ``MAX_TENTATIVAS_IA`` consecutive failures, or
            immediately on non-rate-limit API errors.
    """
    _is_pesar = tipo_propositura == "requerimento_pesar"
    _template = PROMPT_TEMPLATE_PESAR if _is_pesar else PROMPT_TEMPLATE
    _validar = validar_dados_requerimento_pesar if _is_pesar else validar_dados_mocao
    prompt = _template.replace("{texto_mocao}", texto_mocao)
    logger.debug("Enviando %s à API Gemini.", tipo_propositura)

    with _chamada_lock:
        _chamada_n[0] += 1
        _n = _chamada_n[0]

    _tentativas_log: list[dict[str, Any]] = []
    _resultado_final: dict[str, Any] | None = None
    _erro_final: str | None = None

    try:
        for tentativa in range(MAX_TENTATIVAS_IA):
            _tentativa_info: dict[str, Any] = {"tentativa": tentativa + 1}
            try:
                response = cliente_genai.models.generate_content(
                    model=MODELO_IA,
                    contents=prompt,
                )
                logger.debug("Resposta recebida (tentativa %d).", tentativa + 1)
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)
                match = _RE_RETRY_DELAY.search(msg)
                espera = int(match.group(1)) + 2 if match else RETRY_DELAY_PADRAO_S
                if "429" in msg:
                    _tentativa_info.update(
                        {"status": "rate_limit", "erro": msg, "espera_s": espera}
                    )
                    _tentativas_log.append(_tentativa_info)
                    logger.warning(
                        "Rate limit atingido. Aguardando %ds (tentativa %d/%d).",
                        espera,
                        tentativa + 1,
                        MAX_TENTATIVAS_IA,
                    )
                    for _ in range(espera):
                        if cancel_event is not None and cancel_event.is_set():
                            raise RuntimeError("Processamento cancelado.")
                        time.sleep(1)
                    continue
                _tentativa_info.update({"status": "erro_api", "erro": msg})
                _tentativas_log.append(_tentativa_info)
                logger.error("Erro na API Gemini: %s", exc, exc_info=True)
                _erro_final = msg
                raise

            raw_text: str = response.text  # type: ignore[union-attr]
            _tentativa_info["resposta_bruta"] = raw_text
            _preview = raw_text[:500] + ("…" if len(raw_text) > 500 else "")
            logger.debug("Resposta bruta da IA (tentativa %d): %r", tentativa + 1, _preview)

            try:
                json_str = limpar_json_da_resposta(raw_text)
                data: Any = json.loads(json_str)
                resultado: dict[str, Any] = cast(
                    dict[str, Any], data[0] if isinstance(data, list) else data
                )
                _validar(resultado)
            except (ValueError, json.JSONDecodeError) as exc:
                _tentativa_info.update({"status": "resposta_invalida", "erro": str(exc)})
                _tentativas_log.append(_tentativa_info)
                logger.warning(
                    "Resposta inválida da IA (tentativa %d/%d): %s. Bruta: %r",
                    tentativa + 1,
                    MAX_TENTATIVAS_IA,
                    exc,
                    _preview,
                )
                if tentativa < MAX_TENTATIVAS_IA - 1:
                    continue
                _erro_final = str(exc)
                raise

            _tentativa_info["status"] = "sucesso"
            _tentativas_log.append(_tentativa_info)

            if _is_pesar:
                logger.debug(
                    "Dados extraídos — requerimento de pesar nº %s, falecido: %s.",
                    resultado.get("numero_requerimento"),
                    resultado.get("falecido"),
                )
            else:
                logger.debug(
                    "Dados extraídos — moção nº %s, tipo: %s.",
                    resultado.get("numero_mocao"),
                    resultado.get("tipo_mocao"),
                )

            try:
                um = response.usage_metadata
                resultado["_usage"] = {
                    "prompt_tokens":     int(um.prompt_token_count),
                    "candidates_tokens": int(um.candidates_token_count),
                    "total_tokens":      int(um.total_token_count),
                }
            except Exception:  # noqa: BLE001
                resultado["_usage"] = {
                    "prompt_tokens": 0, "candidates_tokens": 0, "total_tokens": 0
                }

            _alertas = _gerar_alertas(tipo_propositura, resultado, _tentativas_log)
            resultado["_alertas"] = _alertas
            _resultado_final = resultado
            return resultado

        _erro_final = "Número máximo de tentativas excedido."
        raise RuntimeError(_erro_final)

    finally:
        _uso = _resultado_final.get("_usage") if _resultado_final is not None else None
        _alertas_log = (
            _resultado_final.get("_alertas", [])
            if _resultado_final is not None
            else _gerar_alertas(tipo_propositura, None, _tentativas_log)
        )
        _dados_log = (
            {k: v for k, v in _resultado_final.items() if k not in ("_usage", "_alertas")}
            if _resultado_final is not None
            else None
        )
        registrar_chamada_ia({
            "timestamp":      datetime.now().isoformat(timespec="milliseconds"),
            "sessao_id":      SESSAO_ID,
            "chamada":        _n,
            "tipo_propositura": tipo_propositura,
            "prompt":         prompt,
            "tentativas":     _tentativas_log,
            "dados_extraidos": _dados_log,
            "usage":          _uso,
            "alertas":        _alertas_log,
            "erro":           _erro_final,
        })
