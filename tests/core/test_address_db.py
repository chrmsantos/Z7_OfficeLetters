"""Tests for z7_officeletters.core.address_db."""

from __future__ import annotations

from pathlib import Path

import pytest

from z7_officeletters.core.address_db import (
    EntradaEndereco,
    buscar_endereco,
    carregar_db,
    resetar_cache,
)


# ---------------------------------------------------------------------------
# Shared raw paragraphs (mirrors a subset of the real enderecam_padrao.docx)
# ---------------------------------------------------------------------------

_PARAGRAFOS: list[str] = [
    "A Sua Excelência o Senhor",
    "LUIZ INÁCIO LULA DA SILVA",
    "Presidente da República Federativa do Brasil",
    "Praça dos Três Poderes, Palácio do Planalto",
    "CEP: 70150-900 – Brasília/DF",
    "",
    "A Sua Excelência o Senhor",
    "TARCÍSIO DE FREITAS",
    "Governador do Estado de São Paulo",
    "Palácio dos Bandeirantes",
    "Av. Morumbi, nº 4.500, Morumbi",
    "CEP: 05.650-000 – São Paulo/SP",
    "",
    "gabinetedogovernador@sp.gov.br",
    "",
    "À Sua Excelência a Senhora",
    "MARIA CRISTINA DA SILVA",
    "Secretária Municipal de Promoção Social",
    "Santa Bárbara d'Oeste/SP",
    "",
    "Aos Cuidados dos(as) Senhores(as)",
    "EDUARDO AGGIO DE SÁ – DIRETOR-PRESIDENTE",
    "NALVA BRANT – ASSESSORA",
    "Departamento Estadual de Trânsito de São Paulo – DETRAN/SP",
    "Rua Boa Vista, nº 209 – Centro Histórico de São Paulo",
    "CEP: 00114-001 – São Paulo/SP",
    "",
    "À",
    "TORCIDA INFERNO BARBARENSE",
    "Rua Izidoro Aprígio, nº 100 – Vila Tereza",
    "CEP: 13450-070 – Santa Bárbara d'Oeste/SP",
    "",
    "torcidainfernobarbarense@gmail.com",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entries() -> list[EntradaEndereco]:
    """Parse the sample paragraphs (no disk I/O)."""
    from z7_officeletters.core.address_db import _parse_entries  # noqa: PLC0415
    return _parse_entries(_PARAGRAFOS)


# ---------------------------------------------------------------------------
# _parse_entries
# ---------------------------------------------------------------------------
class TestParseEntries:

    def test_count(self) -> None:
        assert len(_entries()) == 5

    def test_tratamento_excelencia_masculino(self) -> None:
        e = _entries()[0]
        assert "Excelência" in e.tratamento
        assert "Senhor" in e.tratamento

    def test_nome_lula(self) -> None:
        assert _entries()[0].nome == "LUIZ INÁCIO LULA DA SILVA"

    def test_cargo_lula(self) -> None:
        assert "Presidente" in _entries()[0].cargo

    def test_endereco_lula(self) -> None:
        assert "Praça dos Três Poderes" in _entries()[0].endereco

    def test_email_vazio_lula(self) -> None:
        assert _entries()[0].email == ""

    def test_email_tarcisio(self) -> None:
        assert _entries()[1].email == "gabinetedogovernador@sp.gov.br"

    def test_tratamento_excelencia_feminino(self) -> None:
        e = _entries()[2]
        assert "Excelência" in e.tratamento
        assert "Senhora" in e.tratamento

    def test_tratamento_cuidados(self) -> None:
        e = _entries()[3]
        assert "Cuidados" in e.tratamento

    def test_nome_detran_entry_first_line(self) -> None:
        # First line after tratamento for the DETRAN block
        assert "EDUARDO AGGIO" in _entries()[3].nome

    def test_cargo_detran_contains_institution_name(self) -> None:
        assert "DETRAN" in _entries()[3].cargo

    def test_tratamento_a_sozinho(self) -> None:
        e = _entries()[4]
        assert e.tratamento == "À"

    def test_nome_torcida(self) -> None:
        assert _entries()[4].nome == "TORCIDA INFERNO BARBARENSE"

    def test_email_torcida(self) -> None:
        assert "torcidainfernobarbarense@gmail.com" in _entries()[4].email


# ---------------------------------------------------------------------------
# buscar_endereco (uses module-level cache with injected entries)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset() -> None:
    """Clear the global cache before each test."""
    resetar_cache()


class TestBuscarEndereco:

    def _setup(self) -> None:
        """Inject parsed sample entries directly into the module cache."""
        import z7_officeletters.core.address_db as _mod  # noqa: PLC0415
        _mod._cached_db = _entries()
        _mod._cached_path = Path("dummy")

    def test_match_por_nome_exato(self) -> None:
        self._setup()
        e = buscar_endereco("LUIZ INÁCIO LULA DA SILVA")
        assert e is not None
        assert e.nome == "LUIZ INÁCIO LULA DA SILVA"

    def test_match_case_insensitive(self) -> None:
        self._setup()
        e = buscar_endereco("luiz inácio lula da silva")
        assert e is not None

    def test_match_sem_acentos(self) -> None:
        self._setup()
        e = buscar_endereco("Tarcisio de Freitas")
        assert e is not None
        assert "TARCÍSIO" in e.nome

    def test_match_por_sigla_cargo(self) -> None:
        self._setup()
        e = buscar_endereco("DETRAN")
        assert e is not None
        assert "DETRAN" in e.cargo

    def test_match_nome_instituicao_abreviado(self) -> None:
        self._setup()
        e = buscar_endereco("DETRAN/SP")
        assert e is not None

    def test_match_torcida(self) -> None:
        self._setup()
        e = buscar_endereco("Torcida Inferno Barbarense")
        assert e is not None
        assert e.nome == "TORCIDA INFERNO BARBARENSE"

    def test_nenhum_match_nome_desconhecido(self) -> None:
        self._setup()
        e = buscar_endereco("Fulano de Tal Inexistente")
        assert e is None

    def test_nome_muito_curto_retorna_none(self) -> None:
        self._setup()
        e = buscar_endereco("SP")
        assert e is None

    def test_cache_vazio_retorna_none(self) -> None:
        # Cache is reset by autouse fixture; no path injected → empty cache
        e = buscar_endereco("TARCÍSIO DE FREITAS")
        assert e is None


# ---------------------------------------------------------------------------
# carregar_db (uses a real file when available, otherwise graceful fallback)
# ---------------------------------------------------------------------------
class TestCarregarDb:

    def test_arquivo_inexistente_retorna_lista_vazia(self) -> None:
        result = carregar_db(Path("nao_existe.docx"))
        assert result == []

    def test_arquivo_real_carregado(self) -> None:
        """Integration test — only runs when the real file is present."""
        p = Path("ender/enderecam_padrao.docx")
        if not p.exists():
            pytest.skip("enderecam_padrao.docx not found in workspace")
        entries = carregar_db(p)
        assert len(entries) > 0
        # Every entry must have at least a tratamento and a nome
        for e in entries:
            assert e.tratamento
            assert e.nome
