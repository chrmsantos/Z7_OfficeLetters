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
import time
from pathlib import Path
from typing import Any, cast

from z7_officeletters.constants import MAX_TENTATIVAS_IA, RETRY_DELAY_PADRAO_S
from z7_officeletters.core.logging_setup import logger

__all__ = [
    "PROMPT_TEMPLATE_PADRAO",
    "PROMPT_TEMPLATE",
    "MODELO_IA",
    "carregar_prompt_template",
    "limpar_json_da_resposta",
    "validar_dados_mocao",
    "extrair_dados_com_ia",
]

# ── Built-in prompt (shipped with the application) ───────────────────────────
PROMPT_TEMPLATE_PADRAO: str = (
    "    Atue como um assistente legislativo. Leia o texto da(s) moção(ões) abaixo e extraia os dados estritamente no formato JSON.\n"
    "    Cada moção pode conter um ou mais destinatários. Para cada destinatário, extraia nome, cargo ou tratamento, endereço e email (se houver), e classifique se é o prefeito/prefeitura ou uma instituição.\n"
    "    Se houver múltiplos destinatários exigidos em uma moção, retorne todos na lista 'destinatarios'.\n"
    "    Se o texto da moção não contiver um campo específico (ex: email ou endereço do destinatário), deixe o valor correspondente vazio no JSON.\n"
    "    Se o texto mencionar que o destinatário é o prefeito ou a prefeitura, marque 'is_prefeito' como true. Se mencionar uma instituição, marque 'is_instituicao' como true.\n"
    "    O campo 'numero_mocao' deve conter apenas o número sequencial da moção, sem sufixos de ano ou outros caracteres. Ex: '432' em vez de '432/2026'.\n"
    "    O campo 'tipo_mocao' deve ser classificado como 'Aplauso', 'Apelo', 'Apoio' ou 'Protesto' com base no conteúdo da moção.\n"
    "    O campo 'autores' deve ser uma lista de nomes completos dos vereadores autores da moção, conforme mencionados no texto. Se o texto mencionar apenas o cargo (ex: 'os vereadores'), use 'Vereador(a) Indefinido(a)'.\n"
    "    O campo 'destinatarios' deve ser uma lista de objetos, cada um contendo:\n"
    "      - 'nome': nome completo do destinatário (pessoa ou instituição),\n"
    "      - 'cargo_ou_tratamento': cargo ou tratamento do destinatário,\n"
    "      - 'endereco': endereço completo do destinatário,\n"
    "      - 'email': email do destinatário,\n"
    "      - 'is_prefeito': true se o destinatário for o prefeito, caso contrário false,\n"
    "      - 'is_instituicao': true se o destinatário for uma instituição, caso contrário false,\n"
    '      - \'genero\': "M" para masculino ou "F" para feminino — infira pelo nome, cargo ou tratamento do destinatário; use "M" quando indeterminado\n'
    "    \n"
    "    Formato JSON esperado:\n"
    "    {\n"
    '        "tipo_mocao": "Aplauso",\n'
    '        "numero_mocao": "Ex: 432",\n'
    '        "autores": ["Nome do Vereador 1", "Nome do Vereador 2"],\n'
    '        "destinatarios": [\n'
    "            {\n"
    '                "nome": "NOME DA PESSOA OU INSTITUIÇÃO",\n'
    '                "cargo_ou_tratamento": "Ex: Presidente da CDHU / Aos cuidados de...",\n'
    '                "endereco": "Endereço completo se houver no texto, senão vazio",\n'
    '                "email": "Email se houver, senão vazio",\n'
    '                "is_prefeito": true ou false,\n'
    '                "is_instituicao": true ou false,\n'
    '                "genero": "M" ou "F"\n'
    "            }\n"
    "        ]\n"
    "    }\n"
    "    \n"
    "    Texto da moção:\n"
    "    {texto_mocao}\n"
)

# Pre-compiled patterns used in retry logic.
_RE_RETRY_DELAY: re.Pattern[str] = re.compile(r"retry_delay\s*\{\s*seconds:\s*(\d+)")


def _prompt_file_path() -> Path:
    """Return the path to the user-editable prompt template file.

    Returns:
        Path next to the executable (frozen) or next to the package root (dev).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "prompt_template.txt"
    # Resolve relative to the project root (four levels up from this file)
    return Path(__file__).parent.parent.parent.parent / "prompt_template.txt"


def carregar_prompt_template() -> str:
    """Load the prompt template from disk, falling back to the built-in default.

    Returns:
        Active prompt template string with a ``{texto_mocao}`` placeholder.
    """
    p = _prompt_file_path()
    if p.exists():
        try:
            return p.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    return PROMPT_TEMPLATE_PADRAO


# Active template (can be replaced at runtime via the GUI prompt editor).
PROMPT_TEMPLATE: str = carregar_prompt_template()

# Active AI model name (can be replaced at runtime via the GUI advanced dialog).
def _load_modelo_ia() -> str:
    try:
        from z7_officeletters.core.api_key import carregar_modelo_ia  # noqa: PLC0415
        return carregar_modelo_ia()
    except Exception:  # noqa: BLE001
        from z7_officeletters.core.api_key import DEFAULT_MODELO_IA  # noqa: PLC0415
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


def extrair_dados_com_ia(texto_mocao: str, cliente_genai: Any) -> dict[str, Any]:
    """Send a motion text to Gemini and return validated structured data.

    Retries up to ``MAX_TENTATIVAS_IA`` times on rate-limit (HTTP 429) errors,
    honouring the ``retry_delay`` value in the error response when available.

    Args:
        texto_mocao: Raw text of one motion extracted from the input file.
        cliente_genai: Initialised ``google.genai.Client`` instance.

    Returns:
        Validated dict with keys ``tipo_mocao``, ``numero_mocao``, ``autores``,
        and ``destinatarios``.

    Raises:
        Exception: After ``MAX_TENTATIVAS_IA`` consecutive failures, or
            immediately on non-rate-limit API errors.
    """
    prompt = PROMPT_TEMPLATE.replace("{texto_mocao}", texto_mocao)
    logger.debug("Enviando moção à API Gemini.")

    for tentativa in range(MAX_TENTATIVAS_IA):
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
                logger.warning(
                    "Rate limit atingido. Aguardando %ds (tentativa %d/%d).",
                    espera,
                    tentativa + 1,
                    MAX_TENTATIVAS_IA,
                )
                time.sleep(espera)
                continue
            logger.error("Erro na API Gemini: %s", exc, exc_info=True)
            raise

        raw_text: str = response.text  # type: ignore[union-attr]
        _preview = raw_text[:500] + ("…" if len(raw_text) > 500 else "")
        logger.debug("Resposta bruta da IA (tentativa %d): %r", tentativa + 1, _preview)

        try:
            json_str = limpar_json_da_resposta(raw_text)
            data: Any = json.loads(json_str)
            resultado: dict[str, Any] = cast(
                dict[str, Any], data[0] if isinstance(data, list) else data
            )
            validar_dados_mocao(resultado)
        except (ValueError, json.JSONDecodeError) as exc:
            logger.warning(
                "Resposta inválida da IA (tentativa %d/%d): %s. Bruta: %r",
                tentativa + 1,
                MAX_TENTATIVAS_IA,
                exc,
                _preview,
            )
            if tentativa < MAX_TENTATIVAS_IA - 1:
                continue
            raise

        logger.debug(
            "Dados extraídos — moção nº %s, tipo: %s.",
            resultado.get("numero_mocao"),
            resultado.get("tipo_mocao"),
        )
        return resultado

    raise RuntimeError("Número máximo de tentativas excedido.")
