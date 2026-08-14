"""Logging configuration for Z7 OfficeLetters.

Provides a single ``configurar_logging()`` call that sets up rotating file
handlers, a console handler, a context filter that injects session metadata
into every log record, and a session-scoped unique identifier.

Public exports:
    SESSAO_ID: Short random hex string that identifies the current process run.
    logger: Module-level logger (name ``z7_officeletters``).
    ia_log_path: Absolute path of the per-session AI JSONL log file (empty
        string until ``configurar_logging`` is called).
    configurar_logging: Configures all handlers and returns the log file path.
    registrar_chamada_ia: Append one structured AI-call record to the AI log.
    registrar_conferencia_ia: Append one verification-phase record to the AI log.
    log_operation: Context manager that measures and logs operation duration.
"""

from __future__ import annotations

import json
import logging
import sys
import threading
import types
import uuid
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Iterator

from z7_officeletters.constants import PASTA_LOG_IA, PASTA_LOGS

__all__ = [
    "SESSAO_ID",
    "logger",
    "ia_log_path",
    "log_file_path",
    "configurar_logging",
    "registrar_chamada_ia",
    "registrar_conferencia_ia",
    "log_operation",
]

# Unique identifier for the current process run, embedded in every log line.
SESSAO_ID: str = uuid.uuid4().hex[:8]

logger: logging.Logger = logging.getLogger("z7_officeletters")

# Absolute path of the per-session AI JSONL log. Set by configurar_logging().
ia_log_path: str = ""

# Absolute path of the rotating .log file for this session. Set by configurar_logging().
log_file_path: str = ""

# Thread lock for JSONL file writing — prevents interleaved writes.
_jsonl_lock: threading.Lock = threading.Lock()


# ---------------------------------------------------------------------------
# Context filter — injects session metadata into every log record
# ---------------------------------------------------------------------------

class _ContextFilter(logging.Filter):
    """Inject ``sessao_id``, ``python_version`` and ``is_frozen`` into records.

    Attached to the root ``z7_officeletters`` logger so that every handler
    (file, console, and any future handlers) automatically carries this
    metadata.  Use ``%(sessao_id)s`` in formatters to include the value.
    """

    def __init__(self) -> None:
        super().__init__()
        self._python_version: str = (
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        )
        self._is_frozen: bool = getattr(sys, "frozen", False)

    def filter(self, record: logging.LogRecord) -> bool:
        record.sessao_id = SESSAO_ID  # type: ignore[attr-defined]
        record.python_version = self._python_version  # type: ignore[attr-defined]
        record.is_frozen = self._is_frozen  # type: ignore[attr-defined]
        return True


_CONTEXT_FILTRO = _ContextFilter()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

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
                            logger.debug("Log antigo removido: %s", arq)
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("Falha ao remover log antigo '%s': %s", arq, exc)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Falha ao listar pasta de logs '%s': %s", p, exc)


def _escrever_jsonl(caminho: str, record: dict[str, Any]) -> None:
    """Thread-safe append of a single JSON line to a JSONL file.

    Uses a module-level lock to prevent interleaved writes from concurrent
    threads.  Flushes the file handle after each write to ensure data is
    persisted even if the process crashes.

    Args:
        caminho: Absolute path of the JSONL file.
        record: Dictionary to serialize and append.
    """
    with _jsonl_lock:
        try:
            with open(caminho, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False, default=str))
                fh.write("\n")
                fh.flush()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Falha ao gravar JSONL em '%s': %s", caminho, exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

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
    file_handler.addFilter(_CONTEXT_FILTRO)

    console_level = logging.INFO if verbose else logging.WARNING
    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)

    if sys.stderr is not None:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(console_level)
        console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        console_handler.addFilter(_CONTEXT_FILTRO)
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
        thread_name = args.thread.name if args.thread else "desconhecida"
        logger.critical(
            "Exceção não tratada na thread '%s' — a thread será encerrada.",
            thread_name,
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    threading.excepthook = _thread_excepthook

    # Clean up old logs (retention policy: 30 days)
    _limpar_logs_antigos()

    log_file_path = log_path
    logger.debug("Sessão de log iniciada. ID=%s", SESSAO_ID)
    return log_path


@contextmanager
def log_operation(nome: str, nivel: int = logging.DEBUG) -> Iterator[dict[str, Any]]:
    """Measure and log the wall-clock duration of a code block.

    Usage::

        with log_operation("gerar_oficios") as ctx:
            # ... do work ...
            ctx["arquivos"] = 10

        # Automatically logs: "Operação 'gerar_oficios' finalizada em 3.42s [arquivos=10]"

    The context dict values are included in the log message as key=value pairs.

    Args:
        nome: Human-readable name for the operation (appears in the log line).
        nivel: Logging level used for the duration message. Default: DEBUG.

    Yields:
        A ``dict[str, Any]`` that the caller can populate with extra context.
    """
    import time as _time  # noqa: PLC0415

    ctx: dict[str, Any] = {}
    inicio = _time.monotonic()
    try:
        yield ctx
    finally:
        duracao = _time.monotonic() - inicio
        extras = " ".join(f"{k}={v}" for k, v in ctx.items())
        if duracao >= 60:
            nivel_final = logging.WARNING
        elif duracao >= 10:
            nivel_final = logging.INFO
        else:
            nivel_final = nivel
        tempo_fmt = f"{duracao:.2f}s" if duracao < 60 else f"{duracao / 60:.1f}min"
        if extras:
            logger.log(nivel_final, "Operação '%s' finalizada em %s [%s]", nome, tempo_fmt, extras)
        else:
            logger.log(nivel_final, "Operação '%s' finalizada em %s", nome, tempo_fmt)


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
    _escrever_jsonl(ia_log_path, record)


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
        _escrever_jsonl(ia_log_path, record)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Falha ao serializar relatório de conferência: %s", exc)
