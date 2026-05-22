"""Conferência e correção automática dos ofícios e planilha gerados.

Implementa a Fase 6 do fluxo de processamento: após a geração de todos os
ofícios (.docx), este módulo verifica a consistência e a correção linguística
de cada documento antes de a planilha Excel ser gravada em disco.

Verificações realizadas por ofício:
- **Consistência de dados**: ctx ↔ dados extraídos pela IA (números de moção,
  tipos, falecido, tipo_propositura).
- **Concordância linguística**: consistência interna entre vocativo,
  pronome_corpo e tratamento_rodapé; concordância de número nas designações,
  artigos e particípios.
- **Consistência da planilha**: cada linha Excel é conferida contra o ctx do
  ofício correspondente.

Erros encontrados são corrigidos automaticamente por re-renderização do
template .docx; erros irrecuperáveis são registrados no log e o fluxo segue.

Public exports:
    RegistroOficio: snapshot de um ofício gerado, preenchido pelo processor.
    ResultadoVerificacao: resultado da verificação de um único ofício.
    RelatorioConferencia: relatório agregado de toda a rodada.
    conferir_trabalho: orquestrador principal — recebe os registros e executa tudo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from z7_officeletters.core.documents import formatar_lista_pt as _formatar_lista_pt
from z7_officeletters.core.documents import frases_propositura as _frases_propositura

__all__ = [
    "RegistroOficio",
    "ResultadoVerificacao",
    "RelatorioConferencia",
    "conferir_trabalho",
]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class RegistroOficio:
    """Snapshot de um ofício gerado, mantido para verificação na Fase 6.

    Attributes:
        caminho: Caminho absoluto para o arquivo .docx gerado.
        nome_arquivo: Somente o nome do arquivo (sem diretório).
        ctx: Dicionário de contexto usado para renderizar o template (mutável —
            é atualizado in-place quando correções são aplicadas).
        dados_grupo: Lista dos dicts de dados extraídos pela IA para o grupo
            de proposituras agrupadas neste ofício.
        dest_raw: Dict bruto do destinatário extraído pela IA (primeiro do grupo).
        info: Dict ``DestinatarioProcessado`` (já com sobrescritas do DB de
            endereços, quando aplicável).
        n_props: Número de proposituras agrupadas neste ofício.
        tipo_propositura: ``"mocao"`` ou ``"requerimento_pesar"``.
        template_path: Caminho absoluto do template .docx utilizado.
        linha_planilha_idx: Índice da linha correspondente em ``dados_planilha``.
    """

    caminho: str
    nome_arquivo: str
    ctx: dict[str, str]
    dados_grupo: list[dict[str, Any]]
    dest_raw: dict[str, Any]
    info: dict[str, str]
    n_props: int
    tipo_propositura: str
    template_path: str
    linha_planilha_idx: int


@dataclass
class ResultadoVerificacao:
    """Resultado da verificação de um único ofício.

    Attributes:
        arquivo: Nome do arquivo verificado.
        erros_dados: Erros de consistência de dados (números, tipos, falecido).
        erros_linguisticos: Erros de concordância linguística.
        erros_planilha: Erros na linha correspondente da planilha Excel.
        corrigido: True quando todos os erros foram corrigidos com sucesso.
        incorrigivel: True quando houve erros mas a correção falhou.
    """

    arquivo: str
    erros_dados: list[str] = field(default_factory=list)
    erros_linguisticos: list[str] = field(default_factory=list)
    erros_planilha: list[str] = field(default_factory=list)
    corrigido: bool = False
    incorrigivel: bool = False

    @property
    def tem_erros(self) -> bool:
        """True se houver qualquer erro encontrado."""
        return bool(self.erros_dados or self.erros_linguisticos or self.erros_planilha)

    @property
    def todos_erros(self) -> list[str]:
        """Lista plana de todos os erros encontrados."""
        return self.erros_dados + self.erros_linguisticos + self.erros_planilha


@dataclass
class RelatorioConferencia:
    """Relatório agregado de toda a rodada de conferência.

    Attributes:
        total_verificados: Total de ofícios processados pela verificação.
        total_com_erros: Ofícios em que pelo menos um erro foi encontrado.
        total_corrigidos: Ofícios com erros que foram corrigidos com sucesso.
        total_incorrigiveis: Ofícios com erros que não puderam ser corrigidos.
        resultados: Lista de :class:`ResultadoVerificacao` por ofício.
    """

    total_verificados: int = 0
    total_com_erros: int = 0
    total_corrigidos: int = 0
    total_incorrigiveis: int = 0
    resultados: list[ResultadoVerificacao] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Verification functions
# ---------------------------------------------------------------------------


def verificar_consistencia_dados(registro: RegistroOficio) -> list[str]:
    """Verifica se os valores do ctx correspondem aos dados brutos da IA.

    Verifica:
    - ``num_mocao`` no ctx é o merge correto dos números em ``dados_grupo``.
    - ``tipo_mocao`` no ctx é o merge correto dos tipos em ``dados_grupo``.
    - ``falecido`` no ctx corresponde ao merge dos falecidos (requerimento_pesar).
    - ``tipo_propositura`` no ctx bate com o tipo do registro.

    Returns:
        Lista de descrições de erros encontrados (vazia = sem erros).
    """
    erros: list[str] = []
    ctx = registro.ctx
    dados = registro.dados_grupo

    # Re-compute expected merged values from source AI data
    nums_lista = [d["numero_mocao"] for d in dados if d.get("numero_mocao")]
    nums_esperados = _formatar_lista_pt(nums_lista) if nums_lista else ""

    tipos_lista = [str(d.get("tipo_mocao", "")) for d in dados if d.get("tipo_mocao")]
    tipo_esperado = _formatar_lista_pt(tipos_lista) if tipos_lista else ""

    falecidos_lista = [str(d.get("falecido", "")) for d in dados if d.get("falecido")]
    falecido_esperado = _formatar_lista_pt(falecidos_lista) if falecidos_lista else ""

    # Check num_mocao
    if nums_esperados and ctx.get("num_mocao") != nums_esperados:
        erros.append(
            f"num_mocao: ctx='{ctx.get('num_mocao')}' — esperado='{nums_esperados}'"
        )

    # Check tipo_mocao (only for moções)
    if registro.tipo_propositura != "requerimento_pesar" and tipo_esperado:
        if ctx.get("tipo_mocao") != tipo_esperado:
            erros.append(
                f"tipo_mocao: ctx='{ctx.get('tipo_mocao')}' — esperado='{tipo_esperado}'"
            )

    # Check falecido (only for requerimentos de pesar)
    if registro.tipo_propositura == "requerimento_pesar" and falecido_esperado:
        if ctx.get("falecido") != falecido_esperado:
            erros.append(
                f"falecido: ctx='{ctx.get('falecido')}' — esperado='{falecido_esperado}'"
            )

    # Check tipo_propositura field itself
    if ctx.get("tipo_propositura", "") != registro.tipo_propositura:
        erros.append(
            f"tipo_propositura: ctx='{ctx.get('tipo_propositura')}' "
            f"— esperado='{registro.tipo_propositura}'"
        )

    return erros


def verificar_concordancia_linguistica(registro: RegistroOficio) -> list[str]:
    """Verifica concordância de gênero, número e pronomes no ctx.

    Regras verificadas:
    - Consistência interna: vocativo ↔ pronome_corpo ↔ tratamento_rodapé.
    - Requerimento de pesar: formas fixas obrigatórias.
    - Concordância de número: designacao_propositura / copia_art / aprovada_s
      batem com ``n_props``.
    - Prefeito (``is_prefeito``): formas fixas e destinatário correto.
    - Instituição (PJ/Coletivo): formas plurais.

    Returns:
        Lista de descrições de erros encontrados (vazia = sem erros).
    """
    erros: list[str] = []
    ctx = registro.ctx
    dest = registro.dest_raw
    n_props = registro.n_props
    tipo_prop = registro.tipo_propositura
    tipo_mocao = ctx.get("tipo_mocao", "")

    # ── Requerimento de pesar: formas fixas ──────────────────────────────────
    if tipo_prop == "requerimento_pesar":
        if ctx.get("vocativo") != "Ilustríssimos Senhores(as)":
            erros.append(
                f"Requerimento de pesar — vocativo: "
                f"ctx='{ctx.get('vocativo')}' esperado='Ilustríssimos Senhores(as)'"
            )
        if ctx.get("pronome_corpo") != "Vossas Senhorias":
            erros.append(
                f"Requerimento de pesar — pronome_corpo: "
                f"ctx='{ctx.get('pronome_corpo')}' esperado='Vossas Senhorias'"
            )
        _verificar_numero(erros, ctx, tipo_prop, tipo_mocao, n_props)
        return erros

    # ── Internal vocativo ↔ pronome_corpo consistency ────────────────────────
    vocativo = ctx.get("vocativo", "")
    pronome = ctx.get("pronome_corpo", "")
    tratamento = ctx.get("tratamento_rodape", "")
    _verificar_consistencia_pronomes(erros, vocativo, pronome, tratamento)

    # ── Recipient-specific checks ────────────────────────────────────────────
    tipo_dest = dest.get("tipo", "PF")
    is_inst = tipo_dest in ("PJ", "Coletivo") or bool(dest.get("is_instituicao"))
    is_prefeito = bool(dest.get("is_prefeito")) or "prefeito" in (dest.get("nome") or "").lower()

    if is_prefeito:
        _verificar_prefeito(erros, ctx)
    elif is_inst:
        _verificar_instituicao(erros, ctx)
    else:
        genero = dest.get("genero") or "M"
        nivel = dest.get("nivel_protocolo") or "VS"
        _verificar_pf(erros, ctx, genero, nivel)

    # ── Number agreement ─────────────────────────────────────────────────────
    _verificar_numero(erros, ctx, tipo_prop, tipo_mocao, n_props)

    return erros


def _verificar_consistencia_pronomes(
    erros: list[str], vocativo: str, pronome: str, tratamento: str
) -> None:
    """Verifica a consistência interna entre vocativo, pronome e tratamento."""
    voc_lower = vocativo.lower()

    if "excelentíssim" in voc_lower:
        if pronome != "Vossa Excelência":
            erros.append(
                f"Inconsistência: vocativo '{vocativo}' requer pronome "
                f"'Vossa Excelência' — encontrado '{pronome}'"
            )
    elif "ilustríssimos" in voc_lower or "ilustríssimas" in voc_lower:
        if pronome != "Vossas Senhorias":
            erros.append(
                f"Inconsistência: vocativo plural '{vocativo}' requer "
                f"'Vossas Senhorias' — encontrado '{pronome}'"
            )
    elif "ilustríssim" in voc_lower:
        if pronome != "Vossa Senhoria":
            erros.append(
                f"Inconsistência: vocativo '{vocativo}' requer "
                f"'Vossa Senhoria' — encontrado '{pronome}'"
            )

    # Gender consistency between vocativo and tratamento_rodape
    voc_feminino = "senhora" in voc_lower and "senhori" not in voc_lower
    voc_masculino = (
        "senhor" in voc_lower
        and "senhora" not in voc_lower
        and "senhori" not in voc_lower
        and "senhorias" not in voc_lower
    )
    trat_lower = tratamento.lower()
    if voc_feminino and "senhor" in trat_lower and "senhora" not in trat_lower:
        erros.append(
            f"Inconsistência: vocativo feminino '{vocativo}' mas "
            f"tratamento_rodapé com forma masculina '{tratamento}'"
        )
    if voc_masculino and "senhora" in trat_lower and "senhori" not in trat_lower:
        erros.append(
            f"Inconsistência: vocativo masculino '{vocativo}' mas "
            f"tratamento_rodapé com forma feminina '{tratamento}'"
        )


def _verificar_prefeito(erros: list[str], ctx: dict[str, str]) -> None:
    """Verifica que o ctx usa as formas fixas obrigatórias para o Prefeito."""
    from z7_officeletters.core.config import PREFEITO  # noqa: PLC0415

    if ctx.get("vocativo") != "Excelentíssimo Senhor Prefeito":
        erros.append(
            f"Prefeito — vocativo: ctx='{ctx.get('vocativo')}' "
            f"esperado='Excelentíssimo Senhor Prefeito'"
        )
    if ctx.get("pronome_corpo") != "Vossa Excelência":
        erros.append(
            f"Prefeito — pronome_corpo: ctx='{ctx.get('pronome_corpo')}' "
            f"esperado='Vossa Excelência'"
        )
    nome_esperado = PREFEITO.get("nome", "").upper()
    if nome_esperado and ctx.get("destinatario_nome") != nome_esperado:
        erros.append(
            f"Prefeito — destinatario_nome: ctx='{ctx.get('destinatario_nome')}' "
            f"esperado='{nome_esperado}'"
        )


def _verificar_instituicao(erros: list[str], ctx: dict[str, str]) -> None:
    """Verifica que o ctx usa as formas plurais para PJ/Coletivo."""
    pronome = ctx.get("pronome_corpo", "")
    vocativo = ctx.get("vocativo", "")

    if pronome != "Vossas Senhorias":
        erros.append(
            f"Instituição — pronome_corpo: ctx='{pronome}' esperado='Vossas Senhorias'"
        )
    voc_lower = vocativo.lower()
    if "senhores" not in voc_lower and "senhoras" not in voc_lower:
        erros.append(
            f"Instituição — vocativo: ctx='{vocativo}' não está no plural "
            f"(esperado 'Ilustríssimos Senhores' ou 'Ilustríssimas Senhoras')"
        )


def _verificar_pf(
    erros: list[str], ctx: dict[str, str], genero: str, nivel: str
) -> None:
    """Verifica formas de gênero e nível de protocolo para pessoa física."""
    vocativo = ctx.get("vocativo", "")
    tratamento = ctx.get("tratamento_rodape", "")
    voc_lower = vocativo.lower()
    trat_lower = tratamento.lower()

    if genero == "F":
        if "senhor" in voc_lower and "senhora" not in voc_lower:
            erros.append(
                f"Gênero F — vocativo com forma masculina: '{vocativo}'"
            )
        if nivel == "VS":
            if "ilustríssima" not in voc_lower:
                erros.append(
                    f"Gênero F, nível VS — vocativo: '{vocativo}' "
                    f"deveria conter 'Ilustríssima'"
                )
            if not tratamento.startswith("À Ilustríssima"):
                erros.append(
                    f"Gênero F, nível VS — tratamento_rodapé: '{tratamento}' "
                    f"deveria começar com 'À Ilustríssima'"
                )
        elif nivel in ("VE", "VE_M"):
            if "excelentíssima" not in voc_lower:
                erros.append(
                    f"Gênero F, nível {nivel} — vocativo: '{vocativo}' "
                    f"deveria conter 'Excelentíssima'"
                )
    else:  # genero == "M"
        if nivel == "VS":
            if "ilustríssimo" not in voc_lower:
                erros.append(
                    f"Gênero M, nível VS — vocativo: '{vocativo}' "
                    f"deveria conter 'Ilustríssimo'"
                )
            if not tratamento.startswith("Ao Ilustríssimo"):
                erros.append(
                    f"Gênero M, nível VS — tratamento_rodapé: '{tratamento}' "
                    f"deveria começar com 'Ao Ilustríssimo'"
                )
        elif nivel in ("VE", "VE_M"):
            if "excelentíssimo" not in voc_lower:
                erros.append(
                    f"Gênero M, nível {nivel} — vocativo: '{vocativo}' "
                    f"deveria conter 'Excelentíssimo'"
                )

    # Protocol-level crase check
    if nivel == "VE":
        if "À Sua Excelência" in tratamento:
            erros.append(
                f"Nível VE (federal/estadual) — tratamento_rodapé: '{tratamento}' "
                f"não deve ter crase; esperado 'A Sua Excelência'"
            )
    elif nivel == "VE_M":
        if tratamento.startswith("A Sua Excelência") and not tratamento.startswith("À"):
            erros.append(
                f"Nível VE_M (municipal) — tratamento_rodapé: '{tratamento}' "
                f"deve ter crase; esperado 'À Sua Excelência'"
            )


def _verificar_numero(
    erros: list[str],
    ctx: dict[str, str],
    tipo_prop: str,
    tipo_mocao: str,
    n_props: int,
) -> None:
    """Verifica concordância de número em designacao, copia_art e aprovada_s."""
    esp_desig, esp_art, esp_aprov = _frases_propositura(tipo_prop, tipo_mocao, n_props)

    ctx_desig = ctx.get("designacao_propositura", "")
    ctx_art = ctx.get("copia_art", "")
    ctx_aprov = ctx.get("aprovada_s", "")

    if ctx_desig and ctx_desig != esp_desig:
        erros.append(
            f"Designação (n={n_props}): ctx='{ctx_desig}' — esperado='{esp_desig}'"
        )
    if ctx_art and ctx_art != esp_art:
        erros.append(
            f"Artigo cópia (n={n_props}): ctx='{ctx_art}' — esperado='{esp_art}'"
        )
    if ctx_aprov and ctx_aprov != esp_aprov:
        erros.append(
            f"Particípio (n={n_props}): ctx='{ctx_aprov}' — esperado='{esp_aprov}'"
        )


def verificar_linha_planilha(
    linha: list[Any], registro: RegistroOficio
) -> list[str]:
    """Verifica se a linha da planilha é consistente com o ofício correspondente.

    Confere:
    - ``linha[0]`` (num_oficio) == ctx[``num_oficio``].
    - ``linha[2]`` (destinatário) == tratamento_rodapé + destinatario_nome.
    - ``linha[3]`` (assunto) contém o tipo e os números de moção corretos.
    - ``linha[5]`` (envio) == info[``envio``].

    Returns:
        Lista de descrições de erros encontrados (vazia = sem erros).
    """
    erros: list[str] = []
    ctx = registro.ctx
    info = registro.info
    n_props = registro.n_props
    tipo_prop = registro.tipo_propositura
    num_mocao = ctx.get("num_mocao", "")
    tipo_mocao = ctx.get("tipo_mocao", "")

    if len(linha) < 6:
        erros.append(f"Linha da planilha com apenas {len(linha)} coluna(s) — esperado ≥ 6")
        return erros

    num_planilha = str(linha[0])
    dest_planilha = str(linha[2])
    assunto_planilha = str(linha[3])
    envio_planilha = str(linha[5])

    # num_oficio
    if num_planilha != ctx.get("num_oficio", ""):
        erros.append(
            f"Planilha num_oficio: '{num_planilha}' ≠ ctx '{ctx.get('num_oficio')}'"
        )

    # destinatário
    esperado_dest = (
        f"{info.get('tratamento_rodape', '')} {info.get('destinatario_nome', '')}".strip()
    )
    if dest_planilha != esperado_dest:
        erros.append(
            f"Planilha destinatário: '{dest_planilha}' ≠ esperado '{esperado_dest}'"
        )

    # assunto: deve conter o número da moção
    if num_mocao and num_mocao not in assunto_planilha:
        erros.append(
            f"Planilha assunto: '{assunto_planilha}' não contém número '{num_mocao}'"
        )

    # assunto: deve conter o tipo (para moções)
    if tipo_prop != "requerimento_pesar" and tipo_mocao and tipo_mocao not in assunto_planilha:
        erros.append(
            f"Planilha assunto: '{assunto_planilha}' não contém tipo '{tipo_mocao}'"
        )

    # envio
    if envio_planilha != info.get("envio", ""):
        erros.append(
            f"Planilha envio: '{envio_planilha}' ≠ '{info.get('envio')}'"
        )

    return erros


# ---------------------------------------------------------------------------
# Correction
# ---------------------------------------------------------------------------


def corrigir_ctx(
    registro: RegistroOficio,
    erros_dados: list[str],
    erros_ling: list[str],
) -> dict[str, str]:
    """Deriva um ctx corrigido a partir dos dados de origem e do info processado.

    Aplica correções cirúrgicas: apenas campos com erros detectados são
    recalculados, preservando os demais valores originais (inclusive possíveis
    sobrescritas vindas do banco de endereços).

    Args:
        registro: Registro do ofício a corrigir.
        erros_dados: Lista de erros de consistência de dados (de
            :func:`verificar_consistencia_dados`).
        erros_ling: Lista de erros linguísticos (de
            :func:`verificar_concordancia_linguistica`).

    Returns:
        Novo dict ctx com as correções aplicadas (o ctx original não é mutado).
    """
    ctx = dict(registro.ctx)  # shallow copy — str values are immutable
    dados = registro.dados_grupo
    info = registro.info
    n_props = registro.n_props
    tipo_prop = registro.tipo_propositura

    # ── Fix data fields ───────────────────────────────────────────────────────
    erros_dados_lower = [e.lower() for e in erros_dados]

    if any("num_mocao" in e for e in erros_dados_lower):
        nums_lista = [d["numero_mocao"] for d in dados if d.get("numero_mocao")]
        if nums_lista:
            merged = _formatar_lista_pt(nums_lista)
            ctx["num_mocao"] = merged
            ctx["NUM_MOCAO"] = merged

    if any("tipo_mocao" in e for e in erros_dados_lower):
        tipos = [str(d.get("tipo_mocao", "")) for d in dados if d.get("tipo_mocao")]
        if tipos:
            merged = _formatar_lista_pt(tipos)
            ctx["tipo_mocao"] = merged
            ctx["TIPO_MOCAO"] = merged

    if any("falecido" in e for e in erros_dados_lower):
        falecidos = [str(d.get("falecido", "")) for d in dados if d.get("falecido")]
        if falecidos:
            merged = _formatar_lista_pt(falecidos)
            ctx["falecido"] = merged
            ctx["FALECIDO"] = merged

    if any("tipo_propositura" in e for e in erros_dados_lower):
        ctx["tipo_propositura"] = tipo_prop
        ctx["TIPO_PROPOSITURA"] = tipo_prop

    # ── Fix honorifics / protocol forms ──────────────────────────────────────
    # Use ``info`` (already contains DB overrides) to avoid regression.
    erros_ling_lower = [e.lower() for e in erros_ling]
    honorific_keywords = ("vocativo", "pronome", "gênero", "tratamento", "prefeito", "instituição")
    if any(kw in e for e in erros_ling_lower for kw in honorific_keywords):
        ctx["vocativo"] = info["vocativo"]
        ctx["VOCATIVO"] = info["vocativo"]
        ctx["pronome_corpo"] = info["pronome_corpo"]
        ctx["PRONOME_CORPO"] = info["pronome_corpo"]
        ctx["tratamento_rodape"] = info["tratamento_rodape"]
        ctx["TRATAMENTO_RODAPE"] = info["tratamento_rodape"]
        ctx["destinatario_nome"] = info["destinatario_nome"]
        ctx["DESTINATARIO_NOME"] = info["destinatario_nome"]

    # ── Fix requerimento_pesar fixed overrides ────────────────────────────────
    if tipo_prop == "requerimento_pesar":
        ctx["vocativo"] = "Ilustríssimos Senhores(as)"
        ctx["VOCATIVO"] = "Ilustríssimos Senhores(as)"
        ctx["pronome_corpo"] = "Vossas Senhorias"
        ctx["PRONOME_CORPO"] = "Vossas Senhorias"

    # ── Fix number agreement ──────────────────────────────────────────────────
    number_keywords = ("designação", "artigo", "particípio", "copia", "aprovada", "designacao")
    if any(kw in e for e in erros_ling_lower for kw in number_keywords):
        tipo_mocao = ctx.get("tipo_mocao", "")
        desig, art, aprov = _frases_propositura(tipo_prop, tipo_mocao, n_props)
        ctx["designacao_propositura"] = desig
        ctx["DESIGNACAO_PROPOSITURA"] = desig
        ctx["copia_art"] = art
        ctx["COPIA_ART"] = art
        ctx["aprovada_s"] = aprov
        ctx["APROVADA_S"] = aprov

    return ctx


def _corrigir_linha_planilha(
    linha: list[Any], registro: RegistroOficio
) -> list[Any]:
    """Retorna uma linha de planilha corrigida para o registro fornecido."""
    ctx = registro.ctx
    info = registro.info
    n_props = registro.n_props
    tipo_prop = registro.tipo_propositura

    # Pad line to at least 6 elements to prevent IndexError
    linha_corr = list(linha)
    if len(linha_corr) < 6:
        linha_corr.extend([""] * (6 - len(linha_corr)))

    # Extrair o ano da data ISO (campo linha_corr[1], formato YYYY-MM-DD)
    data_iso = str(linha_corr[1])
    year = data_iso[:4] if len(data_iso) >= 4 else ""

    num_mocao = ctx.get("num_mocao", "")
    tipo_mocao = ctx.get("tipo_mocao", "")

    if tipo_prop == "requerimento_pesar":
        plural_s = "s" if n_props > 1 else ""
        assunto = f"Encaminha Requerimento{plural_s} de Pesar nº {num_mocao}/{year}"
    else:
        plural_oes = "ções" if n_props > 1 else "ção"
        assunto = f"Encaminha Mo{plural_oes} de {tipo_mocao} nº {num_mocao}/{year}"

    destinatario = (
        f"{info.get('tratamento_rodape', '')} {info.get('destinatario_nome', '')}".strip()
    )

    linha_corr[0] = ctx.get("num_oficio", linha_corr[0])
    linha_corr[2] = destinatario
    linha_corr[3] = assunto
    linha_corr[5] = info.get("envio", linha_corr[5])
    return linha_corr


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


def conferir_trabalho(
    registros: list[RegistroOficio],
    dados_planilha: list[list[Any]],
    q: Any,
) -> RelatorioConferencia:
    """Orquestrador da Fase 6: verifica e corrige automaticamente todos os ofícios.

    Para cada ofício gerado:
    1. Verifica consistência de dados (ctx ↔ dados_grupo da IA).
    2. Verifica concordância linguística (pronomes, gênero, número).
    3. Verifica a linha correspondente na planilha.
    4. Corrige os erros encontrados via re-renderização do template.
    5. Atualiza ``dados_planilha`` in-place quando a linha Excel precisa de ajuste.
    6. Registra tudo em detalhe (log Python + mensagens na fila UI).

    Args:
        registros: Lista de :class:`RegistroOficio` construída durante a Fase 3.
        dados_planilha: Lista mutável de linhas da planilha; corrigida in-place.
        q: Fila de mensagens do worker (``queue.Queue[tuple]``) para atualizar a UI.

    Returns:
        :class:`RelatorioConferencia` com o resultado completo.
    """
    from docxtpl import DocxTemplate  # noqa: PLC0415 — importado aqui para não poluir core/

    relatorio = RelatorioConferencia()
    relatorio.total_verificados = len(registros)

    q.put(("log", "\n🔍  Iniciando conferência dos ofícios gerados…", "accent"))
    logger.info(
        "Fase 6: Conferência automática — %d ofício(s) a verificar.", len(registros)
    )

    for i, registro in enumerate(registros, start=1):
        resultado = ResultadoVerificacao(arquivo=registro.nome_arquivo)
        prefixo = f"  [{i}/{len(registros)}]  {registro.nome_arquivo}"

        logger.debug("Conferindo: %s", registro.nome_arquivo)
        q.put(("log", f"\n{prefixo}", "dim"))

        # ── 1. Data consistency ───────────────────────────────────────────────
        resultado.erros_dados = verificar_consistencia_dados(registro)
        if resultado.erros_dados:
            q.put(("log", "    � Ajustes de dados:", "warn"))
            for e in resultado.erros_dados:
                logger.warning("  [DADOS] %s — %s", registro.nome_arquivo, e)
                q.put(("log", f"      • {e}", "dim"))

        # ── 2. Linguistic concordance ─────────────────────────────────────────
        resultado.erros_linguisticos = verificar_concordancia_linguistica(registro)
        if resultado.erros_linguisticos:
            q.put(("log", "    📝 Ajustes linguísticos:", "warn"))
            for e in resultado.erros_linguisticos:
                logger.warning("  [LINGUÍSTICO] %s — %s", registro.nome_arquivo, e)
                q.put(("log", f"      • {e}", "dim"))

        # ── 3. Spreadsheet row ────────────────────────────────────────────────
        idx = registro.linha_planilha_idx
        if 0 <= idx < len(dados_planilha):
            resultado.erros_planilha = verificar_linha_planilha(
                dados_planilha[idx], registro
            )
            if resultado.erros_planilha:
                q.put(("log", "    📝 Ajustes na planilha:", "warn"))
                for e in resultado.erros_planilha:
                    logger.warning("  [PLANILHA] %s — %s", registro.nome_arquivo, e)
                    q.put(("log", f"      • {e}", "dim"))

        # ── 4. Auto-correction ────────────────────────────────────────────────
        if resultado.tem_erros:
            relatorio.total_com_erros += 1
            q.put(("log", "    🔧  Corrigindo e re-renderizando…", ""))
            logger.info("  Corrigindo '%s'…", registro.nome_arquivo)

            try:
                ctx_corr = corrigir_ctx(
                    registro, resultado.erros_dados, resultado.erros_linguisticos
                )

                doc = DocxTemplate(registro.template_path)
                doc.render(ctx_corr)
                doc.save(registro.caminho)

                # Commit corrected ctx back into the registro for downstream use
                registro.ctx.update(ctx_corr)

                # Fix spreadsheet row in-place
                if 0 <= idx < len(dados_planilha) and resultado.erros_planilha:
                    dados_planilha[idx] = _corrigir_linha_planilha(
                        dados_planilha[idx], registro
                    )

                resultado.corrigido = True
                relatorio.total_corrigidos += 1
                logger.info("  ✔  '%s' corrigido com sucesso.", registro.nome_arquivo)
                q.put(("log", "    ✔  Corrigido com sucesso.", "success"))

            except Exception as exc:  # noqa: BLE001
                resultado.incorrigivel = True
                relatorio.total_incorrigiveis += 1
                logger.error(
                    "  ✗  Não foi possível corrigir '%s': %s",
                    registro.nome_arquivo, exc,
                )
                q.put(("log", f"    ✗  Não foi possível corrigir: {exc}", "error"))
        else:
            logger.debug("  ✔  Sem erros: %s", registro.nome_arquivo)
            q.put(("log", "    ✔  OK — sem erros.", "success"))

        relatorio.resultados.append(resultado)

    # ── Summary ───────────────────────────────────────────────────────────────
    _emitir_resumo(relatorio, q)
    logger.info(
        "Conferência finalizada: %d verificados, %d com erros, %d corrigidos, %d incorrigíveis.",
        relatorio.total_verificados,
        relatorio.total_com_erros,
        relatorio.total_corrigidos,
        relatorio.total_incorrigiveis,
    )
    return relatorio


def _emitir_resumo(relatorio: RelatorioConferencia, q: Any) -> None:
    """Posta na fila e no logger um resumo da rodada de conferência."""
    total = relatorio.total_verificados
    erros = relatorio.total_com_erros
    corr = relatorio.total_corrigidos
    incorr = relatorio.total_incorrigiveis

    if erros == 0:
        msg = (
            f"\n✅  Conferência concluída — {total} ofício(s) verificado(s), "
            f"nenhum erro encontrado."
        )
        q.put(("log", msg, "success"))
    else:
        partes = [
            f"{total} verificado(s)",
            f"{erros} com erro(s)",
            f"{corr} corrigido(s)",
        ]
        if incorr:
            partes.append(f"{incorr} incorrigível(is)")
        tag = "warn" if incorr else "success"
        msg = "\n📋  Conferência concluída — " + ", ".join(partes) + "."
        q.put(("log", msg, tag))
