"""GUI colour palettes, mutable active palette, and shared regex patterns.

All GUI modules import ``_C`` from here and mutate it in-place when the user
switches themes so every widget creation call picks up the new colours
without needing to be notified explicitly.

Text-parsing symbols (``RE_PROPOSITURA_SPLIT``, ``detectar_tipo_propositura``,
``numero_propositura``) live canonically in ``z7_officeletters.constants`` and
are re-exported here for backward compatibility.

Public exports:
    _DARK: Dark-theme colour map.
    _LIGHT: Light-theme colour map.
    _C: Mutable active palette (initialised to ``_DARK``).
    _RE_PROPOSITURA_SPLIT: Alias for ``RE_PROPOSITURA_SPLIT`` (backward compat).
    _RE_TIPO_PROPOSITURA: Alias for ``RE_TIPO_PROPOSITURA`` (backward compat).
    detectar_tipo_propositura: Return the detected type of a propositura text block.
    numero_propositura: Extract the sequential number from a propositura block.
"""

from __future__ import annotations

from z7_officeletters.constants import (
    RE_PROPOSITURA_SPLIT as _RE_PROPOSITURA_SPLIT,
    RE_TIPO_PROPOSITURA as _RE_TIPO_PROPOSITURA,
    detectar_tipo_propositura,
    numero_propositura,
)

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
