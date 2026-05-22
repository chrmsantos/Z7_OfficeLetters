"""Recipient address and honorific processing.

Applies Brazilian legislative formatting rules to the structured recipient
data returned by the AI, producing the address block, vocative, and pronoun
forms used in the letter template.

Public exports:
    DestinatarioEntrada: TypedDict for the AI-returned recipient object.
    DestinatarioProcessado: TypedDict for the processed output used in the template.
    processar_destinatario: Apply all business rules to a single recipient dict.
"""

from __future__ import annotations

import re
from typing import Any, TypedDict

from z7_officeletters.core.authors import norm
import z7_officeletters.core.config as _config

__all__ = [
    "DestinatarioEntrada",
    "DestinatarioProcessado",
    "processar_destinatario",
    "determinar_genero_instituicao",
    "aplicar_tratamento_db",
]


class DestinatarioEntrada(TypedDict, total=False):
    """Shape of a recipient object as returned by the Gemini AI."""

    tipo: str  # "PF", "PJ", or "Coletivo"
    nome: str
    # PF fields
    nivel_protocolo: str   # "VE" (federal/state), "VE_M" (municipal), or absent (default VS)
    funcao_profissao: str
    # PJ / Coletivo fields
    objeto_atividade: str
    representante: str
    funcao_representante: str
    # Common fields
    endereco: str
    email: str
    is_prefeito: bool
    # Legacy fields — kept for backward compatibility with custom prompts
    is_instituicao: bool
    cargo_ou_tratamento: str
    genero: str  # "M" or "F"


class DestinatarioProcessado(TypedDict):
    """Processed recipient data ready for insertion into the letter template."""

    tratamento_rodape: str
    destinatario_nome: str
    destinatario_endereco: str
    vocativo: str
    pronome_corpo: str
    envio: str


# Honorifics that should be stripped when they are the sole content of the
# ``cargo_ou_tratamento`` field or appear as a prefix before a real title.
_HONORIFICOS: frozenset[str] = frozenset({
    "sr",
    "sr.",
    "sra",
    "sra.",
    "senhor",
    "senhora",
    "ilustríssimo senhor",
    "ilustríssima senhora",
    "ilustríssimo sr.",
    "ilustríssima sra.",
})


def determinar_genero_instituicao(nome: str) -> str:
    """Detects if an institution name is feminine or masculine in Portuguese.

    Rules applied:
    - Normalizes the name (accents stripped, lowercase).
    - Removes leading ordinal/numerical/adjective prefixes.
    - If the first significant word starts with 'a' and is not a known masculine
      noun starting with 'a', it is feminine ('F').
      Otherwise, if the first significant word is in a predefined set of
      common feminine nouns or acronyms, it is feminine ('F').
    - Else, defaults to masculine ('M').

    Args:
        nome: Name of the institution.

    Returns:
        "F" for feminine or "M" for masculine.
    """
    nome_norm = norm(nome).strip()
    if not nome_norm:
        return "M"

    # Strip leading ordinal/number/adjective prefixes, e.g. "1a", "1º", "1ª", "primeira", etc.
    # also strip leading dashes, dots, spaces, etc.
    nome_limpo = re.sub(
        r'^(?:\d+(?:[a-zªº°\.]|\s)*|primeir[ao]|segund[ao]|terceir[ao]|quart[ao]|quint[ao]|sext[ao]|setim[ao]|oitav[ao]|non[ao]|decim[ao])\s+',
        '',
        nome_norm,
        flags=re.IGNORECASE
    )

    # Strip any leading punctuation or symbols
    nome_limpo = nome_limpo.lstrip(".-_#/* ")

    # Split into words
    palavras = nome_limpo.split()
    if not palavras:
        return "M"

    primeira_palavra = palavras[0]

    # Direct feminine articles / pronouns at the beginning of the cleaned name
    if primeira_palavra in ("a", "as", "uma", "umas", "sua", "suas"):
        return "F"

    # Common masculine nouns starting with 'a' to prevent false positives under the 'startswith a' rule
    masculine_a_nouns = {
        "abrigo", "asilo", "albergue", "aeroporto", "ambulatorio", "almoxarifado",
        "arquivo", "acampamento", "agrupamento", "ambulante", "atelie", "alojamento",
        "anexo", "arranha", "arco"
    }

    # If it starts with 'a' and is NOT a known masculine noun starting with 'a', it is feminine
    if primeira_palavra.startswith("a") and primeira_palavra not in masculine_a_nouns:
        return "F"

    # Known feminine nouns or acronyms starting institution names
    feminine_words = {
        "companhia", "cia", "sociedade", "fundacao", "empresa", "prefeitura",
        "camara", "igreja", "escola", "creche", "universidade", "faculdade",
        "secretaria", "defensoria", "procuradoria", "promotoria", "comarca",
        "delegacia", "superintendencia", "gerencia", "diretoria", "coordenadoria",
        "junta", "liga", "federacao", "confederacao", "uniao", "entidade",
        "corporacao", "guarda", "policia", "forca", "organizacao", "administracao",
        "concessionaria", "distribuidora", "clinica", "maternidade", "casa",
        "cooperativa", "redacao", "radio", "televisao", "tv", "inspetoria",
        "ouvidoria", "biblioteca", "sede", "unidade", "subsecao", "secao",
        "seccional", "vara", "varas", "comissao", "subdelegacia", "chancelaria",
        "embaixada", "reitoria", "provedoria", "irmandade", "oficina", "quadra",
        "banda", "orquestra", "galeria", "sala", "cozinha", "fazenda", "chacara",
        "granja", "santa", "santas", "assembleia", "assembleias", "alianca",
        "autarquia", "assessoria", "avenida", "artes", "capela", "paroquia",
        "diocese", "arquidiocese", "comunidade", "comunidades", "instituicao",
        "instituicoes", "entidades", "empresas", "fundacoes", "sociedades",
        "companhias", "camaras", "prefeituras", "escolas", "creches",
        "universidades", "faculdades", "secretarias", "delegacias",
        "superintendencias", "diretorias", "juntas", "ligas", "federacoes",
        "confederacoes", "unioes", "corporacoes", "guardas", "policias",
        "forcas", "organizacoes", "clinicas", "casas", "cooperativas",
        "radios", "bibliotecas", "sedes", "unidades", "secoes", "varas",
        "comissoes", "oab", "apae", "ong", "sabesp", "ect", "ebct", "cpfl"
    }

    if primeira_palavra in feminine_words:
        return "F"

    # Multi-word or compound checks
    if any(nome_limpo.startswith(p) for p in (
        "santa casa", "santas casas", "cruz vermelha", "guarda municipal",
        "policia federal", "policia militar", "policia civil"
    )):
        return "F"

    return "M"


def processar_destinatario(dest: dict[str, Any]) -> DestinatarioProcessado:
    """Apply business rules to a single AI-extracted recipient dictionary.

    Rules applied:
    - If the recipient is the mayor (``is_prefeito`` flag or name contains
      "prefeito"), return fixed mayor address and pronouns from config.
    - For institutions (``is_instituicao``), use plural honorifics and
      determine the preposition (``"Ao"`` / ``"À"``) from the institution name.
    - For natural persons, apply gendered honorifics (``genero`` field).
    - Strip standalone generic honorifics from ``cargo_ou_tratamento``; also
      strip honorific prefixes of the form ``"Sr. / Real Title"`` leaving only
      the real title.
    - Derive the delivery method (``"E-mail"``, ``"Carta"``, ``"Em Mãos"``,
      or ``"Protocolo"``) from available contact fields.

    Args:
        dest: Recipient dict with keys matching ``DestinatarioEntrada``.

    Returns:
        ``DestinatarioProcessado`` with all template variables populated.
    """
    # ── Mayor fast-path ───────────────────────────────────────────────────────
    nome: str = dest.get("nome") or ""
    if dest.get("is_prefeito") or "prefeito" in nome.lower() or "prefeita" in nome.lower():
        pref_nome = _config.PREFEITO["nome"]
        pref_endereco = _config.PREFEITO["endereco"]
        
        # Verify if female councillor list or configured fields contain "prefeita"
        female_list_norm = [norm(f) for f in _config.CONFIG.get("vereadores_feminino", [])]
        pref_nome_norm = norm(pref_nome)
        
        is_female = (
            pref_nome_norm in female_list_norm
            or "prefeita" in pref_nome.lower()
            or "prefeita" in pref_endereco.lower()
            or dest.get("genero") == "F"
            or "prefeita" in nome.lower()
        )
        
        tratamento_rodape = "À Sua Excelência a Senhora" if is_female else "À Sua Excelência o Senhor"
        vocativo = "Excelentíssima Senhora Prefeita" if is_female else "Excelentíssimo Senhor Prefeito"
        
        return DestinatarioProcessado(
            tratamento_rodape=tratamento_rodape,
            destinatario_nome=pref_nome,
            destinatario_endereco=pref_endereco,
            vocativo=vocativo,
            pronome_corpo="Vossa Excelência",
            envio="Protocolo",
        )

    tipo: str = dest.get("tipo") or ""
    is_inst: bool = tipo in ("PJ", "Coletivo") or bool(dest.get("is_instituicao") or False)
    genero: str = dest.get("genero") or "M"  # "M" or "F"; default masculine

    # ── Tratamento no rodapé ──────────────────────────────────────────────────
    if is_inst:
        genero_inst = determinar_genero_instituicao(nome)
        tratamento_rodape = "À" if genero_inst == "F" else "Ao"
        vocativo = "Ilustríssimas Senhoras" if genero == "F" else "Ilustríssimos Senhores"
        pronome_corpo = "Vossas Senhorias"
    else:
        # PF — four protocol levels
        nivel: str = dest.get("nivel_protocolo") or "VS"
        genero_art = "a Senhora" if genero == "F" else "o Senhor"
        if nivel == "VE":
            # Federal / state authorities: no crase
            tratamento_rodape = f"A Sua Excelência {genero_art}"
            vocativo = "Excelentíssima Senhora" if genero == "F" else "Excelentíssimo Senhor"
            pronome_corpo = "Vossa Excelência"
        elif nivel == "VE_M":
            # Municipal authorities: crase
            tratamento_rodape = f"À Sua Excelência {genero_art}"
            vocativo = "Excelentíssima Senhora" if genero == "F" else "Excelentíssimo Senhor"
            pronome_corpo = "Vossa Excelência"
        else:
            # Default — Vossa Senhoria
            tratamento_rodape = "À Ilustríssima Senhora" if genero == "F" else "Ao Ilustríssimo Senhor"
            vocativo = "Ilustríssima Senhora" if genero == "F" else "Ilustríssimo Senhor"
            pronome_corpo = "Vossa Senhoria"

    # ── Address block ─────────────────────────────────────────────────────────
    endereco: str = dest.get("endereco") or ""
    email: str = dest.get("email") or ""
    partes_endereco: list[str] = []

    if is_inst:
        # PJ / Coletivo: object/activity, then representative info
        objeto = dest.get("objeto_atividade") or dest.get("cargo_ou_tratamento") or ""
        representante = dest.get("representante") or ""
        funcao_rep = dest.get("funcao_representante") or ""
        if objeto:
            partes_endereco.append(objeto)
        if representante:
            rep_linha = f"{funcao_rep}: {representante}" if funcao_rep else representante
            partes_endereco.append(rep_linha)
    else:
        # PF: function / profession
        cargo: str = dest.get("funcao_profissao") or dest.get("cargo_ou_tratamento") or ""
        # Pattern: "Sr. / Real Title" → keep only "Real Title"
        if "/" in cargo:
            partes = [p.strip() for p in cargo.split("/", 1)]
            if partes[0].lower() in _HONORIFICOS:
                cargo = partes[1]
        # Discard the field entirely when it is just a generic honorific
        if cargo.strip().lower() in _HONORIFICOS:
            cargo = ""
        if cargo:
            partes_endereco.append(cargo)

    if endereco:
        partes_endereco.append(endereco)
    if email:
        partes_endereco.append(email)

    # ── Delivery method ───────────────────────────────────────────────────────
    if email:
        envio = "E-mail"
    elif endereco:
        envio = "Carta"
    else:
        envio = "Em Mãos"

    return DestinatarioProcessado(
        tratamento_rodape=tratamento_rodape,
        destinatario_nome=nome.upper(),
        destinatario_endereco="\n".join(partes_endereco),
        vocativo=vocativo,
        pronome_corpo=pronome_corpo,
        envio=envio,
    )


def aplicar_tratamento_db(info: dict[str, Any], tratamento: str) -> None:
    """Override honorifics in *info* using the address-database tratamento line.

    Called after :func:`processar_destinatario` when the address database
    supplies a more authoritative tratamento string.  Mutates *info* in place.

    The function syncs ``vocativo`` and ``pronome_corpo`` with the new
    ``tratamento_rodape`` value so that a wrong gender inferred by the AI does
    not bleed through into the final letter.

    Args:
        info: ``DestinatarioProcessado`` dict to update in place.
        tratamento: Raw tratamento line from the address database (e.g.
            ``"A Sua Excelência o Senhor"``).
    """
    t = tratamento.strip()
    t_lower = t.lower()
    if "excelê" in t_lower or "excelencia" in t_lower.encode("ascii", "ignore").decode():
        info["tratamento_rodape"] = t
        info["pronome_corpo"] = "Vossa Excelência"
        info["vocativo"] = (
            "Excelentíssima Senhora" if "senhora" in t_lower else "Excelentíssimo Senhor"
        )
    elif "cuidados" in t_lower:
        info["tratamento_rodape"] = t
        info["vocativo"] = "Ilustríssimos Senhores(as)"
        info["pronome_corpo"] = "Vossas Senhorias"
    else:
        info["tratamento_rodape"] = t
        # When the DB tratamento encodes a gendered honorific (e.g. "À Ilustríssima
        # Senhora" or "Ao Ilustríssimo Senhor"), sync vocativo/pronome_corpo so that
        # a wrong gender from the AI does not bleed through into the final letter.
        t_ascii = t_lower.encode("ascii", "ignore").decode()
        if "ilustrissima" in t_ascii or (
            "senhora" in t_lower and "senhori" not in t_lower
        ):
            info["vocativo"] = "Ilustríssima Senhora"
            info["pronome_corpo"] = "Vossa Senhoria"
        elif "ilustrissimo" in t_ascii or (
            "senhor" in t_lower
            and "senhora" not in t_lower
            and "senhori" not in t_lower
        ):
            info["vocativo"] = "Ilustríssimo Senhor"
            info["pronome_corpo"] = "Vossa Senhoria"
