"""Tests for z7_officeletters.core.authors."""

from __future__ import annotations

import pytest

from z7_officeletters.core.authors import formatar_autores, sigla_autor


# =============================================================================
# formatar_autores
# =============================================================================
class TestFormatarAutores:

    def test_autor_unico_texto(self) -> None:
        texto, _ = formatar_autores(["Alex Dantas"])
        assert texto == "do vereador Alex Dantas"

    def test_autor_unico_sigla_conhecida(self) -> None:
        _, sigla = formatar_autores(["Alex Dantas"])
        assert sigla == "ad"

    def test_autor_desconhecido_sigla_indef(self) -> None:
        _, sigla = formatar_autores(["Vereador Fantasma"])
        assert sigla == "indef"

    def test_dois_autores_texto_plural(self) -> None:
        texto, _ = formatar_autores(["Alex Dantas", "Arnaldo Alves"])
        assert "dos vereadores" in texto

    def test_dois_autores_sigla(self) -> None:
        _, sigla = formatar_autores(["Alex Dantas", "Arnaldo Alves"])
        assert sigla == "ad e outros"

    def test_tres_autores_sigla(self) -> None:
        _, sigla = formatar_autores(["Alex Dantas", "Arnaldo Alves", "Cabo Dorigon"])
        assert sigla == "ad e outros"

    def test_tres_autores_usa_e_no_final(self) -> None:
        texto, _ = formatar_autores(["Alex Dantas", "Arnaldo Alves", "Cabo Dorigon"])
        assert " e " in texto

    def test_busca_sigla_case_insensitive(self) -> None:
        _, sigla = formatar_autores(["alex dantas"])
        assert sigla == "ad"

    def test_autor_com_acento_no_mapa(self) -> None:
        _, sigla = formatar_autores(["Celso Ávila"])
        assert sigla == "clab"

    def test_mistura_conhecido_desconhecido(self) -> None:
        _, sigla = formatar_autores(["Alex Dantas", "Vereador X"])
        assert sigla == "ad e outros"

    def test_desconhecido_primeiro_usa_sigla_do_segundo(self) -> None:
        _, sigla = formatar_autores(["Vereador X", "Alex Dantas"])
        assert sigla == "ad e outros"

    def test_todos_desconhecidos_sigla_indef(self) -> None:
        _, sigla = formatar_autores(["Vereador X", "Vereador Y"])
        assert sigla == "indef e outros"

    def test_nome_sem_acento_resolve_sigla(self) -> None:
        _, sigla = formatar_autores(["Jose Luis Fornasari"])
        assert sigla == "jlf"

    def test_nome_sem_acento_resolve_casing_canonico(self) -> None:
        texto, _ = formatar_autores(["Jose Luis Fornasari"])
        assert "José Luis Fornasari" in texto

    def test_vereadora_unica_texto(self) -> None:
        texto, _ = formatar_autores(["Esther Moraes"])
        assert texto == "da vereadora Esther Moraes"

    def test_vereadora_unica_sigla(self) -> None:
        _, sigla = formatar_autores(["Esther Moraes"])
        assert sigla == "egsbm"

    def test_todas_vereadoras_plural(self) -> None:
        texto, _ = formatar_autores(["Esther Moraes", "Esther Moraes"])
        assert texto.startswith("das vereadoras")

    def test_misto_masculino_feminino_usa_masculino_plural(self) -> None:
        texto, _ = formatar_autores(["Alex Dantas", "Esther Moraes"])
        assert texto.startswith("dos vereadores")

    def test_vereadora_case_insensitive(self) -> None:
        texto, _ = formatar_autores(["esther moraes"])
        assert texto == "da vereadora Esther Moraes"


# =============================================================================
# sigla_autor
# =============================================================================
class TestSiglaAutor:

    def test_nome_canonico_resolve(self) -> None:
        assert sigla_autor("Alex Dantas") == "ad"

    def test_nome_minusculo_resolve(self) -> None:
        assert sigla_autor("alex dantas") == "ad"

    def test_desconhecido_retorna_indef(self) -> None:
        assert sigla_autor("Vereador Fantasma") == "indef"

    def test_fornasari_sem_acento_no_luis(self) -> None:
        # AI às vezes retorna sem o acento em "é": "Jose Luis Fornasari"
        assert sigla_autor("Jose Luis Fornasari") == "jlf"

    def test_fornasari_com_acento_em_luis(self) -> None:
        # AI pode retornar com acento em "í": "José Luís Fornasari"
        assert sigla_autor("José Luís Fornasari") == "jlf"

    def test_fornasari_apelido_joi(self) -> None:
        assert sigla_autor("JOI FORNASARI") == "jlf"
