"""Tests for the pure helper functions in the processing worker."""

from __future__ import annotations

import pytest

from z7_officeletters.core.documents import (
    formatar_lista_pt as _formatar_lista_pt,
    frases_propositura as _frases_propositura,
)
from z7_officeletters.core.recipients import aplicar_tratamento_db as _aplicar_tratamento_db
from z7_officeletters.gui.workers.processor import _normalizar_dest


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


# =============================================================================
# _aplicar_tratamento_db
# =============================================================================

def _info_base_masculino() -> dict:
    """Recipient info as produced by processar_destinatario for a generic male."""
    return {
        "tratamento_rodape": "Ao Ilustríssimo Senhor",
        "vocativo": "Ilustríssimo Senhor",
        "pronome_corpo": "Vossa Senhoria",
    }


def _info_base_feminino() -> dict:
    """Recipient info as produced by processar_destinatario for a generic female."""
    return {
        "tratamento_rodape": "À Ilustríssima Senhora",
        "vocativo": "Ilustríssima Senhora",
        "pronome_corpo": "Vossa Senhoria",
    }


def _info_ai_genero_errado() -> dict:
    """Simulates the AI guessing masculine when the DB says the recipient is female."""
    return {
        "tratamento_rodape": "Ao Ilustríssimo Senhor",
        "vocativo": "Ilustríssimo Senhor",
        "pronome_corpo": "Vossa Senhoria",
    }


class TestAplicarTratamentoDB:

    # --- Excelência ---
    def test_excelencia_masculino(self) -> None:
        info = _info_base_masculino()
        _aplicar_tratamento_db(info, "A Sua Excelência o Senhor")
        assert info["tratamento_rodape"] == "A Sua Excelência o Senhor"
        assert info["vocativo"] == "Excelentíssimo Senhor"
        assert info["pronome_corpo"] == "Vossa Excelência"

    def test_excelencia_feminino(self) -> None:
        info = _info_base_feminino()
        _aplicar_tratamento_db(info, "À Sua Excelência a Senhora")
        assert info["vocativo"] == "Excelentíssima Senhora"
        assert info["pronome_corpo"] == "Vossa Excelência"

    # --- Cuidados ---
    def test_cuidados(self) -> None:
        info = _info_base_masculino()
        _aplicar_tratamento_db(info, "Aos Cuidados do Sr.")
        assert info["vocativo"] == "Ilustríssimos Senhores(as)"
        assert info["pronome_corpo"] == "Vossas Senhorias"

    # --- Ilustríssim(o|a) — o principal bug corrigido ---
    def test_ilustrissima_corrige_genero_errado_pela_ia(self) -> None:
        """DB diz 'Ilustríssima Senhora' mas IA inferiu masculino — deve corrigir."""
        info = _info_ai_genero_errado()
        _aplicar_tratamento_db(info, "À Ilustríssima Senhora")
        assert info["tratamento_rodape"] == "À Ilustríssima Senhora"
        assert info["vocativo"] == "Ilustríssima Senhora"
        assert info["pronome_corpo"] == "Vossa Senhoria"

    def test_ilustrissimo_mantem_masculino(self) -> None:
        info = _info_base_masculino()
        _aplicar_tratamento_db(info, "Ao Ilustríssimo Senhor")
        assert info["tratamento_rodape"] == "Ao Ilustríssimo Senhor"
        assert info["vocativo"] == "Ilustríssimo Senhor"
        assert info["pronome_corpo"] == "Vossa Senhoria"

    # --- Tratamento de instituição (sem marcador de gênero pessoal) ---
    def test_instituicao_sem_marcador_mantem_valores_anteriores(self) -> None:
        """Tratamento tipo 'Ao SAEC' não deve sobrescrever vocativo/pronome já corretos."""
        info = {
            "tratamento_rodape": "Ao",
            "vocativo": "Ilustríssimos Senhores",
            "pronome_corpo": "Vossas Senhorias",
        }
        _aplicar_tratamento_db(info, "Ao SAEC")
        assert info["tratamento_rodape"] == "Ao SAEC"
        assert info["vocativo"] == "Ilustríssimos Senhores"
        assert info["pronome_corpo"] == "Vossas Senhorias"


# =============================================================================
# _frases_propositura
# =============================================================================
class TestFrazesPropositura:

    # --- Moção singular ---
    def test_mocao_singular_designacao(self) -> None:
        des, _, __ = _frases_propositura("mocao", "Aplauso", 1)
        assert des == "Moção de Aplauso"

    def test_mocao_singular_copia_art(self) -> None:
        _, art, __ = _frases_propositura("mocao", "Aplauso", 1)
        assert art == "cópia da"

    def test_mocao_singular_aprovada(self) -> None:
        _, __, aprov = _frases_propositura("mocao", "Aplauso", 1)
        assert aprov == "aprovada"

    # --- Moção plural ---
    def test_mocao_plural_designacao(self) -> None:
        des, _, __ = _frases_propositura("mocao", "Aplauso", 2)
        assert des == "Moções de Aplauso"

    def test_mocao_plural_copia_art(self) -> None:
        _, art, __ = _frases_propositura("mocao", "Aplauso", 2)
        assert art == "cópias das"

    def test_mocao_plural_aprovada(self) -> None:
        _, __, aprov = _frases_propositura("mocao", "Aplauso", 2)
        assert aprov == "aprovadas"

    def test_mocao_plural_tipos_diferentes(self) -> None:
        des, _, __ = _frases_propositura("mocao", "Aplauso e Apoio", 2)
        assert des == "Moções de Aplauso e Apoio"

    # --- Requerimento de pesar singular ---
    def test_pesar_singular_designacao(self) -> None:
        des, _, __ = _frases_propositura("requerimento_pesar", "", 1)
        assert des == "Requerimento de Pesar"

    def test_pesar_singular_copia_art(self) -> None:
        _, art, __ = _frases_propositura("requerimento_pesar", "", 1)
        assert art == "cópia do"

    def test_pesar_singular_aprovado(self) -> None:
        _, __, aprov = _frases_propositura("requerimento_pesar", "", 1)
        assert aprov == "aprovado"

    # --- Requerimento de pesar plural ---
    def test_pesar_plural_designacao(self) -> None:
        des, _, __ = _frases_propositura("requerimento_pesar", "", 3)
        assert des == "Requerimentos de Pesar"

    def test_pesar_plural_copia_art(self) -> None:
        _, art, __ = _frases_propositura("requerimento_pesar", "", 3)
        assert art == "cópias dos"

    def test_pesar_plural_aprovados(self) -> None:
        _, __, aprov = _frases_propositura("requerimento_pesar", "", 3)
        assert aprov == "aprovados"


# =============================================================================
# DB-override pronome consistency (nivel_protocolo forms)
# =============================================================================
class TestAplicarTratamentoDB_Consistencia:
    """Verify that all three pronome fields are always in sync after DB override."""

    def test_ve_m_crase_masculino_consistente(self) -> None:
        """DB with 'À Sua Excelência o Senhor' (VE_M) must sync all three fields."""
        info = _info_base_masculino()
        _aplicar_tratamento_db(info, "À Sua Excelência o Senhor")
        assert info["tratamento_rodape"] == "À Sua Excelência o Senhor"
        assert info["vocativo"] == "Excelentíssimo Senhor"
        assert info["pronome_corpo"] == "Vossa Excelência"

    def test_ve_m_crase_feminino_consistente(self) -> None:
        """DB with 'À Sua Excelência a Senhora' must sync gender-aware fields."""
        info = _info_base_feminino()
        _aplicar_tratamento_db(info, "À Sua Excelência a Senhora")
        assert info["tratamento_rodape"] == "À Sua Excelência a Senhora"
        assert info["vocativo"] == "Excelentíssima Senhora"
        assert info["pronome_corpo"] == "Vossa Excelência"

    def test_ve_sem_crase_masculino_consistente(self) -> None:
        """DB with 'A Sua Excelência o Senhor' (VE, federal) must sync all three fields."""
        info = _info_base_masculino()
        _aplicar_tratamento_db(info, "A Sua Excelência o Senhor")
        assert info["vocativo"] == "Excelentíssimo Senhor"
        assert info["pronome_corpo"] == "Vossa Excelência"

    def test_ilustrissimo_pronome_singular(self) -> None:
        """Ao Ilustríssimo Senhor must keep singular pronome."""
        info = _info_base_masculino()
        _aplicar_tratamento_db(info, "Ao Ilustríssimo Senhor")
        assert info["vocativo"] == "Ilustríssimo Senhor"
        assert info["pronome_corpo"] == "Vossa Senhoria"

    def test_ilustrissima_pronome_singular(self) -> None:
        """'À Ilustríssima Senhora' must keep singular feminine forms."""
        info = _info_base_feminino()
        _aplicar_tratamento_db(info, "À Ilustríssima Senhora")
        assert info["vocativo"] == "Ilustríssima Senhora"
        assert info["pronome_corpo"] == "Vossa Senhoria"

    def test_cuidados_pronome_plural(self) -> None:
        """'Cuidados' tratamento must produce plural vocativo and plural pronome."""
        info = _info_base_masculino()
        _aplicar_tratamento_db(info, "Aos Cuidados do Sr.")
        assert info["vocativo"] == "Ilustríssimos Senhores(as)"
        assert info["pronome_corpo"] == "Vossas Senhorias"

