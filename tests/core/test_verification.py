"""Tests for z7_officeletters.core.verification."""

from __future__ import annotations

import queue
from typing import Any

import pytest

from z7_officeletters.core.verification import (
    RegistroOficio,
    RelatorioConferencia,
    ResultadoVerificacao,
    _corrigir_linha_planilha,
    _formatar_lista_pt,
    _frases_propositura,
    _verificar_consistencia_pronomes,
    _verificar_numero,
    corrigir_ctx,
    verificar_concordancia_linguistica,
    verificar_consistencia_dados,
    verificar_linha_planilha,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _ctx_mocao(
    num_oficio: str = "001",
    tipo_mocao: str = "Aplauso",
    num_mocao: str = "124",
    vocativo: str = "Ilustríssimo Senhor",
    pronome_corpo: str = "Vossa Senhoria",
    tratamento_rodape: str = "Ao Ilustríssimo Senhor",
    destinatario_nome: str = "FULANO DE TAL",
    destinatario_endereco: str = "",
    designacao_propositura: str = "Moção de Aplauso",
    copia_art: str = "cópia da",
    aprovada_s: str = "aprovada",
    tipo_propositura: str = "mocao",
    **extra: str,
) -> dict[str, str]:
    ctx: dict[str, str] = {
        "num_oficio": num_oficio,
        "NUM_OFICIO": num_oficio,
        "tipo_mocao": tipo_mocao,
        "TIPO_MOCAO": tipo_mocao,
        "num_mocao": num_mocao,
        "NUM_MOCAO": num_mocao,
        "vocativo": vocativo,
        "VOCATIVO": vocativo,
        "pronome_corpo": pronome_corpo,
        "PRONOME_CORPO": pronome_corpo,
        "tratamento_rodape": tratamento_rodape,
        "TRATAMENTO_RODAPE": tratamento_rodape,
        "destinatario_nome": destinatario_nome,
        "DESTINATARIO_NOME": destinatario_nome,
        "destinatario_endereco": destinatario_endereco,
        "DESTINATARIO_ENDERECO": destinatario_endereco,
        "designacao_propositura": designacao_propositura,
        "DESIGNACAO_PROPOSITURA": designacao_propositura,
        "copia_art": copia_art,
        "COPIA_ART": copia_art,
        "aprovada_s": aprovada_s,
        "APROVADA_S": aprovada_s,
        "tipo_propositura": tipo_propositura,
        "TIPO_PROPOSITURA": tipo_propositura,
        "falecido": "",
        "FALECIDO": "",
    }
    ctx.update(extra)
    return ctx


def _dados_mocao(
    tipo: str = "Aplauso", numero: str = "124"
) -> dict[str, Any]:
    return {
        "tipo_mocao": tipo,
        "numero_mocao": numero,
        "autores": ["Alex Dantas"],
        "destinatarios": [{"nome": "Fulano de Tal"}],
    }


def _dados_pesar(numero: str = "45", falecido: str = "João Silva") -> dict[str, Any]:
    return {
        "numero_mocao": numero,
        "falecido": falecido,
        "autores": ["Alex Dantas"],
        "destinatarios": [{"nome": "Família"}],
    }


def _info_padrao(
    vocativo: str = "Ilustríssimo Senhor",
    pronome_corpo: str = "Vossa Senhoria",
    tratamento_rodape: str = "Ao Ilustríssimo Senhor",
    destinatario_nome: str = "FULANO DE TAL",
    destinatario_endereco: str = "",
    envio: str = "Em Mãos",
) -> dict[str, str]:
    return {
        "vocativo": vocativo,
        "pronome_corpo": pronome_corpo,
        "tratamento_rodape": tratamento_rodape,
        "destinatario_nome": destinatario_nome,
        "destinatario_endereco": destinatario_endereco,
        "envio": envio,
    }


def _dest_raw(
    tipo: str = "PF",
    nome: str = "Fulano de Tal",
    genero: str = "M",
    nivel_protocolo: str = "",
    is_prefeito: bool = False,
    is_instituicao: bool = False,
) -> dict[str, Any]:
    d: dict[str, Any] = {
        "tipo": tipo,
        "nome": nome,
        "genero": genero,
        "is_prefeito": is_prefeito,
        "is_instituicao": is_instituicao,
    }
    if nivel_protocolo:
        d["nivel_protocolo"] = nivel_protocolo
    return d


def _registro(
    *,
    ctx: dict[str, str] | None = None,
    dados_grupo: list[dict[str, Any]] | None = None,
    dest_raw: dict[str, Any] | None = None,
    info: dict[str, str] | None = None,
    n_props: int = 1,
    tipo_propositura: str = "mocao",
    nome_arquivo: str = "Of. 001 - test.docx",
    caminho: str = "/tmp/test/Of. 001 - test.docx",
    template_path: str = "/tmp/modelo_mocao.docx",
    linha_planilha_idx: int = 0,
) -> RegistroOficio:
    return RegistroOficio(
        caminho=caminho,
        nome_arquivo=nome_arquivo,
        ctx=ctx or _ctx_mocao(),
        dados_grupo=dados_grupo or [_dados_mocao()],
        dest_raw=dest_raw or _dest_raw(),
        info=info or _info_padrao(),
        n_props=n_props,
        tipo_propositura=tipo_propositura,
        template_path=template_path,
        linha_planilha_idx=linha_planilha_idx,
    )


def _linha_padrao(
    num_oficio: str = "001",
    data_iso: str = "2026-05-15",
    destinatario: str = "Ao Ilustríssimo Senhor FULANO DE TAL",
    assunto: str = "Encaminha Moção de Aplauso nº 124/2026",
    vereadores: str = "Alex Dantas (ad)",
    envio: str = "Em Mãos",
    sigla: str = "ajc",
) -> list[Any]:
    return [num_oficio, data_iso, destinatario, assunto, vereadores, envio, sigla]


# ---------------------------------------------------------------------------
# _formatar_lista_pt
# ---------------------------------------------------------------------------
class TestFormatarListaPt:
    def test_unico(self) -> None:
        assert _formatar_lista_pt(["a"]) == "a"

    def test_dois(self) -> None:
        assert _formatar_lista_pt(["a", "b"]) == "a e b"

    def test_tres(self) -> None:
        assert _formatar_lista_pt(["a", "b", "c"]) == "a, b e c"

    def test_deduplica(self) -> None:
        assert _formatar_lista_pt(["a", "a", "b"]) == "a e b"

    def test_preserva_ordem(self) -> None:
        assert _formatar_lista_pt(["b", "a"]) == "b e a"


# ---------------------------------------------------------------------------
# _frases_propositura
# ---------------------------------------------------------------------------
class TestFrasesPropositura:
    def test_mocao_singular(self) -> None:
        desig, art, aprov = _frases_propositura("mocao", "Aplauso", 1)
        assert desig == "Moção de Aplauso"
        assert art == "cópia da"
        assert aprov == "aprovada"

    def test_mocao_plural(self) -> None:
        desig, art, aprov = _frases_propositura("mocao", "Aplauso", 2)
        assert desig == "Moções de Aplauso"
        assert art == "cópias das"
        assert aprov == "aprovadas"

    def test_pesar_singular(self) -> None:
        desig, art, aprov = _frases_propositura("requerimento_pesar", "", 1)
        assert desig == "Requerimento de Pesar"
        assert art == "cópia do"
        assert aprov == "aprovado"

    def test_pesar_plural(self) -> None:
        desig, art, aprov = _frases_propositura("requerimento_pesar", "", 3)
        assert desig == "Requerimentos de Pesar"
        assert art == "cópias dos"
        assert aprov == "aprovados"


# ---------------------------------------------------------------------------
# verificar_consistencia_dados
# ---------------------------------------------------------------------------
class TestVerificarConsistenciaDados:
    def test_sem_erros_mocao(self) -> None:
        reg = _registro()
        assert verificar_consistencia_dados(reg) == []

    def test_num_mocao_incorreto(self) -> None:
        reg = _registro(
            ctx=_ctx_mocao(num_mocao="999"),
            dados_grupo=[_dados_mocao(numero="124")],
        )
        erros = verificar_consistencia_dados(reg)
        assert any("num_mocao" in e for e in erros)

    def test_tipo_mocao_incorreto(self) -> None:
        reg = _registro(
            ctx=_ctx_mocao(tipo_mocao="Apelo"),
            dados_grupo=[_dados_mocao(tipo="Aplauso")],
        )
        erros = verificar_consistencia_dados(reg)
        assert any("tipo_mocao" in e for e in erros)

    def test_tipo_propositura_incorreto(self) -> None:
        ctx = _ctx_mocao(tipo_propositura="requerimento_pesar")
        reg = _registro(ctx=ctx, tipo_propositura="mocao")
        erros = verificar_consistencia_dados(reg)
        assert any("tipo_propositura" in e for e in erros)

    def test_merge_multiplas_mocoes(self) -> None:
        dados = [_dados_mocao(numero="124"), _dados_mocao(numero="125")]
        ctx = _ctx_mocao(num_mocao="124 e 125")
        reg = _registro(ctx=ctx, dados_grupo=dados, n_props=2)
        assert verificar_consistencia_dados(reg) == []

    def test_falecido_incorreto_requerimento(self) -> None:
        dados = [_dados_pesar(falecido="Maria Silva")]
        ctx_pesar = _ctx_mocao(tipo_propositura="requerimento_pesar")
        ctx_pesar["falecido"] = "João Silva"
        ctx_pesar["FALECIDO"] = "João Silva"
        reg = _registro(
            ctx=ctx_pesar,
            dados_grupo=dados,
            tipo_propositura="requerimento_pesar",
        )
        erros = verificar_consistencia_dados(reg)
        assert any("falecido" in e for e in erros)


# ---------------------------------------------------------------------------
# _verificar_consistencia_pronomes
# ---------------------------------------------------------------------------
class TestVerificarConsistenciaPronomes:
    def test_excelentissimo_vossa_excelencia(self) -> None:
        erros: list[str] = []
        _verificar_consistencia_pronomes(
            erros, "Excelentíssimo Senhor", "Vossa Excelência", "À Sua Excelência o Senhor"
        )
        assert erros == []

    def test_excelentissimo_pronome_errado(self) -> None:
        erros: list[str] = []
        _verificar_consistencia_pronomes(
            erros, "Excelentíssimo Senhor", "Vossa Senhoria", ""
        )
        assert any("Vossa Excelência" in e for e in erros)

    def test_ilustrissimo_vossa_senhoria(self) -> None:
        erros: list[str] = []
        _verificar_consistencia_pronomes(
            erros, "Ilustríssimo Senhor", "Vossa Senhoria", "Ao Ilustríssimo Senhor"
        )
        assert erros == []

    def test_ilustrissimo_pronome_errado(self) -> None:
        erros: list[str] = []
        _verificar_consistencia_pronomes(
            erros, "Ilustríssimo Senhor", "Vossa Excelência", ""
        )
        assert any("Vossa Senhoria" in e for e in erros)

    def test_plural_vossas_senhorias(self) -> None:
        erros: list[str] = []
        _verificar_consistencia_pronomes(
            erros, "Ilustríssimos Senhores", "Vossas Senhorias", "Ao"
        )
        assert erros == []

    def test_plural_pronome_errado(self) -> None:
        erros: list[str] = []
        _verificar_consistencia_pronomes(
            erros, "Ilustríssimos Senhores", "Vossa Senhoria", ""
        )
        assert any("Vossas Senhorias" in e for e in erros)

    def test_consistencia_genero_vocativo_tratamento_divergente(self) -> None:
        erros: list[str] = []
        _verificar_consistencia_pronomes(
            erros, "Ilustríssima Senhora", "Vossa Senhoria", "Ao Ilustríssimo Senhor"
        )
        assert any("masculina" in e or "feminina" in e or "feminino" in e for e in erros)


# ---------------------------------------------------------------------------
# _verificar_numero
# ---------------------------------------------------------------------------
class TestVerificarNumero:
    def test_singular_correto(self) -> None:
        erros: list[str] = []
        ctx = _ctx_mocao(
            designacao_propositura="Moção de Aplauso",
            copia_art="cópia da",
            aprovada_s="aprovada",
        )
        _verificar_numero(erros, ctx, "mocao", "Aplauso", 1)
        assert erros == []

    def test_plural_correto(self) -> None:
        erros: list[str] = []
        ctx = _ctx_mocao(
            designacao_propositura="Moções de Aplauso",
            copia_art="cópias das",
            aprovada_s="aprovadas",
        )
        _verificar_numero(erros, ctx, "mocao", "Aplauso", 2)
        assert erros == []

    def test_singular_quando_plural_esperado(self) -> None:
        erros: list[str] = []
        ctx = _ctx_mocao(
            designacao_propositura="Moção de Aplauso",
            copia_art="cópia da",
            aprovada_s="aprovada",
        )
        _verificar_numero(erros, ctx, "mocao", "Aplauso", 2)
        assert len(erros) == 3  # designacao + copia_art + aprovada_s

    def test_pesar_plural_correto(self) -> None:
        erros: list[str] = []
        ctx = _ctx_mocao(
            tipo_propositura="requerimento_pesar",
            designacao_propositura="Requerimentos de Pesar",
            copia_art="cópias dos",
            aprovada_s="aprovados",
        )
        _verificar_numero(erros, ctx, "requerimento_pesar", "", 2)
        assert erros == []


# ---------------------------------------------------------------------------
# verificar_concordancia_linguistica
# ---------------------------------------------------------------------------
class TestVerificarConcordanciaLinguistica:
    def test_mocao_pf_masculino_vs_sem_erros(self) -> None:
        reg = _registro(
            ctx=_ctx_mocao(
                vocativo="Ilustríssimo Senhor",
                pronome_corpo="Vossa Senhoria",
                tratamento_rodape="Ao Ilustríssimo Senhor",
            ),
            dest_raw=_dest_raw(genero="M"),
        )
        assert verificar_concordancia_linguistica(reg) == []

    def test_mocao_pf_feminino_vs_sem_erros(self) -> None:
        reg = _registro(
            ctx=_ctx_mocao(
                vocativo="Ilustríssima Senhora",
                pronome_corpo="Vossa Senhoria",
                tratamento_rodape="À Ilustríssima Senhora",
            ),
            dest_raw=_dest_raw(genero="F"),
        )
        assert verificar_concordancia_linguistica(reg) == []

    def test_mocao_pf_feminino_vocativo_masculino(self) -> None:
        reg = _registro(
            ctx=_ctx_mocao(
                vocativo="Ilustríssimo Senhor",
                pronome_corpo="Vossa Senhoria",
                tratamento_rodape="Ao Ilustríssimo Senhor",
            ),
            dest_raw=_dest_raw(genero="F"),
        )
        erros = verificar_concordancia_linguistica(reg)
        assert any("masculina" in e or "masculino" in e for e in erros)

    def test_pf_ve_municipal_sem_crase(self) -> None:
        reg = _registro(
            ctx=_ctx_mocao(
                vocativo="Excelentíssimo Senhor",
                pronome_corpo="Vossa Excelência",
                tratamento_rodape="A Sua Excelência o Senhor",  # missing crase — VE_M should have it
            ),
            dest_raw=_dest_raw(genero="M", nivel_protocolo="VE_M"),
        )
        erros = verificar_concordancia_linguistica(reg)
        assert any("VE_M" in e or "crase" in e for e in erros)

    def test_pf_ve_federal_com_crase_errada(self) -> None:
        reg = _registro(
            ctx=_ctx_mocao(
                vocativo="Excelentíssimo Senhor",
                pronome_corpo="Vossa Excelência",
                tratamento_rodape="À Sua Excelência o Senhor",  # has crase — VE should not
            ),
            dest_raw=_dest_raw(genero="M", nivel_protocolo="VE"),
        )
        erros = verificar_concordancia_linguistica(reg)
        assert any("VE" in e or "crase" in e for e in erros)

    def test_instituicao_pronome_errado(self) -> None:
        reg = _registro(
            ctx=_ctx_mocao(
                vocativo="Ilustríssimos Senhores",
                pronome_corpo="Vossa Senhoria",  # wrong — should be Vossas Senhorias
                tratamento_rodape="Ao",
            ),
            dest_raw=_dest_raw(tipo="PJ"),
        )
        erros = verificar_concordancia_linguistica(reg)
        assert any("Vossas Senhorias" in e for e in erros)

    def test_requerimento_pesar_formas_fixas_corretas(self) -> None:
        ctx = _ctx_mocao(
            tipo_propositura="requerimento_pesar",
            vocativo="Ilustríssimos Senhores(as)",
            pronome_corpo="Vossas Senhorias",
            designacao_propositura="Requerimento de Pesar",
            copia_art="cópia do",
            aprovada_s="aprovado",
        )
        reg = _registro(ctx=ctx, tipo_propositura="requerimento_pesar")
        assert verificar_concordancia_linguistica(reg) == []

    def test_requerimento_pesar_vocativo_errado(self) -> None:
        ctx = _ctx_mocao(
            tipo_propositura="requerimento_pesar",
            vocativo="Ilustríssimo Senhor",  # wrong — fixed form expected
            pronome_corpo="Vossas Senhorias",
            designacao_propositura="Requerimento de Pesar",
            copia_art="cópia do",
            aprovada_s="aprovado",
        )
        reg = _registro(ctx=ctx, tipo_propositura="requerimento_pesar")
        erros = verificar_concordancia_linguistica(reg)
        assert any("Ilustríssimos Senhores(as)" in e for e in erros)

    def test_numero_plural_agrupado(self) -> None:
        ctx = _ctx_mocao(
            designacao_propositura="Moção de Aplauso",  # wrong — should be plural
            copia_art="cópia da",
            aprovada_s="aprovada",
        )
        reg = _registro(ctx=ctx, n_props=2)
        erros = verificar_concordancia_linguistica(reg)
        assert any("Moções de Aplauso" in e for e in erros)


# ---------------------------------------------------------------------------
# verificar_linha_planilha
# ---------------------------------------------------------------------------
class TestVerificarLinhaPlanilha:
    def test_linha_correta(self) -> None:
        reg = _registro()
        linha = _linha_padrao()
        assert verificar_linha_planilha(linha, reg) == []

    def test_num_oficio_errado(self) -> None:
        reg = _registro()
        linha = _linha_padrao(num_oficio="999")
        erros = verificar_linha_planilha(linha, reg)
        assert any("num_oficio" in e for e in erros)

    def test_destinatario_errado(self) -> None:
        reg = _registro()
        linha = _linha_padrao(destinatario="Ao Excelentíssimo Senhor OUTRO NOME")
        erros = verificar_linha_planilha(linha, reg)
        assert any("destinatário" in e or "destinatario" in e.lower() for e in erros)

    def test_num_mocao_ausente_no_assunto(self) -> None:
        reg = _registro()
        linha = _linha_padrao(assunto="Encaminha Moção de Aplauso nº 999/2026")
        erros = verificar_linha_planilha(linha, reg)
        assert any("124" in e for e in erros)

    def test_envio_errado(self) -> None:
        reg = _registro()
        linha = _linha_padrao(envio="E-mail")
        erros = verificar_linha_planilha(linha, reg)
        assert any("envio" in e.lower() for e in erros)

    def test_linha_curta(self) -> None:
        reg = _registro()
        erros = verificar_linha_planilha(["001", "2026-05-15"], reg)
        assert any("coluna" in e for e in erros)


# ---------------------------------------------------------------------------
# corrigir_ctx
# ---------------------------------------------------------------------------
class TestCorrigirCtx:
    def test_corrige_num_mocao(self) -> None:
        reg = _registro(
            ctx=_ctx_mocao(num_mocao="999"),
            dados_grupo=[_dados_mocao(numero="124")],
        )
        ctx_corr = corrigir_ctx(reg, ["num_mocao: ctx='999'"], [])
        assert ctx_corr["num_mocao"] == "124"
        assert ctx_corr["NUM_MOCAO"] == "124"

    def test_corrige_tipo_mocao(self) -> None:
        reg = _registro(
            ctx=_ctx_mocao(tipo_mocao="Apelo"),
            dados_grupo=[_dados_mocao(tipo="Aplauso")],
        )
        ctx_corr = corrigir_ctx(reg, ["tipo_mocao: ctx='Apelo'"], [])
        assert ctx_corr["tipo_mocao"] == "Aplauso"

    def test_corrige_tipo_propositura(self) -> None:
        ctx = _ctx_mocao(tipo_propositura="requerimento_pesar")
        reg = _registro(ctx=ctx, tipo_propositura="mocao")
        ctx_corr = corrigir_ctx(reg, ["tipo_propositura: ctx='requerimento_pesar'"], [])
        assert ctx_corr["tipo_propositura"] == "mocao"

    def test_corrige_honorificos_usando_info(self) -> None:
        ctx = _ctx_mocao(
            vocativo="Ilustríssimo Senhor",  # wrong gender
            pronome_corpo="Vossa Senhoria",
            tratamento_rodape="Ao Ilustríssimo Senhor",
        )
        info_fem = _info_padrao(
            vocativo="Ilustríssima Senhora",
            pronome_corpo="Vossa Senhoria",
            tratamento_rodape="À Ilustríssima Senhora",
            destinatario_nome="MARIA SILVA",
        )
        reg = _registro(ctx=ctx, info=info_fem)
        ctx_corr = corrigir_ctx(reg, [], ["Gênero F — vocativo com forma masculina: 'Ilustríssimo Senhor'"])
        assert ctx_corr["vocativo"] == "Ilustríssima Senhora"
        assert ctx_corr["tratamento_rodape"] == "À Ilustríssima Senhora"

    def test_corrige_concordancia_numero(self) -> None:
        ctx = _ctx_mocao(
            designacao_propositura="Moção de Aplauso",  # wrong — should be plural
            copia_art="cópia da",
            aprovada_s="aprovada",
        )
        reg = _registro(ctx=ctx, n_props=2)
        ctx_corr = corrigir_ctx(
            reg, [], ["Designação (n=2): ctx='Moção de Aplauso'"]
        )
        assert ctx_corr["designacao_propositura"] == "Moções de Aplauso"
        assert ctx_corr["copia_art"] == "cópias das"
        assert ctx_corr["aprovada_s"] == "aprovadas"

    def test_nao_muta_ctx_original(self) -> None:
        ctx_orig = _ctx_mocao(num_mocao="999")
        reg = _registro(ctx=ctx_orig, dados_grupo=[_dados_mocao(numero="124")])
        corrigir_ctx(reg, ["num_mocao: ctx='999'"], [])
        assert ctx_orig["num_mocao"] == "999"

    def test_corrige_requerimento_pesar_formas_fixas(self) -> None:
        ctx = _ctx_mocao(
            tipo_propositura="requerimento_pesar",
            vocativo="Ilustríssimo Senhor",  # wrong
            pronome_corpo="Vossa Senhoria",
        )
        reg = _registro(ctx=ctx, tipo_propositura="requerimento_pesar")
        ctx_corr = corrigir_ctx(reg, [], ["Requerimento de pesar — vocativo:"])
        assert ctx_corr["vocativo"] == "Ilustríssimos Senhores(as)"
        assert ctx_corr["pronome_corpo"] == "Vossas Senhorias"


# ---------------------------------------------------------------------------
# _corrigir_linha_planilha
# ---------------------------------------------------------------------------
class TestCorrigirLinhaPlanilha:
    def test_corrige_destinatario(self) -> None:
        reg = _registro()
        linha = _linha_padrao(destinatario="Errado")
        corr = _corrigir_linha_planilha(linha, reg)
        assert corr[2] == "Ao Ilustríssimo Senhor FULANO DE TAL"

    def test_corrige_assunto_mocao(self) -> None:
        reg = _registro()
        linha = _linha_padrao(assunto="Errado")
        corr = _corrigir_linha_planilha(linha, reg)
        assert "Aplauso" in corr[3]
        assert "124" in corr[3]

    def test_corrige_assunto_pesar(self) -> None:
        ctx_p = _ctx_mocao(
            tipo_propositura="requerimento_pesar",
            num_mocao="45",
        )
        info_p = _info_padrao(
            vocativo="Ilustríssimos Senhores(as)",
            pronome_corpo="Vossas Senhorias",
            tratamento_rodape="Aos familiares do Sr.(ª),",
            destinatario_nome="JOÃO SILVA",
        )
        reg = _registro(
            ctx=ctx_p,
            info=info_p,
            tipo_propositura="requerimento_pesar",
        )
        linha = _linha_padrao(assunto="Errado")
        corr = _corrigir_linha_planilha(linha, reg)
        assert "Requerimento de Pesar" in corr[3]
        assert "45" in corr[3]

    def test_preserva_colunas_nao_verificadas(self) -> None:
        reg = _registro()
        linha = _linha_padrao(vereadores="Alex Dantas (ad)", sigla="ajc")
        corr = _corrigir_linha_planilha(linha, reg)
        assert corr[4] == "Alex Dantas (ad)"
        assert corr[6] == "ajc"

    def test_assunto_mocao_singular_formato_exato(self) -> None:
        """Verifica que o assunto gerado contém 'Moção' (com cedilha), não 'Moão'."""
        reg = _registro()
        linha = _linha_padrao(assunto="Errado")
        corr = _corrigir_linha_planilha(linha, reg)
        assert corr[3] == "Encaminha Moção de Aplauso nº 124/2026"

    def test_assunto_mocao_plural_formato_exato(self) -> None:
        """Verifica que o assunto plural contém 'Moções' (com cedilha), não 'Moões'."""
        ctx = _ctx_mocao(num_mocao="124 e 125", tipo_mocao="Aplauso")
        reg = _registro(ctx=ctx, n_props=2)
        linha = _linha_padrao(assunto="Errado")
        corr = _corrigir_linha_planilha(linha, reg)
        assert corr[3] == "Encaminha Moções de Aplauso nº 124 e 125/2026"


# ---------------------------------------------------------------------------
# ResultadoVerificacao helpers
# ---------------------------------------------------------------------------
class TestResultadoVerificacao:
    def test_sem_erros(self) -> None:
        r = ResultadoVerificacao(arquivo="test.docx")
        assert not r.tem_erros
        assert r.todos_erros == []

    def test_com_erros(self) -> None:
        r = ResultadoVerificacao(arquivo="test.docx", erros_dados=["erro1"])
        assert r.tem_erros
        assert r.todos_erros == ["erro1"]

    def test_todos_erros_concatenados(self) -> None:
        r = ResultadoVerificacao(
            arquivo="test.docx",
            erros_dados=["d1"],
            erros_linguisticos=["l1", "l2"],
            erros_planilha=["p1"],
        )
        assert r.todos_erros == ["d1", "l1", "l2", "p1"]
