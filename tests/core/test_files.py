"""Tests for z7_officeletters.core.files."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from z7_officeletters.core.files import (
    ler_arquivo_mocoes,
)


# =============================================================================
# ler_arquivo_mocoes
# =============================================================================
class TestLerArquivoMocoes:

    def test_le_txt_utf8(self, tmp_path: Path) -> None:
        f = tmp_path / "mocoes.txt"
        f.write_text("MOÇÃO Nº 1\nTexto.", encoding="utf-8")
        assert ler_arquivo_mocoes(str(f)) == "MOÇÃO Nº 1\nTexto."

    def test_txt_preserva_conteudo_completo(self, tmp_path: Path) -> None:
        conteudo = "MOÇÃO Nº 1\n\nMOÇÃO Nº 2\nSegundo texto."
        f = tmp_path / "mocoes.txt"
        f.write_text(conteudo, encoding="utf-8")
        assert ler_arquivo_mocoes(str(f)) == conteudo

    def test_formato_invalido_levanta_value_error(self, tmp_path: Path) -> None:
        f = tmp_path / "mocoes.xyz"
        f.write_text("x")
        with pytest.raises(ValueError, match="suportado"):
            ler_arquivo_mocoes(str(f))

    def test_le_docx_via_mock(self, tmp_path: Path) -> None:
        mock_doc = MagicMock()
        mock_doc.paragraphs = [
            MagicMock(text="MOÇÃO Nº 1"),
            MagicMock(text="Texto."),
        ]
        with patch("docx.Document", return_value=mock_doc):
            resultado = ler_arquivo_mocoes(str(tmp_path / "mocoes.docx"))
        assert resultado == "MOÇÃO Nº 1\nTexto."

    def test_pdf_sem_pypdf_levanta_import_error(self, tmp_path: Path) -> None:
        f = tmp_path / "mocoes.pdf"
        f.write_bytes(b"%PDF-1.4")
        with patch.dict("sys.modules", {"pypdf": None}):
            with pytest.raises(ImportError, match="pypdf"):
                ler_arquivo_mocoes(str(f))
