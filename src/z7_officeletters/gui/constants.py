"""GUI colour palettes, mutable active palette, and shared regex patterns.

All GUI modules import ``_C`` from here and mutate it in-place when the user
switches themes so every widget creation call picks up the new colours
without needing to be notified explicitly.

Public exports:
    _DARK: Dark-theme colour map.
    _LIGHT: Light-theme colour map.
    _C: Mutable active palette (initialised to ``_DARK``).
    _RE_PROPOSITURA_SPLIT: Pre-compiled regex that splits multi-propositura text files.
    _RE_TIPO_PROPOSITURA: Pre-compiled regex that identifies the type of each block.
    detectar_tipo_propositura: Return the detected type of a propositura text block.
"""

from __future__ import annotations

import re

__all__ = ["_DARK", "_LIGHT", "_C", "_RE_PROPOSITURA_SPLIT", "_RE_TIPO_PROPOSITURA", "detectar_tipo_propositura", "numero_propositura"]

_DARK: dict[str, str] = {
    "bg":      "#0f111a",
    "card":    "#1a1d2e",
    "panel":   "#22253a",
    "border":  "#2e3150",
    "accent":  "#4f8ef7",
    "accent2": "#3a7aee",
    "success": "#57c77c",
    "error":   "#f07178",
    "warn":    "#ffb454",
    "text":    "#cdd6f4",
    "dim":     "#6c7086",
}

_LIGHT: dict[str, str] = {
    "bg":      "#f0f2f8",
    "card":    "#ffffff",
    "panel":   "#e8ecf6",
    "border":  "#c8cedf",
    "accent":  "#2563eb",
    "accent2": "#1d4ed8",
    "success": "#16a34a",
    "error":   "#dc2626",
    "warn":    "#d97706",
    "text":    "#1e2030",
    "dim":     "#6b7280",
}

# Mutable active palette — updated in-place by _toggle_theme.
_C: dict[str, str] = dict(_DARK)

# Splits a multi-propositura text file at each "MOÇÃO Nº" or "REQUERIMENTO Nº" header.
_RE_PROPOSITURA_SPLIT: re.Pattern[str] = re.compile(
    r'(?=(?:MOÇÃO|REQUERIMENTO)\s+N[º°])', re.IGNORECASE
)

# Identifies the type of a propositura block from its opening header.
_RE_TIPO_PROPOSITURA: re.Pattern[str] = re.compile(
    r'^(?P<tipo>MOÇÃO|REQUERIMENTO(?:\s+DE\s+PESAR)?)\s+N[º°]', re.IGNORECASE
)

# Extracts the sequential number from a propositura header line.
_RE_NUMERO_PROPOSITURA: re.Pattern[str] = re.compile(
    r'(?:MOÇÃO|REQUERIMENTO(?:\s+DE\s+PESAR)?)\s+N[º°]\s*(\d+)', re.IGNORECASE
)


def numero_propositura(texto: str) -> int:
    """Extract the sequential number from a propositura header for sorting.

    Args:
        texto: Raw text of a single propositura block.

    Returns:
        The integer number found in the header, or 0 if not matched.
    """
    m = _RE_NUMERO_PROPOSITURA.search(texto.lstrip())
    return int(m.group(1)) if m else 0


def detectar_tipo_propositura(texto: str) -> str:
    """Return the propositura type detected from the block's opening header.

    Args:
        texto: Raw text of a single propositura block.

    Returns:
        ``"requerimento_pesar"`` if the block starts with a *requerimento*
        header; ``"mocao"`` otherwise (including when no header is matched).
    """
    m = _RE_TIPO_PROPOSITURA.match(texto.lstrip())
    if m and m.group("tipo").upper().startswith("REQUERIMENTO"):
        return "requerimento_pesar"
    return "mocao"
