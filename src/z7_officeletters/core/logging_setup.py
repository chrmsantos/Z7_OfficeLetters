"""Logging configuration for Z7 OfficeLetters.

Provides a single ``configurar_logging()`` call that sets up rotating file
handlers, a console handler, and a session-scoped unique identifier included
in every log record.

Public exports:
    SESSAO_ID: Short random hex string that identifies the current process run.
    logger: Module-level logger (name ``z7_officeletters``).
    ia_log_path: Absolute path of the per-session AI JSONL log file (empty
        string until ``configurar_logging`` is called).
    configurar_logging: Configures all handlers and returns the log file path.
    registrar_chamada_ia: Append one structured AI-call record to the AI log.
    registrar_conferencia_ia: Append one verification-phase record to the AI log.
"""

from __future__ import annotations

import json
import logging
import sys
import threading
import types
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from z7_officeletters.constants import PASTA_LOG_IA, PASTA_LOGS

__all__ = [
    "SESSAO_ID",
    "logger",
    "ia_log_path",
    "log_file_path",
    "configurar_logging",
    "registrar_chamada_ia",
    "registrar_conferencia_ia",
]

# Unique identifier for the current process run, embedded in every log line.
SESSAO_ID: str = uuid.uuid4().hex[:8]

logger: logging.Logger = logging.getLogger("z7_officeletters")

# Absolute path of the per-session AI JSONL log. Set by configurar_logging().
ia_log_path: str = ""

# Absolute path of the rotating .log file for this session. Set by configurar_logging().
log_file_path: str = ""


def _limpar_logs_antigos() -> None:
    """Remove log files and AI logs older than 30 days."""
    from datetime import datetime, timedelta  # noqa: PLC0415
    limite = datetime.now() - timedelta(days=30)
    
    for pasta_path in (PASTA_LOGS, PASTA_LOG_IA):
        p = Path(pasta_path)
        if not p.exists():
            continue
        try:
            for arq in p.iterdir():
                if arq.is_file() and arq.suffix in (".log", ".jsonl"):
                    try:
                        mtime = datetime.fromtimestamp(arq.stat().st_mtime)
                        if mtime < limite:
                            arq.unlink()
                    except Exception:  # noqa: BLE001
                        pass
        except Exception:  # noqa: BLE001
            pass


def configurar_logging(verbose: bool = False) -> str:
    """Configure rotating file and console log handlers.

    Sets up:
    - A ``RotatingFileHandler`` (DEBUG level, 2 MB, 5 backups) in
      ``PASTA_LOGS``.
    - A ``StreamHandler`` (WARNING by default; INFO when *verbose* is True).
    - A ``sys.excepthook`` that captures unhandled exceptions into the log.

    Calling this function multiple times is safe: existing handlers are cleared
    before new ones are added.

    Args:
        verbose: When True the console handler is raised to INFO level.

    Returns:
        Absolute path of the log file created in this session.
    """
    global ia_log_path, log_file_path
    # Prevent handler accumulation on repeated calls (e.g., during testing).
    logger.handlers.clear()

    Path(PASTA_LOGS).mkdir(parents=True, exist_ok=True)

    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = str(Path(PASTA_LOGS) / f"z7_officeletters_{timestamp}_{SESSAO_ID}.log")

    # Initialise the AI JSONL log path for this session.
    Path(PASTA_LOG_IA).mkdir(parents=True, exist_ok=True)
    ia_log_path = str(Path(PASTA_LOG_IA) / f"ia_{timestamp}_{SESSAO_ID}.jsonl")

    fmt = logging.Formatter(
        f"%(asctime)s [{SESSAO_ID}] [%(levelname)-8s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_path,
        encoding="utf-8",
        maxBytes=2 * 1024 * 1024,  # 2 MB per file
        backupCount=5,
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)

    console_level = logging.INFO if verbose else logging.WARNING
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))

    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    def _excepthook(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_tb: types.TracebackType | None,
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logger.critical(
            "Exceção não tratada — o processo será encerrado.",
            exc_info=(exc_type, exc_value, exc_tb),
        )

    sys.excepthook = _excepthook  # type: ignore[assignment]

    def _thread_excepthook(args: threading.ExceptHookArgs) -> None:
        logger.critical(
            f"Exceção não tratada na thread '{args.thread.name if args.thread else 'desconhecida'}' — a thread será encerrada.",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    threading.excepthook = _thread_excepthook

    # Clean up old logs (retention policy: 30 days)
    _limpar_logs_antigos()

    log_file_path = log_path
    logger.debug("Sessão de log iniciada. ID=%s", SESSAO_ID)
    return log_path


def registrar_chamada_ia(record: dict[str, Any]) -> None:
    """Append one AI-call record as a JSON line to the per-session AI log.

    The file is located at ``ia_log_path`` (set by :func:`configurar_logging`).
    Each line is a self-contained JSON object describing a single call to the
    Gemini API, including the full prompt, every raw response received (across
    all retry attempts), the final parsed data, token usage, and a list of
    soft-warning alerts about missing or unexpected fields.

    Silently does nothing if :func:`configurar_logging` has not yet been called
    (e.g. during unit tests that do not initialise logging).

    Args:
        record: Dict with at minimum the keys produced by
            :func:`~z7_officeletters.core.ai.extrair_dados_com_ia`.
    """
    if not ia_log_path:
        return
    try:
        with open(ia_log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=str))
            fh.write("\n")
    except Exception:  # noqa: BLE001
        pass


def registrar_conferencia_ia(relatorio: Any) -> None:
    """Append one verification-phase record as a JSON line to the per-session AI log.

    Records a ``RelatorioConferencia`` produced by
    :func:`~z7_officeletters.core.verification.conferir_trabalho` as a
    structured JSONL entry of type ``"conferencia"``.  The record includes
    the aggregate counters and the per-file results (errors found, whether
    correction succeeded, etc.).

    Silently does nothing if :func:`configurar_logging` has not yet been called
    (e.g. during unit tests that do not initialise logging).

    Args:
        relatorio: A :class:`~z7_officeletters.core.verification.RelatorioConferencia`
            instance (typed as ``Any`` here to avoid a circular import).
    """
    if not ia_log_path:
        return

    from datetime import datetime  # noqa: PLC0415

    try:
        resultados_serializados = [
            {
                "arquivo": r.arquivo,
                "erros_dados": r.erros_dados,
                "erros_linguisticos": r.erros_linguisticos,
                "erros_planilha": r.erros_planilha,
                "corrigido": r.corrigido,
                "incorrigivel": r.incorrigivel,
            }
            for r in relatorio.resultados
        ]
        record: dict[str, Any] = {
            "tipo": "conferencia",
            "timestamp": datetime.now().isoformat(timespec="milliseconds"),
            "sessao_id": SESSAO_ID,
            "total_verificados": relatorio.total_verificados,
            "total_com_erros": relatorio.total_com_erros,
            "total_corrigidos": relatorio.total_corrigidos,
            "total_incorrigiveis": relatorio.total_incorrigiveis,
            "resultados": resultados_serializados,
        }
        with open(ia_log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=str))
            fh.write("\n")
    except Exception:  # noqa: BLE001
        pass
