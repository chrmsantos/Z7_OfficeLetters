"""Author name resolution and attribution formatting.

Converts the raw author list returned by the AI into:
- A human-readable attribution string (``"do vereador Alex Dantas"``).
- A combined file-name sigla (``"ad e outros"``).

Matching is done via case-insensitive substring search with a Unicode
normalization fallback so that accent variations (e.g. the AI returning
``"Jose Luis"`` instead of ``"José Luis"``) are resolved correctly.

The module-level lookup tables are rebuilt from ``config.MAPA_AUTORES``
on import and again whenever ``rebuild_tables()`` is called (e.g. after the
user saves the config editor).

Public exports:
    norm: Strip accents and lowercase a string for fuzzy matching.
    formatar_autores: Format an author list into attribution text + sigla.
    sigla_autor: Return the individual sigla for a single author name.
    rebuild_tables: Rebuild lookup tables after MAPA_AUTORES changes.
"""

from __future__ import annotations

import unicodedata

import z7_officeletters.core.config as _config

__all__ = ["norm", "formatar_autores", "sigla_autor", "rebuild_tables"]


def norm(s: str) -> str:
    """Lowercase and remove diacritics for accent-insensitive matching.

    Args:
        s: Input string (may contain accented characters).

    Returns:
        ASCII-only lowercased string with diacritics stripped.
    """
    return unicodedata.normalize("NFD", s.lower()).encode("ascii", "ignore").decode()


# ── Lookup tables (rebuilt by rebuild_tables) ─────────────────────────────────

# Exact lowercase key → sigla pairs, used for the first matching pass.
_MAPA_AUTORES_ITENS: tuple[tuple[str, str], ...] = tuple(
    (nome.lower(), sigla) for nome, sigla in _config.MAPA_AUTORES.items()
)

# Exact lowercase key → canonical-cased name (e.g. "alex dantas" → "Alex Dantas").
_MAPA_AUTORES_CASING: dict[str, str] = {
    nome.lower(): nome for nome in _config.MAPA_AUTORES
}

# Accent-stripped key → sigla pairs, used as a fallback matching pass.
_MAPA_AUTORES_ITENS_NORM: tuple[tuple[str, str], ...] = tuple(
    (norm(nome), sigla) for nome, sigla in _config.MAPA_AUTORES.items()
)

# Accent-stripped key → canonical-cased name.
_MAPA_AUTORES_CASING_NORM: dict[str, str] = {
    norm(nome): nome for nome in _config.MAPA_AUTORES
}

# Lowercased names of female councillors for gender-correct attribution.
_VEREADORES_FEMININO_LOWER: frozenset[str] = frozenset(
    nome.lower() for nome in _config.CONFIG.get("vereadores_feminino", [])
)


def rebuild_tables() -> None:
    """Rebuild all lookup tables from the current ``config.MAPA_AUTORES``.

    Must be called after ``config.reload_config()`` so the author lookup
    tables stay in sync with the updated configuration.
    """
    global _MAPA_AUTORES_ITENS  # noqa: PLW0603
    global _MAPA_AUTORES_CASING
    global _MAPA_AUTORES_ITENS_NORM
    global _MAPA_AUTORES_CASING_NORM
    global _VEREADORES_FEMININO_LOWER
    _MAPA_AUTORES_ITENS = tuple(
        (nome.lower(), sigla) for nome, sigla in _config.MAPA_AUTORES.items()
    )
    _MAPA_AUTORES_CASING = {nome.lower(): nome for nome in _config.MAPA_AUTORES}
    _MAPA_AUTORES_ITENS_NORM = tuple(
        (norm(nome), sigla) for nome, sigla in _config.MAPA_AUTORES.items()
    )
    _MAPA_AUTORES_CASING_NORM = {norm(nome): nome for nome in _config.MAPA_AUTORES}
    _VEREADORES_FEMININO_LOWER = frozenset(
        nome.lower() for nome in _config.CONFIG.get("vereadores_feminino", [])
    )


def _resolve_sigla(autor_lower: str, autor_norm: str) -> str:
    """Return the sigla for an author name using a two-pass lookup.

    First pass: exact lowercase substring match against config keys.
    Second pass: accent-stripped substring match (handles AI omitting accents).

    Args:
        autor_lower: Lowercased version of the AI-returned author name.
        autor_norm: Accent-stripped + lowercased version of the same name.

    Returns:
        Sigla string (lowercase) or ``"indef"`` if the author is unknown.
    """
    return (
        next((s for k, s in _MAPA_AUTORES_ITENS if k in autor_lower), None)
        or next((s for k, s in _MAPA_AUTORES_ITENS_NORM if k in autor_norm), "indef")
    )


def _resolve_casing(autor_lower: str, autor_norm: str, fallback: str) -> str:
    """Return the canonical-cased name for an author.

    Uses the same two-pass lookup as ``_resolve_sigla``; falls back to
    ``str.title()`` of the original name when not found in config.

    When multiple config keys match (e.g. both ``"Júlio César"`` and
    ``"Júlio César Santos da Silva"``), the **longest** key wins so that
    the most specific (full) canonical name is preferred.

    Args:
        autor_lower: Lowercased version of the AI-returned author name.
        autor_norm: Accent-stripped + lowercased version of the same name.
        fallback: The original AI-returned name (used for title-casing).

    Returns:
        Canonical-cased name string.
    """
    best: str | None = None
    best_len = 0
    for k, v in _MAPA_AUTORES_CASING.items():
        if k in autor_lower and len(k) > best_len:
            best = v
            best_len = len(k)
    if best:
        return best
    for k, v in _MAPA_AUTORES_CASING_NORM.items():
        if k in autor_norm and len(k) > best_len:
            best = v
            best_len = len(k)
    return best or fallback.title()


def formatar_autores(lista_autores: list[str]) -> tuple[str, str]:
    """Format a list of author names into an attribution string and a combined sigla.

    The attribution string follows the Portuguese legislative style:
    - ``"do vereador Alex Dantas"`` (single male author)
    - ``"da vereadora Esther Moraes"`` (single female author)
    - ``"dos vereadores Alex Dantas e Arnaldo Alves"`` (mixed or all-male)
    - ``"das vereadoras ..."`` (all-female group)

    The combined sigla uses the first known author's sigla followed by
    ``"e outros"`` when there is more than one author.  If no author is
    recognised, ``"indef"`` is used.

    Args:
        lista_autores: Raw author names as returned by the Gemini AI.

    Returns:
        A two-tuple ``(texto_autoria, sigla_final)``.
    """
    siglas: list[str] = []
    nomes_limpos: list[str] = []
    femininos: list[bool] = []

    for autor in lista_autores:
        autor_lower = autor.lower()
        autor_n = norm(autor)
        siglas.append(_resolve_sigla(autor_lower, autor_n).lower())
        nomes_limpos.append(_resolve_casing(autor_lower, autor_n, autor))
        femininos.append(any(f in autor_lower for f in _VEREADORES_FEMININO_LOWER))

    if len(siglas) == 2:
        sigla_final = f"{siglas[0]} e {siglas[1]}"
    else:
        sigla_principal = next((s for s in siglas if s != "indef"), "indef")
        sigla_final = f"{sigla_principal} e outros" if len(siglas) > 1 else sigla_principal
    todas_femininas = all(femininos)

    if len(nomes_limpos) == 1:
        prefixo = "da vereadora" if femininos[0] else "do vereador"
        texto_autoria = f"{prefixo} {nomes_limpos[0]}"
    else:
        nomes_str = ", ".join(nomes_limpos[:-1]) + " e " + nomes_limpos[-1]
        prefixo = "das vereadoras" if todas_femininas else "dos vereadores"
        texto_autoria = f"{prefixo} {nomes_str}"

    return texto_autoria, sigla_final


def sigla_autor(nome: str) -> str:
    """Return the individual sigla for a single author name.

    Args:
        nome: Author name as it appears in text (any casing).

    Returns:
        Lowercase sigla from ``config.MAPA_AUTORES``, or ``"indef"`` if the
        name is not recognised.
    """
    return _resolve_sigla(nome.lower(), norm(nome))
