"""Tests for the pure helper functions in the processing worker."""

from __future__ import annotations

import pytest

from z7_officeletters.gui.workers.processor import _formatar_lista_pt, _normalizar_dest


# =============================================================================
# _normalizar_dest
# =============================================================================
class TestNormalizarDest:

    def test_uppercase(self) -> None:
        assert _normalizar_dest("João Silva") == "JOÃO SILVA"

    def test_colapsa_espacos(self) -> None:
        assert _normalizar_dest("  Maria   Santos  ") == "MARIA SANTOS"

    def test_ja_maiusculo(self) -> None:
        assert _normalizar_dest("PREFEITURA MUNICIPAL") == "PREFEITURA MUNICIPAL"

    def test_string_vazia(self) -> None:
        assert _normalizar_dest("") == ""

    def test_nome_simples(self) -> None:
        assert _normalizar_dest("alex dantas") == "ALEX DANTAS"


# =============================================================================
# _formatar_lista_pt
# =============================================================================
class TestFormatarListaPt:

    def test_um_item(self) -> None:
        assert _formatar_lista_pt(["Aplauso"]) == "Aplauso"

    def test_dois_itens(self) -> None:
        assert _formatar_lista_pt(["10", "15"]) == "10 e 15"

    def test_tres_itens(self) -> None:
        assert _formatar_lista_pt(["10", "15", "20"]) == "10, 15 e 20"

    def test_quatro_itens(self) -> None:
        assert _formatar_lista_pt(["a", "b", "c", "d"]) == "a, b, c e d"

    def test_deduplica_preservando_ordem(self) -> None:
        assert _formatar_lista_pt(["10", "10", "15"]) == "10 e 15"

    def test_deduplica_unico_repetido(self) -> None:
        assert _formatar_lista_pt(["Aplauso", "Aplauso"]) == "Aplauso"

    def test_preserva_ordem_insercao(self) -> None:
        assert _formatar_lista_pt(["15", "10"]) == "15 e 10"

    def test_tipos_mocao_distintos(self) -> None:
        assert _formatar_lista_pt(["Aplauso", "Apoio"]) == "Aplauso e Apoio"


# =============================================================================
# grouping key consistency
# =============================================================================
class TestAgrupamentoPorDestinatario:
    """Verify that the normalisation key correctly identifies same/different recipients."""

    def test_mesmo_nome_maiusculas_minusculas(self) -> None:
        assert _normalizar_dest("Prefeitura Municipal") == _normalizar_dest("PREFEITURA MUNICIPAL")

    def test_nomes_distintos_nao_colidem(self) -> None:
        assert _normalizar_dest("João Silva") != _normalizar_dest("Maria Santos")
