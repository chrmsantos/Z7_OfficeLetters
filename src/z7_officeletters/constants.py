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
    MAX_TENTATIVAS_IA: Maximum Gemini API retry attempts per call.
    RETRY_DELAY_PADRAO_S: Default wait (seconds) on a 429 rate-limit.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

__all__ = [
    "MESES_PT",
    "ORDEM_PREFERENCIA",
    "FORMATOS_SUPORTADOS",
    "MODELO_OFICIO",
    "MODELO_REQUERIMENTO_PESAR",
    "MODELO_PLANILHA",
    "ENDERECAMENTO_PADRAO",
    "BASE_DIR",
    "PASTA_SAIDA",
    "PASTA_LOGS",
    "PASTA_PROPOSITURAS",
    "PASTA_PLANILHA",
    "MAX_TENTATIVAS_IA",
    "RETRY_DELAY_PADRAO_S",
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

# ── Address database (optional — app degrades gracefully if missing) ──────────
ENDERECAMENTO_PADRAO: str = "ender/enderecam_padrao.docx"

# ── User-data directories ─────────────────────────────────────────────────────
BASE_DIR: Path = (
    Path(os.environ.get("USERPROFILE", str(Path.home())))
    / "AppData"
    / "Local"
    / "Z7"
    / "Tmp"
    / "OfficeLetters"
)

PASTA_SAIDA: str = str(BASE_DIR / "oficios_gerados")
# Logs live inside the project tree (dev) or next to the exe (frozen).
if getattr(sys, "frozen", False):
    PASTA_LOGS: str = str(Path(sys.executable).parent / "logs")
else:
    PASTA_LOGS: str = str(Path(__file__).parent.parent.parent / "logs")
PASTA_PROPOSITURAS: str = str(BASE_DIR / "proposituras")
PASTA_PLANILHA: str = str(BASE_DIR / "planilha_gerada")

# ── AI retry policy ───────────────────────────────────────────────────────────
MAX_TENTATIVAS_IA: int = 5
RETRY_DELAY_PADRAO_S: int = 60
