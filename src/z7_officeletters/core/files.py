"""File listing and multi-format text extraction.

Scans the proposition input folder, deduplicates files with the same stem
by keeping the preferred format, and reads text from ``.txt``, ``.docx``,
``.doc``, ``.odt``, and ``.pdf`` files.

Public exports:
    listar_proposituras: List supported proposition files in the input folder.
    resolver_arquivo_preferencial: Return the best-format variant for a given path.
    ler_arquivo_mocoes: Extract text from a supported file.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from z7_officeletters.constants import (
    FORMATOS_SUPORTADOS,
    ORDEM_PREFERENCIA,
    PASTA_PROPOSITURAS,
)

__all__ = [
    "listar_proposituras",
    "resolver_arquivo_preferencial",
    "ler_arquivo_mocoes",
]

# ODT XML namespace for text content.
_ODT_NS: str = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"


def resolver_arquivo_preferencial(caminho: str) -> str:
    """Return the highest-priority variant for a file path.

    Given any supported file path, checks whether sibling files with the same
    stem exist in higher-priority formats and returns the best one found.
    If no better variant exists the original *caminho* is returned unchanged.

    Args:
        caminho: Absolute or relative path to a supported proposition file.

    Returns:
        Path string of the highest-priority existing variant.
    """
    p = Path(caminho)
    base = p.parent / p.stem
    for ext in ORDEM_PREFERENCIA:
        candidato = base.with_suffix(ext)
        if candidato.exists():
            return str(candidato)
    return caminho


def listar_proposituras() -> list[Path]:
    """List all supported proposition files in ``PASTA_PROPOSITURAS``.

    When two files share the same stem (e.g. ``mocoes.txt`` and
    ``mocoes.docx``), only the higher-priority format is included so the
    caller does not process the same content twice.

    Returns:
        Alphabetically sorted list of ``Path`` objects for unique propositions.
        An empty list is returned (and the folder created) if it does not exist.
    """
    pasta = Path(PASTA_PROPOSITURAS)
    if not pasta.is_dir():
        pasta.mkdir(parents=True, exist_ok=True)
        return []

    vistos: dict[str, Path] = {}

    for arq in sorted(pasta.iterdir()):
        if arq.suffix.lower() not in FORMATOS_SUPORTADOS:
            continue
        pref = Path(resolver_arquivo_preferencial(str(arq)))
        if pref.stem not in vistos:
            vistos[pref.stem] = pref

    return list(vistos.values())


def _extrair_texto_odt(caminho: str) -> str:
    """Extract plain text from an ``.odt`` file.

    Uses only the standard library (``zipfile`` + ``xml.etree``) to avoid
    introducing additional runtime dependencies.

    Args:
        caminho: Absolute path to the ``.odt`` file.

    Returns:
        Extracted text with paragraphs separated by newlines.
    """
    with zipfile.ZipFile(caminho, "r") as zf:
        with zf.open("content.xml") as fh:
            tree = ET.parse(fh)

    partes: list[str] = []
    for elem in tree.iter():
        tag = elem.tag
        if tag in (f"{{{_ODT_NS}}}p", f"{{{_ODT_NS}}}line-break"):
            partes.append("".join(elem.itertext()))
    return "\n".join(partes)


def ler_arquivo_mocoes(caminho: str) -> str:
    """Extract and return the full text of a proposition file.

    Supports ``.txt``, ``.docx``, ``.doc``, ``.odt``, and ``.pdf`` formats.
    Heavy dependencies (``docx``, ``win32com``, ``pypdf``) are imported lazily
    to keep module load time fast when running tests.

    Args:
        caminho: Absolute path to the proposition file.

    Returns:
        Full text content of the file.

    Raises:
        ImportError: If the required optional dependency is not installed.
        ValueError: If the file extension is not supported.
    """
    sufixo = Path(caminho).suffix.lower()

    if sufixo == ".txt":
        try:
            with Path(caminho).open("r", encoding="utf-8") as fh:
                return fh.read()
        except UnicodeDecodeError:
            with Path(caminho).open("r", encoding="latin-1") as fh:
                return fh.read()

    if sufixo == ".docx":
        import docx as _docx  # noqa: PLC0415

        doc = _docx.Document(caminho)
        return "\n".join(p.text for p in doc.paragraphs)

    if sufixo == ".doc":
        try:
            import win32com.client  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "Para ler arquivos .doc instale pywin32: pip install pywin32"
            ) from exc
        word = None
        try:
            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False
            doc_com = word.Documents.Open(str(Path(caminho).resolve()))
            texto: str = doc_com.Content.Text
            doc_com.Close(False)
        finally:
            if word is not None:
                try:
                    word.Quit()
                except Exception:
                    pass
        return texto

    if sufixo == ".odt":
        return _extrair_texto_odt(caminho)

    if sufixo == ".pdf":
        try:
            import pypdf as _pypdf  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "Para ler arquivos .pdf instale pypdf: pip install pypdf"
            ) from exc
        reader = _pypdf.PdfReader(caminho)
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    raise ValueError(
        f"Formato '{sufixo}' não suportado. Use .txt, .docx, .doc, .odt ou .pdf."
    )
