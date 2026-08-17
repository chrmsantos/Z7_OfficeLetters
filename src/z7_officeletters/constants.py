"""Application-wide constants that do not depend on runtime configuration.

These values are set at import time and never mutated.  They serve as the
single source of truth for paths, ordered sequences, and locale helpers.

Public exports:
    MESES_PT: Portuguese month names (1-indexed dict).
    ORDEM_PREFERENCIA: Preferred file-extension order for propositions.
    FORMATOS_SUPORTADOS: Frozenset of supported file extensions.
    MODELO_OFICIO: Relative path to the Word letter template.
    MODELO_PLANILHA: Relative path to the Excel spreadsheet template.
    BASE_DIR: Root directory for user data (logs, output, input).
    PASTA_SAIDA: Absolute path to the generated letters folder.
    PASTA_LOGS: Absolute path to the rotating log files folder.
    PASTA_PROPOSITURAS: Absolute path to the proposition input folder.
    PASTA_PLANILHA: Absolute path to the generated spreadsheet folder.
    PASTA_PROPOSITURAS_FONTE: Absolute path to the source propositions backup folder.
    MAX_TENTATIVAS_IA: Maximum Gemini API retry attempts per call.
    RETRY_DELAY_PADRAO_S: Default wait (seconds) on a 429 rate-limit.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

__all__ = [
    "MESES_PT",
    "ORDEM_PREFERENCIA",
    "FORMATOS_SUPORTADOS",
    "MODELO_OFICIO",
    "MODELO_REQUERIMENTO_PESAR",
    "MODELO_PLANILHA",
    "MODELO_ENVELOPE",
    "ENDERECAMENTO_PADRAO",
    "BASE_DIR",
    "PASTA_SAIDA",
    "PASTA_LOGS",
    "PASTA_LOG_IA",
    "PASTA_PLANILHA",
    "PASTA_ENVELOPES",
    "PASTA_PROPOSITURAS_FONTE",
    "MAX_TENTATIVAS_IA",
    "RETRY_DELAY_PADRAO_S",
    "RE_PROPOSITURA_SPLIT",
    "RE_TIPO_PROPOSITURA",
    "detectar_tipo_propositura",
    "numero_propositura",
]

# ── Locale ────────────────────────────────────────────────────────────────────
MESES_PT: dict[int, str] = {
    1: "janeiro",
    2: "fevereiro",
    3: "março",
    4: "abril",
    5: "maio",
    6: "junho",
    7: "julho",
    8: "agosto",
    9: "setembro",
    10: "outubro",
    11: "novembro",
    12: "dezembro",
}

# ── File resolution ───────────────────────────────────────────────────────────
# Preferred order: plain text first, richest format last, PDF as fallback.
ORDEM_PREFERENCIA: tuple[str, ...] = (".txt", ".docx", ".doc", ".odt", ".pdf")
FORMATOS_SUPORTADOS: frozenset[str] = frozenset(ORDEM_PREFERENCIA)

# ── Template paths (relative to the application root) ────────────────────────
MODELO_OFICIO: str = "templates/modelo_mocao.docx"
MODELO_REQUERIMENTO_PESAR: str = "templates/modelo_requer_pesar.docx"
MODELO_PLANILHA: str = "templates/modelo_planilha.xlsx"
MODELO_ENVELOPE: str = "templates/modelo_envelope.docx"

# ── Address database (optional — app degrades gracefully if missing) ──────────
ENDERECAMENTO_PADRAO: str = "ender/enderecamentos_padrao.docx"

# ── User-data directories ─────────────────────────────────────────────────────
# All user-generated data lives inside the project's /local directory
# (excluded from version control via .gitignore).
BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent / "local"

PASTA_SAIDA: str = str(BASE_DIR / "oficios_gerados")
# Logs live inside the project tree (dev) or next to the exe (frozen).
if getattr(sys, "frozen", False):
    PASTA_LOGS: str = str(Path(sys.executable).parent / "logs")
else:
    PASTA_LOGS: str = str(Path(__file__).parent.parent.parent / "logs")
PASTA_LOG_IA: str = str(Path(PASTA_LOGS) / "ia")
PASTA_PLANILHA: str = str(BASE_DIR / "planilha_gerada")
PASTA_ENVELOPES: str = str(BASE_DIR / "envelopes_gerados")
PASTA_PROPOSITURAS_FONTE: str = str(BASE_DIR / "proposituras_fonte")

# ── AI retry policy ───────────────────────────────────────────────────────────
MAX_TENTATIVAS_IA: int = 5
RETRY_DELAY_PADRAO_S: int = 60
# ── Propositura text-parsing patterns ───────────────────────────────────────

# Splits a multi-propositura text at each “MOÇÃO Nº” / “REQUERIMENTO Nº” header.
RE_PROPOSITURA_SPLIT: re.Pattern[str] = re.compile(
    r'(?=(?:MOÇÃO|REQUERIMENTO)\s+N[\u00ba\u00b0])', re.IGNORECASE
)

# Identifies the type of a propositura block from its opening header.
RE_TIPO_PROPOSITURA: re.Pattern[str] = re.compile(
    r'^(?P<tipo>MOÇÃO|REQUERIMENTO(?:\s+DE\s+PESAR)?)\s+N[\u00ba\u00b0]', re.IGNORECASE
)

# Extracts the sequential number from a propositura header line.
_RE_NUMERO_PROPOSITURA: re.Pattern[str] = re.compile(
    r'(?:MOÇÃO|REQUERIMENTO(?:\s+DE\s+PESAR)?)\s+N[\u00ba\u00b0]\s*(\d+)', re.IGNORECASE
)


def numero_propositura(texto: str) -> int:
    """Extract the sequential number from a propositura header for sorting.

    Returns:
        The integer number found in the header, or 0 if not matched.
    """
    m = _RE_NUMERO_PROPOSITURA.search(texto.lstrip())
    return int(m.group(1)) if m else 0


def detectar_tipo_propositura(texto: str) -> str:
    """Return the propositura type detected from the block's opening header.

    Returns:
        ``"requerimento_pesar"`` if the block starts with a *requerimento*
        header; ``"mocao"`` otherwise.
    """
    m = RE_TIPO_PROPOSITURA.match(texto.lstrip())
    if m and m.group("tipo").upper().startswith("REQUERIMENTO"):
        return "requerimento_pesar"
    return "mocao"