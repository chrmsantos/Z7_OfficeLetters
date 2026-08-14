"""Tests for z7_officeletters.core.logging_setup."""

from __future__ import annotations

import json
import logging
import sys
import threading
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import z7_officeletters.core.logging_setup as _ls_mod
from z7_officeletters.core.logging_setup import (
    SESSAO_ID,
    configurar_logging,
    log_operation,
    logger,
    registrar_chamada_ia,
)


# =============================================================================
# configurar_logging
# =============================================================================
class TestConfigurarLogging:

    def setup_method(self) -> None:
        logger.handlers.clear()

    def teardown_method(self) -> None:
        logger.handlers.clear()
        sys.excepthook = sys.__excepthook__

    def test_cria_arquivo_de_log(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_ls_mod, "PASTA_LOGS", str(tmp_path))
        assert Path(configurar_logging()).exists()

    def test_nome_arquivo_contem_sessao_id(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_ls_mod, "PASTA_LOGS", str(tmp_path))
        assert SESSAO_ID in configurar_logging()

    def test_usa_rotating_file_handler(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_ls_mod, "PASTA_LOGS", str(tmp_path))
        configurar_logging()
        rfhs = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
        assert len(rfhs) == 1

    def test_rotating_handler_max_bytes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_ls_mod, "PASTA_LOGS", str(tmp_path))
        configurar_logging()
        fh = next(h for h in logger.handlers if isinstance(h, RotatingFileHandler))
        assert fh.maxBytes == 2 * 1024 * 1024

    def test_rotating_handler_backup_count(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_ls_mod, "PASTA_LOGS", str(tmp_path))
        configurar_logging()
        fh = next(h for h in logger.handlers if isinstance(h, RotatingFileHandler))
        assert fh.backupCount == 5

    def test_console_level_warning_por_padrao(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_ls_mod, "PASTA_LOGS", str(tmp_path))
        configurar_logging(verbose=False)
        stream_hs = [
            h for h in logger.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)
        ]
        assert stream_hs[0].level == logging.WARNING

    def test_console_level_info_quando_verbose(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_ls_mod, "PASTA_LOGS", str(tmp_path))
        configurar_logging(verbose=True)
        stream_hs = [
            h for h in logger.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)
        ]
        assert stream_hs[0].level == logging.INFO

    def test_chamadas_repetidas_nao_duplicam_handlers(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_ls_mod, "PASTA_LOGS", str(tmp_path))
        configurar_logging()
        configurar_logging()
        assert len(logger.handlers) == 2  # 1 file + 1 console

    def test_excepthook_instalado(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_ls_mod, "PASTA_LOGS", str(tmp_path))
        configurar_logging()
        assert sys.excepthook is not sys.__excepthook__

    def test_excepthook_delega_keyboard_interrupt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_ls_mod, "PASTA_LOGS", str(tmp_path))
        configurar_logging()
        with patch("sys.__excepthook__") as mock_orig:
            sys.excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)
            mock_orig.assert_called_once()

    def test_excepthook_loga_excecao_nao_tratada(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_ls_mod, "PASTA_LOGS", str(tmp_path))
        configurar_logging()
        with patch.object(logger, "critical") as mock_crit:
            try:
                raise RuntimeError("erro de teste")
            except RuntimeError:
                sys.excepthook(*sys.exc_info())
            mock_crit.assert_called_once()

    def test_mensagem_debug_gravada_no_arquivo(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_ls_mod, "PASTA_LOGS", str(tmp_path))
        log_path = configurar_logging()
        logger.debug("mensagem-debug-xyz")
        assert "mensagem-debug-xyz" in Path(log_path).read_text(encoding="utf-8")

    def test_sessao_id_aparece_nas_linhas_de_log(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_ls_mod, "PASTA_LOGS", str(tmp_path))
        log_path = configurar_logging()
        logger.info("linha qualquer")
        assert SESSAO_ID in Path(log_path).read_text(encoding="utf-8")

    def test_thread_excepthook_instalado(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import threading
        monkeypatch.setattr(_ls_mod, "PASTA_LOGS", str(tmp_path))
        orig_hook = getattr(threading, "excepthook", None)
        try:
            configurar_logging()
            assert threading.excepthook is not orig_hook
        finally:
            if orig_hook:
                threading.excepthook = orig_hook

    def test_thread_excepthook_loga_excecao(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import threading
        monkeypatch.setattr(_ls_mod, "PASTA_LOGS", str(tmp_path))
        configurar_logging()
        
        with patch.object(logger, "critical") as mock_crit:
            class DummyThread:
                name = "Thread-Teste"
            
            args = threading.ExceptHookArgs(
                (RuntimeError, RuntimeError("erro de teste thread"), None, DummyThread())
            )
            threading.excepthook(args)
            mock_crit.assert_called_once()
            call_args = mock_crit.call_args[0]
            assert "Thread-Teste" in call_args[1]

    def test_limpa_logs_antigos(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import os
        import time
        from datetime import datetime, timedelta
        
        pasta_logs = tmp_path / "logs"
        pasta_ia = tmp_path / "logs_ia"
        pasta_logs.mkdir()
        pasta_ia.mkdir()
        
        monkeypatch.setattr(_ls_mod, "PASTA_LOGS", str(pasta_logs))
        monkeypatch.setattr(_ls_mod, "PASTA_LOG_IA", str(pasta_ia))
        
        old_log = pasta_logs / "old.log"
        new_log = pasta_logs / "new.log"
        old_ia = pasta_ia / "old.jsonl"
        new_ia = pasta_ia / "new.jsonl"
        
        old_log.touch()
        new_log.touch()
        old_ia.touch()
        new_ia.touch()
        
        past_time = time.time() - (31 * 24 * 3600)
        os.utime(str(old_log), (past_time, past_time))
        os.utime(str(old_ia), (past_time, past_time))
        
        _ls_mod._limpar_logs_antigos()
        
        assert not old_log.exists()
        assert not old_ia.exists()
        assert new_log.exists()
        assert new_ia.exists()

    def test_log_file_path_atribuido_corretamente(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify that configurar_logging sets the module-level log_file_path."""
        monkeypatch.setattr(_ls_mod, "PASTA_LOGS", str(tmp_path))
        path = configurar_logging()
        assert _ls_mod.log_file_path == path

    def test_context_filter_em_handlers(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify that the context filter is attached to all handlers."""
        monkeypatch.setattr(_ls_mod, "PASTA_LOGS", str(tmp_path))
        configurar_logging()
        for handler in logger.handlers:
            filtros = [f for f in handler.filters if isinstance(f, _ls_mod._ContextFilter)]
            assert len(filtros) == 1, f"Handler {handler} missing _ContextFilter"


# =============================================================================
# _ContextFilter
# =============================================================================
class TestContextFilter:

    def test_injeta_sessao_id(self) -> None:
        record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)
        filtro = _ls_mod._ContextFilter()
        filtro.filter(record)
        assert record.sessao_id == SESSAO_ID  # type: ignore[attr-defined]

    def test_injeta_python_version(self) -> None:
        record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)
        filtro = _ls_mod._ContextFilter()
        filtro.filter(record)
        expected = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        assert record.python_version == expected  # type: ignore[attr-defined]

    def test_injeta_is_frozen(self) -> None:
        record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)
        filtro = _ls_mod._ContextFilter()
        filtro.filter(record)
        assert record.is_frozen == getattr(sys, "frozen", False)  # type: ignore[attr-defined]

    def test_sempre_retorna_true(self) -> None:
        record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)
        filtro = _ls_mod._ContextFilter()
        assert filtro.filter(record) is True


# =============================================================================
# _escrever_jsonl
# =============================================================================
class TestEscreverJsonl:

    def setup_method(self) -> None:
        _ls_mod.ia_log_path = ""

    def test_escreve_jsonl_no_arquivo(self, tmp_path: Path) -> None:
        caminho = str(tmp_path / "test.jsonl")
        record = {"teste": 1, "nome": "ação"}
        _ls_mod._escrever_jsonl(caminho, record)
        conteudo = Path(caminho).read_text(encoding="utf-8").strip()
        assert json.loads(conteudo) == record

    def test_escreve_multiplas_linhas(self, tmp_path: Path) -> None:
        caminho = str(tmp_path / "test.jsonl")
        for i in range(3):
            _ls_mod._escrever_jsonl(caminho, {"idx": i})
        linhas = Path(caminho).read_text(encoding="utf-8").strip().split("\n")
        assert len(linhas) == 3
        assert json.loads(linhas[0]) == {"idx": 0}
        assert json.loads(linhas[2]) == {"idx": 2}

    @patch("builtins.open", side_effect=OSError("disk full"))
    def test_falha_de_io_nao_explode(self, mock_open: MagicMock) -> None:
        _ls_mod._escrever_jsonl("/fake/path.jsonl", {"x": 1})

    def test_usa_lock(self) -> None:
        assert isinstance(_ls_mod._jsonl_lock, type(threading.Lock()))


# =============================================================================
# registrar_chamada_ia
# =============================================================================
class TestRegistrarChamadaIa:

    def setup_method(self) -> None:
        _ls_mod.SESSAO_ID = uuid.uuid4().hex[:8]
        _ls_mod.ia_log_path = ""
        logger.setLevel(logging.DEBUG)

    def test_nao_faz_nada_sem_log_path(self) -> None:
        _ls_mod.ia_log_path = ""
        registrar_chamada_ia({"teste": 1})

    def test_grava_registro_no_arquivo(self, tmp_path: Path) -> None:
        caminho = str(tmp_path / "ia.jsonl")
        _ls_mod.ia_log_path = caminho
        record = {"tipo": "chamada_ia", "prompt": "teste"}
        registrar_chamada_ia(record)
        conteudo = Path(caminho).read_text(encoding="utf-8").strip()
        assert json.loads(conteudo) == record


# =============================================================================
# log_operation
# =============================================================================
class TestLogOperation:

    def setup_method(self) -> None:
        logger.setLevel(logging.DEBUG)

    def test_sem_excecao_registra_duracao(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.DEBUG, logger="z7_officeletters"):
            with log_operation("teste_op"):
                pass
        assert any("teste_op" in r.message for r in caplog.records)
        assert any("finalizada" in r.message for r in caplog.records)

    def test_com_excecao_registra_duracao(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.DEBUG, logger="z7_officeletters"):
            with pytest.raises(ValueError):
                with log_operation("op_erro"):
                    raise ValueError("boom")
        assert any("op_erro" in r.message for r in caplog.records)

    def test_contexto_extra_no_log(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.DEBUG, logger="z7_officeletters"):
            with log_operation("op_ctx") as ctx:
                ctx["arquivos"] = 5
        assert any("arquivos=5" in r.message for r in caplog.records)

    def test_nivel_padrao_debug(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.DEBUG, logger="z7_officeletters"):
            with log_operation("op_debug"):
                pass
        assert any(r.levelno == logging.DEBUG for r in caplog.records)

    def test_yield_dict_vazio(self) -> None:
        with log_operation("op") as ctx:
            assert isinstance(ctx, dict)
            assert len(ctx) == 0
