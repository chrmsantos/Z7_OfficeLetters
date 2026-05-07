"""Address database loaded from the ``enderecam_padrao.docx`` file.

The file contains one address block per recipient, each starting with a
*tratamento* header line (e.g. ``"A Sua Excelência o Senhor"``).  The
remaining lines hold the name, position/title, physical address and e-mail.

Priority rule applied by the caller:
  1. Data from this database (most authoritative).
  2. Data extracted from the propositura by the AI.
  3. Data sourced from the internet (future / out of scope here).

Public exports:
    EntradaEndereco: Parsed address block (NamedTuple).
    carregar_db: Parse a ``.docx`` file and return all entries.
    buscar_endereco: Fuzzy look-up a recipient by name.
    resetar_cache: Force the next call to ``buscar_endereco`` to reload.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import NamedTuple

__all__ = ["EntradaEndereco", "carregar_db", "buscar_endereco", "resetar_cache"]


class EntradaEndereco(NamedTuple):
    """One recipient block parsed from the address database."""

    tratamento: str  # e.g. "A Sua Excelência o Senhor"
    nome: str        # first name/title line (usually all-caps)
    cargo: str       # position/title lines joined with newline
    endereco: str    # physical address lines joined with newline
    email: str       # first e-mail found, or ""


# ── Regexes ───────────────────────────────────────────────────────────────────

_RE_EMAIL: re.Pattern[str] = re.compile(r"\S+@\S+\.\S+")

_RE_ADDRESS_HINT: re.Pattern[str] = re.compile(
    r"\b(?:Rua|Av\.|Avenida|Pra[çc]a|Estrada|Bloco|Pal[áa]cio|Esplanada|"
    r"Travessa|CEP|Alameda|Rodovia|Largo|T[eé]rreo|Andar)\b",
    re.IGNORECASE,
)

# A line that starts a new address-book entry begins with one of these patterns.
_RE_TRATAMENTO_START: re.Pattern[str] = re.compile(
    r"^(?:A\s+Sua\s+Excel[êe]ncia|À\s+Sua\s+Excel[êe]ncia|Aos\s+Cuidados|"
    r"À\s+|Ao\s+|À$|Ao$)",
    re.IGNORECASE,
)


# ── Module-level cache ────────────────────────────────────────────────────────

_cached_db: list[EntradaEndereco] = []
_cached_path: Path | None = None


# ── Internal helpers ──────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    """Lowercase and strip diacritics for accent-insensitive comparison."""
    return unicodedata.normalize("NFD", s.lower()).encode("ascii", "ignore").decode()


def _parse_entries(paragraphs: list[str]) -> list[EntradaEndereco]:
    """Group raw paragraph strings into blocks and parse each block.

    A new block starts whenever a *tratamento* header line is detected.
    Within each block, lines are classified as cargo, address or e-mail.

    Args:
        paragraphs: All paragraph texts from the docx (including empty ones).

    Returns:
        List of parsed ``EntradaEndereco`` objects.
    """
    # ── Split into raw blocks ─────────────────────────────────────────────────
    blocks: list[list[str]] = []
    current: list[str] | None = None
    for raw in paragraphs:
        line = raw.strip()
        if _RE_TRATAMENTO_START.match(line) or line in ("À", "Ao"):
            if current is not None:
                blocks.append(current)
            current = [line]
        elif current is not None:
            current.append(line)
    if current:
        blocks.append(current)

    # ── Parse each block ──────────────────────────────────────────────────────
    entries: list[EntradaEndereco] = []
    for block in blocks:
        non_empty = [ln for ln in block if ln]
        if len(non_empty) < 2:
            continue

        tratamento = non_empty[0]
        nome = non_empty[1]
        cargo_parts: list[str] = []
        addr_parts: list[str] = []
        email_parts: list[str] = []

        for line in non_empty[2:]:
            if _RE_EMAIL.search(line):
                email_parts.append(line)
            elif _RE_ADDRESS_HINT.search(line):
                addr_parts.append(line)
            else:
                cargo_parts.append(line)

        entries.append(EntradaEndereco(
            tratamento=tratamento,
            nome=nome,
            cargo="\n".join(cargo_parts),
            endereco="\n".join(addr_parts),
            email=email_parts[0] if email_parts else "",
        ))

    return entries


# ── Public API ────────────────────────────────────────────────────────────────

def carregar_db(path: Path) -> list[EntradaEndereco]:
    """Parse *path* (a ``.docx`` file) and return all address entries.

    Returns an empty list if the file cannot be read (missing or corrupt),
    so the caller can degrade gracefully without raising.

    Args:
        path: Filesystem path to ``enderecam_padrao.docx`` (or similar).

    Returns:
        List of ``EntradaEndereco`` objects; may be empty.
    """
    try:
        from docx import Document  # type: ignore[import-untyped]  # noqa: PLC0415

        doc = Document(str(path))
        paragraphs = [p.text for p in doc.paragraphs]
    except Exception:  # noqa: BLE001
        return []
    return _parse_entries(paragraphs)


def resetar_cache() -> None:
    """Discard the in-memory cache so the next lookup reloads from disk.

    Useful in tests that swap the db file between calls.
    """
    global _cached_db, _cached_path  # noqa: PLW0603
    _cached_db = []
    _cached_path = None


def buscar_endereco(nome: str, db_path: Path | None = None) -> EntradaEndereco | None:
    """Return the database entry that best matches *nome*, or ``None``.

    Matching uses two passes (both accent-insensitive):

    1. Check whether the normalised query appears anywhere in the entry's
       ``nome + cargo`` text (handles abbreviated queries like ``"DETRAN"``).
    2. Check whether the normalised entry name appears as a substring inside
       the query (handles the AI returning the full canonical name).

    The address lines are intentionally excluded from matching to avoid false
    positives on common place names (e.g. ``"São Paulo"``).

    Args:
        nome: Recipient name as returned by the Gemini AI.
        db_path: Path to the ``.docx`` database file.  When provided and
            different from the previously loaded path the cache is refreshed.

    Returns:
        The first matching ``EntradaEndereco``, or ``None`` if not found.
    """
    global _cached_db, _cached_path  # noqa: PLW0603

    if db_path is not None and db_path != _cached_path:
        _cached_db = carregar_db(db_path)
        _cached_path = db_path

    if not _cached_db:
        return None

    nome_norm = _norm(nome.strip())
    if len(nome_norm) < 4:  # avoid spurious matches on very short strings
        return None

    for entry in _cached_db:
        searchable = _norm(f"{entry.nome} {entry.cargo}")
        entry_nome_norm = _norm(entry.nome)
        if nome_norm in searchable or entry_nome_norm in nome_norm:
            return entry

    return None
