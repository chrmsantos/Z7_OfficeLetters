"""Background processing worker.

Runs the full pipeline (read → AI extraction → docx generation → xlsx export)
in a daemon thread, posting progress and result messages to a ``queue.Queue``
that the main thread polls.

Message format
--------------
All messages are tuples whose first element is a ``str`` tag:

``("log", text, tag)``
    Append a line to the log panel.  ``tag`` is one of the colour tags
    registered on the CTkTextbox (``"success"``, ``"error"``, ``"warn"``,
    ``"dim"``, ``"accent"``, ``"bold"``), or an empty string for plain text.

``("progress", current, total)``
    Update the progress bar.

``("done", generated, errors, elapsed_seconds)``
    Processing finished successfully.

``("cancelled", done_so_far, total)``
    Processing was cancelled by the user.

``("error", message)``
    A fatal, unrecoverable error occurred.

Public exports:
    run_processing_worker: Start the worker thread.
"""

from __future__ import annotations

import os
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Any

from z7_officeletters.constants import MODELO_OFICIO, MODELO_REQUERIMENTO_PESAR, MODELO_PLANILHA, ENDERECAMENTO_PADRAO, PASTA_SAIDA, PASTA_PLANILHA, RE_PROPOSITURA_SPLIT, detectar_tipo_propositura, numero_propositura
from z7_officeletters.core import ai as _ai
from z7_officeletters.core import address_db as _addr_db
from z7_officeletters.core import authors as _authors
from z7_officeletters.core import documents as _docs
from z7_officeletters.core import files as _files
from z7_officeletters.core import recipients as _recipients
from z7_officeletters.core import verification as _verification
from z7_officeletters.core.api_key import salvar_api_key
from z7_officeletters.core.logging_setup import configurar_logging, registrar_conferencia_ia

__all__ = ["run_processing_worker"]


def _normalizar_dest(nome: str) -> str:
    """Normalize a recipient name to a stable grouping key (uppercase, collapsed whitespace)."""
    return " ".join(nome.upper().split())


def _formatar_lista_pt(items: list[str]) -> str:
    """Format a list of strings in Portuguese style, deduplicating while preserving order.

    Examples:
        ``["a"]`` → ``"a"``
        ``["a", "b"]`` → ``"a e b"``
        ``["a", "b", "c"]`` → ``"a, b e c"``
    """
    unique: list[str] = list(dict.fromkeys(items))
    if len(unique) == 1:
        return unique[0]
    return ", ".join(unique[:-1]) + " e " + unique[-1]


def _frases_propositura(
    tipo_propositura: str,
    tipo_mocao_merged: str,
    n_props: int,
) -> tuple[str, str, str]:
    """Return plural-aware phrase fragments for the letter template.

    Args:
        tipo_propositura: ``"mocao"`` or ``"requerimento_pesar"``.
        tipo_mocao_merged: Merged motion type string (e.g. ``"Aplauso"``).
            Ignored when *tipo_propositura* is ``"requerimento_pesar"``.
        n_props: Number of propositions grouped in this letter.

    Returns:
        A three-tuple ``(designacao_propositura, copia_art, aprovada_s)``
        where:
        - *designacao_propositura* — full noun phrase, e.g. ``"Moção de Aplauso"``
          or ``"Moções de Aplauso"``.
        - *copia_art* — contracted article phrase, e.g. ``"cópia da"`` or
          ``"cópias das"``.
        - *aprovada_s* — past-participle agreement, ``"aprovada"`` /
          ``"aprovadas"`` / ``"aprovado"`` / ``"aprovados"``.
    """
    if tipo_propositura == "requerimento_pesar":
        if n_props > 1:
            return "Requerimentos de Pesar", "cópias dos", "aprovados"
        return "Requerimento de Pesar", "cópia do", "aprovado"
    # moção
    if n_props > 1:
        return f"Moções de {tipo_mocao_merged}", "cópias das", "aprovadas"
    return f"Moção de {tipo_mocao_merged}", "cópia da", "aprovada"


def _aplicar_tratamento_db(info: dict, tratamento: str) -> None:
    """Override tratamento_rodape and honorifics in *info* from a DB tratamento line.

    Called after ``processar_destinatario`` when the address database
    provides a more authoritative tratamento string.

    Args:
        info: ``DestinatarioProcessado`` dict (mutated in place).
        tratamento: Raw tratamento line from the address database.
    """
    t = tratamento.strip()
    t_lower = t.lower()
    if "excelê" in t_lower or "excelencia" in t_lower.encode("ascii", "ignore").decode():
        info["tratamento_rodape"] = t
        info["pronome_corpo"] = "Vossa Excelência"
        info["vocativo"] = (
            "Excelentíssima Senhora" if "senhora" in t_lower else "Excelentíssimo Senhor"
        )
    elif "cuidados" in t_lower:
        info["tratamento_rodape"] = t
        info["vocativo"] = "Ilustríssimos Senhores(as)"
        info["pronome_corpo"] = "Vossas Senhorias"
    else:
        info["tratamento_rodape"] = t
        # When the DB tratamento encodes a gendered honorific (e.g. "À Ilustríssima
        # Senhora" or "Ao Ilustríssimo Senhor"), sync vocativo/pronome_corpo so that
        # a wrong gender from the AI does not bleed through into the final letter.
        t_ascii = t_lower.encode("ascii", "ignore").decode()
        if "ilustrissima" in t_ascii or (
            "senhora" in t_lower and "senhori" not in t_lower
        ):
            info["vocativo"] = "Ilustríssima Senhora"
            info["pronome_corpo"] = "Vossa Senhoria"
        elif "ilustrissimo" in t_ascii or (
            "senhor" in t_lower
            and "senhora" not in t_lower
            and "senhori" not in t_lower
        ):
            info["vocativo"] = "Ilustríssimo Senhor"
            info["pronome_corpo"] = "Vossa Senhoria"


def _worker_main(
    inputs: dict[str, Any],
    q: "queue.Queue[tuple[Any, ...]]",
    cancel_event: threading.Event,
) -> None:
    """Main worker body — executed in a daemon thread."""
    try:
        from google import genai  # noqa: PLC0415
        from docxtpl import DocxTemplate  # noqa: PLC0415
        from openpyxl import Workbook, load_workbook  # noqa: PLC0415

        log_path = configurar_logging()
        q.put(("log", f"📋  Log: {log_path}", "dim"))

        salvar_api_key(inputs["api_key"])
        cliente = genai.Client(api_key=inputs["api_key"])

        model_input_limit = 0
        try:
            _model_info = cliente.models.get(model=_ai.MODELO_IA)
            model_input_limit = int(_model_info.input_token_limit or 0)
        except Exception:  # noqa: BLE001
            pass

        arquivos_proc: list[str] = inputs["arquivos"]
        todos_textos: list[tuple[str, str]] = []
        for arq in arquivos_proc:
            q.put(("log", f"📂  Lendo: {Path(arq).name}", "accent"))
            conteudo = _files.ler_arquivo_mocoes(arq)
            textos_arq = RE_PROPOSITURA_SPLIT.split(conteudo)
            for t in textos_arq:
                t = t.strip()
                if t and RE_PROPOSITURA_SPLIT.match(t):
                    todos_textos.append((t, detectar_tipo_propositura(t)))

        proposituras = sorted(
            todos_textos,
            key=lambda item: (0 if item[1] == "requerimento_pesar" else 1, numero_propositura(item[0])),
        )
        total = len(proposituras)
        n_mocoes = sum(1 for _, tp in proposituras if tp == "mocao")
        n_pesar = sum(1 for _, tp in proposituras if tp == "requerimento_pesar")
        partes = []
        if n_mocoes:
            partes.append(f"{n_mocoes} moção(oes)")
        if n_pesar:
            partes.append(f"{n_pesar} requerimento(s) de pesar")
        resumo = " e ".join(partes) if partes else f"{total} propositura(s)"
        q.put(("log", f"\n❆  {resumo} encontrada(s). Iniciando IA…\n", "bold"))
        q.put(("progress", 0, total))

        Path(PASTA_SAIDA).mkdir(parents=True, exist_ok=True)

        _app_root = (
            Path(sys.executable).parent
            if getattr(sys, "frozen", False)
            else Path(__file__).parent.parent.parent.parent.parent
        )
        _meipass = Path(getattr(sys, "_MEIPASS", ""))

        def _resolve_template(rel: str) -> Path:
            p = _app_root / rel
            if not p.exists() and getattr(sys, "frozen", False):
                p = _meipass / rel
            return p

        modelo_oficio = _resolve_template(MODELO_OFICIO)
        modelo_requerimento_pesar = _resolve_template(MODELO_REQUERIMENTO_PESAR)

        # Address DB — optional; the app degrades gracefully when absent.
        _db_path = _resolve_template(ENDERECAMENTO_PADRAO)
        if _db_path.exists():
            q.put(("log", f"📒  Base de endereçamentos: {_db_path.name}", "dim"))
            _addr_db.buscar_endereco("__warmup__", db_path=_db_path)  # prime cache
        else:
            _db_path = None  # type: ignore[assignment]
            q.put(("log", "  ⚠  enderecam_padrao.docx não encontrado — usando apenas dados da IA.", "warn"))

        if not modelo_oficio.exists():
            q.put(("error", f"Arquivo 'modelo_mocao.docx' não encontrado.\n{modelo_oficio}"))
            return

        dados_planilha: list[list[str]] = []
        numero_atual: int = inputs["num_inicial"]
        year: int = int(inputs["data_iso"][:4])
        erros = 0
        inicio = time.time()
        total_prompt_tokens = 0
        total_candidates_tokens = 0
        total_tokens = 0
        registros_verificacao: list[_verification.RegistroOficio] = []

        # ── Phase 1: AI extraction ────────────────────────────────────────────
        # Process each propositura individually; collect validated data dicts.
        extracted: list[tuple[str, dict]] = []  # (tipo_propositura, dados)

        for i, (texto, tipo_propositura) in enumerate(proposituras, 1):
            if cancel_event.is_set():
                q.put(("cancelled", i - 1, total, "proposituras"))
                return

            q.put(("log", f"─── Propositura {i}/{total} ─────────────────────────────", "dim"))
            q.put(("progress", i - 1, total))

            try:
                dados = _ai.extrair_dados_com_ia(
                    texto, cliente,
                    tipo_propositura=tipo_propositura,
                    cancel_event=cancel_event,
                )
            except RuntimeError as exc:
                if cancel_event.is_set():
                    q.put(("cancelled", i - 1, total, "proposituras"))
                    return
                q.put(("log", f"  ✖  Erro: {exc}", "error"))
                erros += 1
                continue
            except Exception as exc:  # noqa: BLE001
                q.put(("log", f"  ✖  Erro: {exc}", "error"))
                erros += 1
                continue

            usage = dados.pop("_usage", {"prompt_tokens": 0, "candidates_tokens": 0, "total_tokens": 0})
            alertas_ia = dados.pop("_alertas", [])
            total_prompt_tokens += usage["prompt_tokens"]
            total_candidates_tokens += usage["candidates_tokens"]
            total_tokens += usage["total_tokens"]
            if usage["total_tokens"]:
                _saldo_str = (
                    f"  |  saldo: {(model_input_limit - usage['prompt_tokens']):,}"
                    if model_input_limit else ""
                )
                q.put(("log",
                    f"  🔢  Tokens: {usage['total_tokens']:,} "
                    f"(entrada: {usage['prompt_tokens']:,} | saída: {usage['candidates_tokens']:,}){_saldo_str}",
                    "dim"))
            for alerta in alertas_ia:
                q.put(("log", f"  ⚠  {alerta}", "warn"))

            # Normalise motion/requerimento number to just the numeric part.
            num_raw = dados.get("numero_requerimento") or dados.get("numero_mocao", "")
            dados["numero_mocao"] = _docs.normalizar_numero_mocao(str(num_raw))
            extracted.append((tipo_propositura, dados))

        # ── Phase 2: group by (tipo_propositura, recipient) ───────────────────
        # When multiple propositions share the same recipient, they are merged
        # into a single office letter so that one ofício covers all of them.
        #
        # Key:   (tipo_propositura, normalized_dest_name)
        # Value: list of (dados, raw_dest_dict, processed_info) triples
        grupos: dict[tuple[str, str], list[tuple[dict, dict, dict]]] = {}

        for tipo_propositura, dados in extracted:
            for dest in dados["destinatarios"]:
                # Enrich recipient data: DB (priority 1) > propositura (priority 2)
                dest_proc = dict(dest)  # shallow copy to avoid mutating AI data
                db_entry = _addr_db.buscar_endereco(dest["nome"], db_path=_db_path)
                if db_entry:
                    # DB is the most authoritative source — override all fields it supplies.
                    dest_proc["nome"] = db_entry.nome
                    if db_entry.cargo:
                        dest_proc["cargo_ou_tratamento"] = db_entry.cargo
                    if db_entry.endereco:
                        dest_proc["endereco"] = db_entry.endereco
                    if db_entry.email:
                        dest_proc["email"] = db_entry.email

                info = _recipients.processar_destinatario(dest_proc)

                # Override honorifics when DB supplies a richer tratamento string.
                if db_entry:
                    _aplicar_tratamento_db(info, db_entry.tratamento)

                dest_key = (tipo_propositura, _normalizar_dest(dest["nome"]))
                if dest_key not in grupos:
                    grupos[dest_key] = []
                grupos[dest_key].append((dados, dest, info))

        n_grupos = len(grupos)
        q.put(("progress", total, total))
        if n_grupos:
            q.put(("log", f"\n📬  {n_grupos} ofício(s) a gerar após agrupamento...\n", "bold"))

        # ── Phase 3: generate one letter per group ────────────────────────────
        for dest_key, grupo in grupos.items():
            if cancel_event.is_set():
                q.put(("cancelled", len(dados_planilha), n_grupos, "ofícios"))
                return

            tipo_propositura = dest_key[0]
            n_props = len(grupo)

            # Merge proposition data from every item in the group.
            all_autores: list[str] = []
            for d_item, _dest_raw, _info_item in grupo:
                for a in d_item["autores"]:
                    if a not in all_autores:
                        all_autores.append(a)
            texto_autoria, sigla_autores = _authors.formatar_autores(all_autores)

            nums_mocao = [d_item["numero_mocao"] for d_item, _, __ in grupo]
            num_mocao_merged = _formatar_lista_pt(nums_mocao)

            tipos_mocao = [
                str(d_item.get("tipo_mocao", ""))
                for d_item, _, __ in grupo
                if d_item.get("tipo_mocao")
            ]
            tipo_mocao_merged = _formatar_lista_pt(tipos_mocao) if tipos_mocao else ""

            falecidos = [
                str(d_item.get("falecido", ""))
                for d_item, _, __ in grupo
                if d_item.get("falecido")
            ]
            falecido_merged = _formatar_lista_pt(falecidos) if falecidos else ""

            # Recipient info is identical for all items in the group
            # (they share the same destination); use the first entry.
            _dados0, dest0, info = grupo[0]

            if n_props > 1:
                q.put(("log",
                    f"─── Ofício nº {numero_atual:03d} — {dest_key[1]} "
                    f"({n_props} proposituras agrupadas) ───",
                    "dim"))
            else:
                q.put(("log",
                    f"─── Ofício nº {numero_atual:03d} — {dest_key[1]} ─────────────────────────────",
                    "dim"))

            num_str = f"{numero_atual:03d}"
            sigla_redator = inputs["sigla"]

            # Plural-aware phrase fragments used by both templates.
            # These allow the assunto line and body paragraph to read correctly
            # regardless of whether one or many propositions are grouped.
            _designacao_prop, _copia_art, _aprovada_s = _frases_propositura(
                tipo_propositura, tipo_mocao_merged, n_props
            )

            ctx: dict[str, str] = {
                "num_oficio":            num_str,
                "data_extenso":          inputs["data_extenso"],
                "tipo_mocao":            tipo_mocao_merged,
                "num_mocao":             num_mocao_merged,
                "falecido":              falecido_merged,
                "tipo_propositura":      tipo_propositura,
                "sigla_redator":         sigla_redator,
                "vocativo":              info["vocativo"],
                "pronome_corpo":         info["pronome_corpo"],
                "texto_autoria":         texto_autoria,
                "tratamento_rodape":     info["tratamento_rodape"],
                "destinatario_nome":     info["destinatario_nome"],
                "destinatario_endereco": info["destinatario_endereco"],
                "designacao_propositura": _designacao_prop,
                "copia_art":             _copia_art,
                "aprovada_s":            _aprovada_s,
                # Uppercase aliases for Word template placeholders
                "NUM_OFICIO":            num_str,
                "DATA_EXTENSO":          inputs["data_extenso"],
                "TIPO_MOCAO":            tipo_mocao_merged,
                "NUM_MOCAO":             num_mocao_merged,
                "FALECIDO":              falecido_merged,
                "TIPO_PROPOSITURA":      tipo_propositura,
                "SIGLA_REDATOR":         sigla_redator,
                "VOCATIVO":              info["vocativo"],
                "PRONOME_CORPO":         info["pronome_corpo"],
                "TEXTO_AUTORIA":         texto_autoria,
                "TRATAMENTO_RODAPE":     info["tratamento_rodape"],
                "DESTINATARIO_NOME":     info["destinatario_nome"],
                "DESTINATARIO_ENDERECO": info["destinatario_endereco"],
                "DESIGNACAO_PROPOSITURA": _designacao_prop,
                "COPIA_ART":             _copia_art,
                "APROVADA_S":            _aprovada_s,
            }

            if tipo_propositura == "requerimento_pesar":
                ctx["vocativo"]           = "Ilustríssimos Senhores(as)"
                ctx["VOCATIVO"]           = "Ilustríssimos Senhores(as)"
                ctx["pronome_corpo"]      = "Vossas Senhorias"
                ctx["PRONOME_CORPO"]      = "Vossas Senhorias"
                ctx["tratamento_rodape"]  = "Aos familiares do Sr.(ª),"
                ctx["TRATAMENTO_RODAPE"]  = "Aos familiares do Sr.(ª),"
                ctx["destinatario_nome"]  = falecido_merged.upper()
                ctx["DESTINATARIO_NOME"]  = falecido_merged.upper()

                _tmpl = modelo_requerimento_pesar
                if not _tmpl.exists():
                    q.put(("log",
                        f"  ⚠  Template 'modelo_requer_pesar.docx' não encontrado — "
                        f"usando modelo_mocao.docx como fallback.",
                        "warn"))
                    _tmpl = modelo_oficio
            else:
                _tmpl = modelo_oficio

            doc = DocxTemplate(str(_tmpl))
            doc.render(ctx)

            nome = _docs.construir_nome_arquivo(
                num_str,
                inputs["sigla"],
                tipo_mocao_merged,
                num_mocao_merged,
                info["envio"],
                dest0["nome"],
                sigla_autores,
                ano=year,
                tipo_propositura=tipo_propositura,
            )
            caminho_oficio = os.path.join(PASTA_SAIDA, nome)
            doc.save(caminho_oficio)
            q.put(("log", f"  ✔  {nome}", "success"))

            if tipo_propositura == "requerimento_pesar":
                plural_s = "s" if n_props > 1 else ""
                assunto = f"Encaminha Requerimento{plural_s} de Pesar nº {num_mocao_merged}/{year}"
            else:
                plural_oes = "ões" if n_props > 1 else "ão"
                assunto = f"Encaminha Mo{plural_oes} de {tipo_mocao_merged} nº {num_mocao_merged}/{year}"

            dados_planilha.append([
                num_str,
                inputs["data_iso"],
                f"{info['tratamento_rodape']} {info['destinatario_nome']}".strip(),
                assunto,
                ", ".join(
                    f"{a} ({_authors.sigla_autor(a)})" for a in all_autores
                ),
                info["envio"],
                inputs["sigla"],
            ])

            # Register this letter for Phase 6 verification.
            registros_verificacao.append(_verification.RegistroOficio(
                caminho=caminho_oficio,
                nome_arquivo=nome,
                ctx=dict(ctx),
                dados_grupo=[d for d, _, __ in grupo],
                dest_raw=dict(dest0),
                info=dict(info),
                n_props=n_props,
                tipo_propositura=tipo_propositura,
                template_path=str(_tmpl),
                linha_planilha_idx=len(dados_planilha) - 1,
            ))

            numero_atual += 1

        # ── Phase 5: Verification (conference) ───────────────────────────────
        # Runs before the spreadsheet is written to disk so that any corrections
        # to dados_planilha rows are reflected in the final .xlsx file.
        if registros_verificacao:
            relatorio_conf = _verification.conferir_trabalho(
                registros_verificacao, dados_planilha, q
            )
            registrar_conferencia_ia(relatorio_conf)
            erros += relatorio_conf.total_incorrigiveis

        # ── Phase 6: Excel spreadsheet ────────────────────────────────────────
        q.put(("log", "\n📊  Gerando planilha Excel…", "accent"))
        if getattr(sys, "frozen", False):
            modelo_xlsx = Path(sys.executable).parent / MODELO_PLANILHA
        else:
            modelo_xlsx = Path(__file__).parent.parent.parent.parent.parent / MODELO_PLANILHA

        if modelo_xlsx.exists():
            wb = load_workbook(str(modelo_xlsx))
            ws = wb.active
            assert ws is not None
        else:
            wb = Workbook()
            ws = wb.active
            assert ws is not None
            ws.append(["Of. n.º", "Data", "Destinatário", "Assunto", "Vereador", "Envio", "Autor"])

        ws.title = f"Controle {year}"
        for row in dados_planilha:
            ws.append(row)

        Path(PASTA_PLANILHA).mkdir(parents=True, exist_ok=True)
        wb.save(os.path.join(PASTA_PLANILHA, "CONTROLE_OFICIOS.xlsx"))

        elapsed = time.time() - inicio
        if total_tokens:
            q.put(("log",
                f"\n🔢  Tokens consumidos: {total_tokens:,} total "
                f"(entrada: {total_prompt_tokens:,} | saída: {total_candidates_tokens:,})",
                "accent"))
        q.put(("done", len(dados_planilha), erros, elapsed, total_tokens))

    except Exception as exc:  # noqa: BLE001
        q.put(("error", str(exc)))


def run_processing_worker(
    inputs: dict[str, Any],
    q: "queue.Queue[tuple[Any, ...]]",
    cancel_event: threading.Event,
) -> threading.Thread:
    """Start the processing worker in a background daemon thread.

    Args:
        inputs: Processing parameters with keys ``num_inicial``, ``sigla``,
            ``data_extenso``, ``data_iso``, ``arquivos``, and ``api_key``.
        q: Queue to post progress/result messages on.
        cancel_event: Event that, when set, requests graceful cancellation.

    Returns:
        The started ``Thread`` instance.
    """
    t = threading.Thread(
        target=_worker_main,
        args=(inputs, q, cancel_event),
        daemon=True,
    )
    t.start()
    return t
