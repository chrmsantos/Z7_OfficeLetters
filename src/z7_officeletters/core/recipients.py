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

from typing import Any, TypedDict

import z7_officeletters.core.config as _config

__all__ = [
    "DestinatarioEntrada",
    "DestinatarioProcessado",
    "processar_destinatario",
]


class DestinatarioEntrada(TypedDict, total=False):
    """Shape of a recipient object as returned by the Gemini AI."""

    nome: str
    cargo_ou_tratamento: str
    endereco: str
    email: str
    is_prefeito: bool
    is_instituicao: bool
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
    if dest.get("is_prefeito") or "prefeito" in nome.lower():
        return DestinatarioProcessado(
            tratamento_rodape="A Sua Excelência, o Senhor",
            destinatario_nome=_config.PREFEITO["nome"],
            destinatario_endereco=_config.PREFEITO["endereco"],
            vocativo="Excelentíssimo Senhor Prefeito",
            pronome_corpo="Vossa Excelência",
            envio="Protocolo",
        )

    is_inst: bool = bool(dest.get("is_instituicao") or False)
    genero: str = dest.get("genero") or "M"  # "M" or "F"; default masculine

    # ── Tratamento no rodapé ──────────────────────────────────────────────────
    if is_inst:
        nome_lower = nome.lower()
        tratamento_rodape = "À" if nome_lower.startswith("a") else "Ao"
    else:
        tratamento_rodape = (
            "À Ilustríssima Senhora" if genero == "F" else "Ao Ilustríssimo Senhor"
        )

    # ── Cargo / tratamento — strip generic honorifics ─────────────────────────
    cargo: str = dest.get("cargo_ou_tratamento") or ""
    if not is_inst:
        # Pattern: "Sr. / Real Title" → keep only "Real Title"
        if "/" in cargo:
            partes = [p.strip() for p in cargo.split("/", 1)]
            if partes[0].lower() in _HONORIFICOS:
                cargo = partes[1]
        # Discard the field entirely when it is just a generic honorific
        if cargo.strip().lower() in _HONORIFICOS:
            cargo = ""

    # ── Address block ─────────────────────────────────────────────────────────
    endereco: str = dest.get("endereco") or ""
    email: str = dest.get("email") or ""
    endereco_final = cargo
    if endereco:
        endereco_final += f"\n{endereco}"
    if email:
        endereco_final += f"\n{email}"

    # ── Delivery method ───────────────────────────────────────────────────────
    if email:
        envio = "E-mail"
    elif endereco:
        envio = "Carta"
    else:
        envio = "Em Mãos"

    # ── Vocative and body pronoun ─────────────────────────────────────────────
    if is_inst:
        vocativo = "Ilustríssimas Senhoras" if genero == "F" else "Ilustríssimos Senhores"
        pronome_corpo = "Vossas Senhorias"
    else:
        vocativo = "Ilustríssima Senhora" if genero == "F" else "Ilustríssimo Senhor"
        pronome_corpo = "Vossa Senhoria"

    return DestinatarioProcessado(
        tratamento_rodape=tratamento_rodape,
        destinatario_nome=nome.upper(),
        destinatario_endereco=endereco_final.strip(),
        vocativo=vocativo,
        pronome_corpo=pronome_corpo,
        envio=envio,
    )
