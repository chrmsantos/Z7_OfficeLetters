"""Tests for z7_officeletters.core.recipients."""

from __future__ import annotations

import pytest

from tests.conftest import make_dest_simples, make_dest_pj, make_dest_coletivo
from z7_officeletters.core.recipients import processar_destinatario


# =============================================================================
# processar_destinatario
# =============================================================================
class TestProcessarDestinatario:

    # --- Mayor rule ---
    def test_prefeito_por_flag(self) -> None:
        r = processar_destinatario(make_dest_simples(nome="Rafael", is_prefeito=True))
        assert r["vocativo"] == "Excelentíssimo Senhor Prefeito"
        assert r["pronome_corpo"] == "Vossa Excelência"
        assert r["envio"] == "Protocolo"
        assert r["destinatario_nome"] == "RAFAEL PIOVEZAN"

    def test_prefeito_tratamento_rodape(self) -> None:
        r = processar_destinatario(make_dest_simples(is_prefeito=True))
        assert r["tratamento_rodape"] == "À Sua Excelência o Senhor"

    def test_prefeito_por_nome(self) -> None:
        r = processar_destinatario(make_dest_simples(nome="o Prefeito Municipal"))
        assert r["pronome_corpo"] == "Vossa Excelência"

    def test_prefeito_endereco_fixo(self) -> None:
        r = processar_destinatario(make_dest_simples(is_prefeito=True))
        assert "Oeste/SP" in r["destinatario_endereco"]
        assert "Prefeito Municipal" in r["destinatario_endereco"]

    # --- Delivery method ---
    def test_envio_email_tem_prioridade_sobre_endereco(self) -> None:
        r = processar_destinatario(make_dest_simples(endereco="Rua X", email="x@y.com"))
        assert r["envio"] == "E-mail"

    def test_envio_carta_sem_email(self) -> None:
        r = processar_destinatario(make_dest_simples(endereco="Rua X"))
        assert r["envio"] == "Carta"

    def test_envio_em_maos_sem_contato(self) -> None:
        r = processar_destinatario(make_dest_simples())
        assert r["envio"] == "Em Mãos"

    # --- Formatting ---
    def test_nome_em_maiusculas(self) -> None:
        r = processar_destinatario(make_dest_simples(nome="João Silva"))
        assert r["destinatario_nome"] == "JOÃO SILVA"

    def test_pessoa_fisica_masculino_tratamento(self) -> None:
        r = processar_destinatario(make_dest_simples(genero="M"))
        assert r["tratamento_rodape"] == "Ao Ilustríssimo Senhor"

    def test_pessoa_fisica_feminino_tratamento(self) -> None:
        r = processar_destinatario(make_dest_simples(genero="F"))
        assert r["tratamento_rodape"] == "À Ilustríssima Senhora"

    def test_pronome_pessoa_fisica(self) -> None:
        r = processar_destinatario(make_dest_simples())
        assert r["pronome_corpo"] == "Vossa Senhoria"

    def test_instituicao_tratamento_ao(self) -> None:
        r = processar_destinatario(
            make_dest_simples(nome="Câmara Municipal", is_instituicao=True)
        )
        assert r["tratamento_rodape"] == "Ao"

    def test_instituicao_comeca_com_a_usa_crase(self) -> None:
        r = processar_destinatario(
            make_dest_simples(nome="ABCD Fundação", is_instituicao=True)
        )
        assert r["tratamento_rodape"] == "À"

    def test_instituicao_pronome_plural(self) -> None:
        r = processar_destinatario(
            make_dest_simples(nome="Câmara Municipal", is_instituicao=True)
        )
        assert r["pronome_corpo"] == "Vossas Senhorias"

    def test_instituicao_masculina_vocativo(self) -> None:
        r = processar_destinatario(
            make_dest_simples(nome="Câmara Municipal", is_instituicao=True, genero="M")
        )
        assert r["vocativo"] == "Ilustríssimos Senhores"

    def test_instituicao_feminina_vocativo(self) -> None:
        r = processar_destinatario(
            make_dest_simples(nome="Associação das Mães", is_instituicao=True, genero="F")
        )
        assert r["vocativo"] == "Ilustríssimas Senhoras"

    def test_pessoa_fisica_masculino_vocativo(self) -> None:
        r = processar_destinatario(make_dest_simples(genero="M"))
        assert r["vocativo"] == "Ilustríssimo Senhor"

    def test_pessoa_fisica_feminino_vocativo(self) -> None:
        r = processar_destinatario(make_dest_simples(nome="Maria Silva", genero="F"))
        assert r["vocativo"] == "Ilustríssima Senhora"

    def test_endereco_concatena_cargo_e_logradouro(self) -> None:
        r = processar_destinatario(make_dest_simples(
            cargo_ou_tratamento="Secretário de Saúde",
            endereco="Av. das Flores, 100",
        ))
        assert "Secretário de Saúde" in r["destinatario_endereco"]
        assert "Av. das Flores, 100" in r["destinatario_endereco"]

    def test_endereco_inclui_email(self) -> None:
        r = processar_destinatario(
            make_dest_simples(cargo_ou_tratamento="Diretor", email="d@e.com")
        )
        assert "d@e.com" in r["destinatario_endereco"]

    def test_honorifico_barra_cargo_remove_honorifico(self) -> None:
        r = processar_destinatario(
            make_dest_simples(cargo_ou_tratamento="Sr. / Ex-servidor")
        )
        assert r["destinatario_endereco"] == "Ex-servidor"

    def test_honorifico_barra_cargo_variante_sem_ponto(self) -> None:
        r = processar_destinatario(
            make_dest_simples(cargo_ou_tratamento="Sr / Diretor Geral")
        )
        assert r["destinatario_endereco"] == "Diretor Geral"

    def test_pf_funcao_profissao_incluida_no_endereco(self) -> None:
        r = processar_destinatario(
            make_dest_simples(funcao_profissao="Médico Cardiologista")
        )
        assert "Médico Cardiologista" in r["destinatario_endereco"]

    def test_pf_funcao_profissao_tem_prioridade_sobre_cargo_ou_tratamento(self) -> None:
        r = processar_destinatario(
            make_dest_simples(funcao_profissao="Engenheiro", cargo_ou_tratamento="Velho Campo")
        )
        assert "Engenheiro" in r["destinatario_endereco"]


class TestNivelProtocolo:

    # --- VE: federal/state, no crase ---
    def test_ve_masculino_tratamento(self) -> None:
        r = processar_destinatario(make_dest_simples(nivel_protocolo="VE", genero="M"))
        assert r["tratamento_rodape"] == "A Sua Excelência o Senhor"

    def test_ve_feminino_tratamento(self) -> None:
        r = processar_destinatario(make_dest_simples(nivel_protocolo="VE", genero="F"))
        assert r["tratamento_rodape"] == "A Sua Excelência a Senhora"

    def test_ve_vocativo_masculino(self) -> None:
        r = processar_destinatario(make_dest_simples(nivel_protocolo="VE", genero="M"))
        assert r["vocativo"] == "Excelentíssimo Senhor"

    def test_ve_vocativo_feminino(self) -> None:
        r = processar_destinatario(make_dest_simples(nivel_protocolo="VE", genero="F"))
        assert r["vocativo"] == "Excelentíssima Senhora"

    def test_ve_pronome_corpo(self) -> None:
        r = processar_destinatario(make_dest_simples(nivel_protocolo="VE"))
        assert r["pronome_corpo"] == "Vossa Excelência"

    # --- VE_M: municipal, with crase ---
    def test_ve_m_masculino_tratamento(self) -> None:
        r = processar_destinatario(make_dest_simples(nivel_protocolo="VE_M", genero="M"))
        assert r["tratamento_rodape"] == "À Sua Excelência o Senhor"

    def test_ve_m_feminino_tratamento(self) -> None:
        r = processar_destinatario(make_dest_simples(nivel_protocolo="VE_M", genero="F"))
        assert r["tratamento_rodape"] == "À Sua Excelência a Senhora"

    def test_ve_m_pronome_corpo(self) -> None:
        r = processar_destinatario(make_dest_simples(nivel_protocolo="VE_M"))
        assert r["pronome_corpo"] == "Vossa Excelência"

    # --- VE vs VE_M distinction ---
    def test_ve_nao_usa_crase(self) -> None:
        r = processar_destinatario(make_dest_simples(nivel_protocolo="VE"))
        assert not r["tratamento_rodape"].startswith("À")

    def test_ve_m_usa_crase(self) -> None:
        r = processar_destinatario(make_dest_simples(nivel_protocolo="VE_M"))
        assert r["tratamento_rodape"].startswith("À")

    # --- Realistic examples from the letter format ---
    def test_ministro_federal(self) -> None:
        r = processar_destinatario(make_dest_simples(
            nome="Wellington Dias",
            nivel_protocolo="VE",
            funcao_profissao="Ministro de Estado de Desenvolvimento e Assistência Social",
            endereco="Esplanada dos Ministérios - Bloco A",
            email="ministro@mds.gov.br",
        ))
        assert r["tratamento_rodape"] == "A Sua Excelência o Senhor"
        assert r["pronome_corpo"] == "Vossa Excelência"
        assert "Ministro de Estado" in r["destinatario_endereco"]
        assert r["envio"] == "E-mail"

    def test_secretaria_municipal_excelencia(self) -> None:
        r = processar_destinatario(make_dest_simples(
            nome="Maria Cristina da Silva",
            nivel_protocolo="VE_M",
            funcao_profissao="Secretária Municipal de Promoção Social",
            genero="F",
        ))
        assert r["tratamento_rodape"] == "À Sua Excelência a Senhora"
        assert r["vocativo"] == "Excelentíssima Senhora"

    def test_secretario_municipal_vs(self) -> None:
        r = processar_destinatario(make_dest_simples(
            nome="Marcus Pensuti",
            funcao_profissao="Secretário Municipal de Saúde",
            genero="M",
        ))
        assert r["tratamento_rodape"] == "Ao Ilustríssimo Senhor"
        assert r["pronome_corpo"] == "Vossa Senhoria"


class TestProcessarDestinatarioPJ:

    def test_pj_tratamento_ao(self) -> None:
        r = processar_destinatario(make_dest_pj(nome="Câmara Municipal"))
        assert r["tratamento_rodape"] == "Ao"

    def test_pj_comeca_com_a_usa_crase(self) -> None:
        r = processar_destinatario(make_dest_pj(nome="Associação dos Moradores"))
        assert r["tratamento_rodape"] == "À"

    def test_pj_pronome_plural(self) -> None:
        r = processar_destinatario(make_dest_pj())
        assert r["pronome_corpo"] == "Vossas Senhorias"

    def test_pj_vocativo_masculino(self) -> None:
        r = processar_destinatario(make_dest_pj(genero="M"))
        assert r["vocativo"] == "Ilustríssimos Senhores"

    def test_pj_vocativo_feminino(self) -> None:
        r = processar_destinatario(make_dest_pj(genero="F"))
        assert r["vocativo"] == "Ilustríssimas Senhoras"

    def test_pj_objeto_atividade_incluido_no_endereco(self) -> None:
        r = processar_destinatario(
            make_dest_pj(objeto_atividade="Departamento de Obras")
        )
        assert "Departamento de Obras" in r["destinatario_endereco"]

    def test_pj_representante_sem_funcao(self) -> None:
        r = processar_destinatario(
            make_dest_pj(representante="Carlos Souza")
        )
        assert "Carlos Souza" in r["destinatario_endereco"]

    def test_pj_representante_com_funcao(self) -> None:
        r = processar_destinatario(
            make_dest_pj(representante="Carlos Souza", funcao_representante="Diretor Geral")
        )
        assert "Diretor Geral: Carlos Souza" in r["destinatario_endereco"]

    def test_pj_objeto_antes_de_representante(self) -> None:
        r = processar_destinatario(make_dest_pj(
            objeto_atividade="Setor Jurídico",
            representante="Ana Lima",
            funcao_representante="Procuradora",
        ))
        linhas = r["destinatario_endereco"].split("\n")
        assert linhas[0] == "Setor Jurídico"
        assert "Procuradora: Ana Lima" in linhas[1]

    def test_pj_endereco_e_email_apos_representante(self) -> None:
        r = processar_destinatario(make_dest_pj(
            representante="Ana Lima",
            endereco="Rua das Flores, 10",
            email="ana@pj.com",
        ))
        linhas = r["destinatario_endereco"].split("\n")
        assert "Ana Lima" in linhas[0]
        assert linhas[1] == "Rua das Flores, 10"
        assert linhas[2] == "ana@pj.com"

    def test_pj_envio_email(self) -> None:
        r = processar_destinatario(make_dest_pj(email="x@empresa.com"))
        assert r["envio"] == "E-mail"

    def test_pj_envio_carta(self) -> None:
        r = processar_destinatario(make_dest_pj(endereco="Av. Brasil, 200"))
        assert r["envio"] == "Carta"

    def test_pj_sem_contato_envio_em_maos(self) -> None:
        r = processar_destinatario(make_dest_pj())
        assert r["envio"] == "Em Mãos"

    def test_pj_nome_em_maiusculas(self) -> None:
        r = processar_destinatario(make_dest_pj(nome="Empresa Modelo"))
        assert r["destinatario_nome"] == "EMPRESA MODELO"


class TestProcessarDestinatarioColetivo:

    def test_coletivo_tratamento_ao(self) -> None:
        r = processar_destinatario(make_dest_coletivo(nome="Conselho Tutelar"))
        assert r["tratamento_rodape"] == "Ao"

    def test_coletivo_comeca_com_a_usa_crase(self) -> None:
        r = processar_destinatario(make_dest_coletivo(nome="Associação Recreativa"))
        assert r["tratamento_rodape"] == "À"

    def test_coletivo_pronome_plural(self) -> None:
        r = processar_destinatario(make_dest_coletivo())
        assert r["pronome_corpo"] == "Vossas Senhorias"

    def test_coletivo_representante_com_funcao(self) -> None:
        r = processar_destinatario(make_dest_coletivo(
            representante="Pedro Alves",
            funcao_representante="Presidente",
        ))
        assert "Presidente: Pedro Alves" in r["destinatario_endereco"]

    def test_coletivo_objeto_atividade_no_endereco(self) -> None:
        r = processar_destinatario(
            make_dest_coletivo(objeto_atividade="Torcida Organizada")
        )
        assert "Torcida Organizada" in r["destinatario_endereco"]


# =============================================================================
# Consistency: tratamento_rodape, vocativo, and pronome_corpo must always match
# =============================================================================
class TestConsistenciaPronomes:
    """Invariant: the three pronome fields must always be mutually consistent."""

    # PF — nivel_protocolo VE (federal/state)
    @pytest.mark.parametrize("genero,exp_tratamento,exp_vocativo", [
        ("M", "A Sua Excelência o Senhor", "Excelentíssimo Senhor"),
        ("F", "A Sua Excelência a Senhora", "Excelentíssima Senhora"),
    ])
    def test_ve_campos_consistentes(self, genero: str, exp_tratamento: str, exp_vocativo: str) -> None:
        r = processar_destinatario(make_dest_simples(nivel_protocolo="VE", genero=genero))
        assert r["tratamento_rodape"] == exp_tratamento
        assert r["vocativo"] == exp_vocativo
        assert r["pronome_corpo"] == "Vossa Excelência"

    # PF — nivel_protocolo VE_M (municipal)
    @pytest.mark.parametrize("genero,exp_tratamento,exp_vocativo", [
        ("M", "À Sua Excelência o Senhor", "Excelentíssimo Senhor"),
        ("F", "À Sua Excelência a Senhora", "Excelentíssima Senhora"),
    ])
    def test_ve_m_campos_consistentes(self, genero: str, exp_tratamento: str, exp_vocativo: str) -> None:
        r = processar_destinatario(make_dest_simples(nivel_protocolo="VE_M", genero=genero))
        assert r["tratamento_rodape"] == exp_tratamento
        assert r["vocativo"] == exp_vocativo
        assert r["pronome_corpo"] == "Vossa Excelência"

    # PF — default VS
    @pytest.mark.parametrize("genero,exp_tratamento,exp_vocativo", [
        ("M", "Ao Ilustríssimo Senhor", "Ilustríssimo Senhor"),
        ("F", "À Ilustríssima Senhora", "Ilustríssima Senhora"),
    ])
    def test_vs_campos_consistentes(self, genero: str, exp_tratamento: str, exp_vocativo: str) -> None:
        r = processar_destinatario(make_dest_simples(genero=genero))
        assert r["tratamento_rodape"] == exp_tratamento
        assert r["vocativo"] == exp_vocativo
        assert r["pronome_corpo"] == "Vossa Senhoria"

    # Prefeito
    def test_prefeito_campos_consistentes(self) -> None:
        r = processar_destinatario(make_dest_simples(is_prefeito=True))
        assert r["tratamento_rodape"] == "À Sua Excelência o Senhor"
        assert "Excelentíssimo" in r["vocativo"]
        assert r["pronome_corpo"] == "Vossa Excelência"

    # PJ
    @pytest.mark.parametrize("genero,exp_vocativo", [
        ("M", "Ilustríssimos Senhores"),
        ("F", "Ilustríssimas Senhoras"),
    ])
    def test_pj_campos_consistentes(self, genero: str, exp_vocativo: str) -> None:
        r = processar_destinatario(make_dest_pj(genero=genero))
        assert r["vocativo"] == exp_vocativo
        assert r["pronome_corpo"] == "Vossas Senhorias"

    # Coletivo
    @pytest.mark.parametrize("genero,exp_vocativo", [
        ("M", "Ilustríssimos Senhores"),
        ("F", "Ilustríssimas Senhoras"),
    ])
    def test_coletivo_campos_consistentes(self, genero: str, exp_vocativo: str) -> None:
        r = processar_destinatario(make_dest_coletivo(genero=genero))
        assert r["vocativo"] == exp_vocativo
        assert r["pronome_corpo"] == "Vossas Senhorias"

    # VE must NOT use crase; VE_M must use crase
    def test_ve_nao_tem_crase_ve_m_tem_crase(self) -> None:
        ve = processar_destinatario(make_dest_simples(nivel_protocolo="VE"))
        ve_m = processar_destinatario(make_dest_simples(nivel_protocolo="VE_M"))
        assert not ve["tratamento_rodape"].startswith("À")
        assert ve_m["tratamento_rodape"].startswith("À")


