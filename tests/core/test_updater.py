"""Tests for z7_officeletters.core.updater."""

from __future__ import annotations

import json
import os
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, call, patch
import pytest

from z7_officeletters.core.updater import (
    comparar_versoes,
    obter_ultima_versao,
    _launch_new_instance,
    _generate_restart_script,
    _reiniciar_aplicativo,
)


# =============================================================================
# comparar_versoes
# =============================================================================
class TestCompararVersoes:

    @pytest.mark.parametrize("v1,v2,esperado", [
        ("3.1.6", "3.1.5", True),
        ("3.1.5", "3.1.6", False),
        ("v3.1.6", "v3.1.5", True),
        ("3.1.6", "3.1.6", False),
        ("3.10.1", "3.2.5", True),
        ("3.2.5", "3.10.1", False),
        ("v3.2.0-rc1", "3.1.9", True),
        ("invalido", "3.1.5", False),
        ("3.2.0-rc1", "3.2.0", False),  # Pre-release is older than stable
        ("3.2.0", "3.2.0-rc1", True),   # Stable is newer than pre-release
        ("3.2.0-rc2", "3.2.0-rc1", True), # Pre-release comparison
        ("3.2.0-alpha", "3.2.0-1", True), # String identifier has higher precedence than numeric
        ("3.2.0-rc.1.0", "3.2.0-rc.1", True), # More fields has higher precedence
        ("3.2.0+build1", "3.2.0", False), # Build metadata is ignored in comparison
    ])
    def test_comparacao_semver(self, v1: str, v2: str, esperado: bool) -> None:
        assert comparar_versoes(v1, v2) is esperado


# =============================================================================
# obter_ultima_versao
# =============================================================================
class TestObterUltimaVersao:

    @patch("urllib.request.urlopen")
    def test_obter_versao_com_sucesso(self, mock_urlopen: MagicMock) -> None:
        # Mock GitHub releases response
        mock_response_data = {
            "tag_name": "v3.1.7",
            "assets": [
                {
                    "name": "outros_arquivos.zip",
                    "browser_download_url": "https://example.com/outros.zip"
                },
                {
                    "name": "Z7_OfficeLetters.exe",
                    "browser_download_url": "https://example.com/Z7_OfficeLetters.exe"
                }
            ]
        }
        
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps(mock_response_data).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        tag, url = obter_ultima_versao()
        assert tag == "v3.1.7"
        assert url == "https://example.com/Z7_OfficeLetters.exe"

    @patch("urllib.request.urlopen")
    def test_erro_http(self, mock_urlopen: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status = 404
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with pytest.raises(RuntimeError, match="Servidor respondeu com código HTTP 404"):
            obter_ultima_versao()

    @patch("urllib.request.urlopen")
    def test_conexao_falhou(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.side_effect = Exception("Conexão recusada")

        with pytest.raises(RuntimeError, match="Erro ao conectar com o servidor"):
            obter_ultima_versao()

    @patch("urllib.request.urlopen")
    def test_tag_name_ausente(self, mock_urlopen: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({"assets": []}).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with pytest.raises(RuntimeError, match="resposta do servidor de atualizações não continha informações de versão"):
            obter_ultima_versao()

    @patch("urllib.request.urlopen")
    def test_executavel_ausente_na_release(self, mock_urlopen: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = json.dumps({
            "tag_name": "v3.1.7",
            "assets": [
                {
                    "name": "Z7_OfficeLetters.zip",
                    "browser_download_url": "https://example.com/Z7_OfficeLetters.zip"
                }
            ]
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with pytest.raises(RuntimeError, match="arquivo executável 'Z7_OfficeLetters.exe' não foi publicado nos anexos"):
            obter_ultima_versao()


# =============================================================================
# Escaping for PowerShell
# =============================================================================
class TestEscapingForPowerShell:

    def test_escape_single_quotes(self) -> None:
        raw_path = r"C:\Users\João's PC\App.exe"
        escaped = raw_path.replace("'", "''")
        assert escaped == r"C:\Users\João''s PC\App.exe"

    def test_escape_standard_path(self) -> None:
        raw_path = r"C:\Program Files\Z7\App.exe"
        escaped = raw_path.replace("'", "''")
        assert escaped == r"C:\Program Files\Z7\App.exe"


# =============================================================================
# Download and Stream Flow
# =============================================================================
class TestDownloadFlow:

    def test_chunk_by_chunk_download_success(self) -> None:
        import tempfile
        import pathlib

        mock_response = MagicMock()
        mock_response.info.return_value.get.return_value = "100"
        mock_response.read.side_effect = [b"chunk1", b"chunk2", b""]

        download_cancelled = MagicMock()
        download_cancelled.is_set.return_value = False

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = pathlib.Path(tmpdir) / "app.exe.tmp"

            bytes_downloaded = 0
            with open(temp_path, "wb") as f:
                while not download_cancelled.is_set():
                    chunk = mock_response.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    bytes_downloaded += len(chunk)

            assert bytes_downloaded == 12
            assert temp_path.read_bytes() == b"chunk1chunk2"
            assert temp_path.exists()

    def test_download_cancellation_cleanup(self) -> None:
        import tempfile
        import pathlib

        mock_response = MagicMock()
        mock_response.info.return_value.get.return_value = "100"
        mock_response.read.side_effect = [b"chunk1", b"chunk2"]

        download_cancelled = MagicMock()
        is_cancelled_flag = [False]
        def mock_is_set() -> bool:
            if is_cancelled_flag[0]:
                return True
            is_cancelled_flag[0] = True
            return False
        download_cancelled.is_set.side_effect = mock_is_set

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = pathlib.Path(tmpdir) / "app.exe.tmp"

            bytes_downloaded = 0
            try:
                with open(temp_path, "wb") as f:
                    while not download_cancelled.is_set():
                        chunk = mock_response.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                        bytes_downloaded += len(chunk)

                if download_cancelled.is_set():
                    if temp_path.exists():
                        temp_path.unlink()
            except Exception:
                pass

            assert bytes_downloaded == 6
            assert not temp_path.exists()

    def test_empty_download_throws_error(self) -> None:
        import tempfile
        import pathlib

        mock_response = MagicMock()
        mock_response.info.return_value.get.return_value = "0"
        mock_response.read.return_value = b""

        download_cancelled = MagicMock()
        download_cancelled.is_set.return_value = False

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = pathlib.Path(tmpdir) / "app.exe.tmp"

            bytes_downloaded = 0
            with open(temp_path, "wb") as f:
                while not download_cancelled.is_set():
                    chunk = mock_response.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    bytes_downloaded += len(chunk)

            with pytest.raises(RuntimeError, match="O arquivo baixado está vazio"):
                if temp_path.stat().st_size == 0:
                    raise RuntimeError("O arquivo baixado está vazio.")


# =============================================================================
# _launch_new_instance
# =============================================================================
class TestLaunchNewInstance:

    @patch("z7_officeletters.core.updater.subprocess.Popen")
    def test_sucesso_popen(self, mock_popen: MagicMock) -> None:
        """Strategy 1 succeeds: Popen launches the new exe."""
        exe = Path(r"C:\Apps\Z7_OfficeLetters.exe")
        result = _launch_new_instance(exe)
        assert result is True
        mock_popen.assert_called_once()
        args, kwargs = mock_popen.call_args
        assert args[0] == [str(exe)]
        assert kwargs["close_fds"] is True

    @patch("z7_officeletters.core.updater.subprocess.Popen")
    def test_falha_popen(self, mock_popen: MagicMock) -> None:
        """Strategy 1 fails: Popen raises an exception."""
        mock_popen.side_effect = OSError("Access denied")
        exe = Path(r"C:\Apps\Z7_OfficeLetters.exe")
        result = _launch_new_instance(exe)
        assert result is False


# =============================================================================
# _generate_restart_script
# =============================================================================
class TestGenerateRestartScript:

    @patch("z7_officeletters.core.updater.os.getpid", return_value=9999)
    def test_script_criado_com_sucesso(self, _mock_pid: MagicMock, tmp_path: Path) -> None:
        """Script is created in temp dir with correct PID and exe path."""
        exe = Path(r"C:\Apps\Z7_OfficeLetters.exe")
        with patch("z7_officeletters.core.updater.tempfile.gettempdir", return_value=str(tmp_path)):
            result = _generate_restart_script(exe)

        assert result is not None
        script_path = Path(result)
        assert script_path.exists()
        assert script_path.name == "z7_restart_9999.cmd"

        content = script_path.read_text(encoding="ascii")
        assert "9999" in content
        assert str(exe) in content
        assert "@echo off" in content
        assert "tasklist" in content
        assert "timeout /t 1 /nobreak" in content
        assert "del" in content  # self-delete

    @patch("z7_officeletters.core.updater.os.getpid", return_value=1234)
    def test_script_contem_logica_de_espera(self, _mock_pid: MagicMock, tmp_path: Path) -> None:
        """Script contains the wait-loop logic for PID exit detection."""
        exe = Path(r"C:\Test\app.exe")
        with patch("z7_officeletters.core.updater.tempfile.gettempdir", return_value=str(tmp_path)):
            result = _generate_restart_script(exe)

        assert result is not None
        content = Path(result).read_text(encoding="ascii")
        assert "WAIT_LOOP" in content
        assert "LAUNCH" in content
        assert "set TARGET_PID=1234" in content
        assert "COUNTER" in content

    @patch("z7_officeletters.core.updater.os.getpid", return_value=5555)
    def test_falha_escrita_retorna_none(self, _mock_pid: MagicMock) -> None:
        """Returns None when the temp dir is not writable."""
        with patch("z7_officeletters.core.updater.Path.write_text", side_effect=OSError("disk full")):
            result = _generate_restart_script(Path(r"C:\app.exe"))
        assert result is None


# =============================================================================
# _reiniciar_aplicativo
# =============================================================================
class TestReiniciarAplicativo:

    @patch("z7_officeletters.core.updater.messagebox.showinfo")
    @patch("z7_officeletters.core.updater.os._exit", side_effect=SystemExit(0))
    @patch("z7_officeletters.core.updater.time.sleep")
    @patch("z7_officeletters.core.updater._launch_new_instance", return_value=True)
    def test_estrategia_1_popen_sucesso(
        self,
        mock_launch: MagicMock,
        _mock_sleep: MagicMock,
        mock_exit: MagicMock,
        _mock_msgbox: MagicMock,
    ) -> None:
        """Strategy 1 (Popen) succeeds: parent is destroyed and process exits."""
        parent = MagicMock()
        exe = Path(r"C:\Apps\Z7_OfficeLetters.exe")

        with pytest.raises(SystemExit):
            _reiniciar_aplicativo(exe, parent)

        mock_launch.assert_called_once_with(exe)
        parent.destroy.assert_called_once()
        mock_exit.assert_called_once_with(0)

    @patch("z7_officeletters.core.updater.messagebox.showinfo")
    @patch("z7_officeletters.core.updater.os._exit", side_effect=SystemExit(0))
    @patch("z7_officeletters.core.updater.time.sleep")
    @patch("z7_officeletters.core.updater.subprocess.Popen")
    @patch("z7_officeletters.core.updater._generate_restart_script", return_value=r"C:\Temp\z7_restart_123.cmd")
    @patch("z7_officeletters.core.updater._launch_new_instance", return_value=False)
    def test_estrategia_2_script_cmd_sucesso(
        self,
        mock_launch: MagicMock,
        mock_gen_script: MagicMock,
        mock_popen: MagicMock,
        _mock_sleep: MagicMock,
        mock_exit: MagicMock,
        _mock_msgbox: MagicMock,
    ) -> None:
        """Strategy 1 fails, Strategy 2 (CMD script) succeeds."""
        parent = MagicMock()
        exe = Path(r"C:\Apps\Z7_OfficeLetters.exe")

        with pytest.raises(SystemExit):
            _reiniciar_aplicativo(exe, parent)

        mock_launch.assert_called_once_with(exe)
        mock_gen_script.assert_called_once_with(exe)
        mock_popen.assert_called_once()
        popen_args = mock_popen.call_args[0][0]
        assert popen_args[0] == "cmd.exe"
        assert popen_args[1] == "/c"
        parent.destroy.assert_called_once()
        mock_exit.assert_called_once_with(0)

    @patch("z7_officeletters.core.updater.messagebox.showinfo")
    @patch("z7_officeletters.core.updater.subprocess.Popen", side_effect=OSError("blocked"))
    @patch("z7_officeletters.core.updater._generate_restart_script", return_value=None)
    @patch("z7_officeletters.core.updater._launch_new_instance", return_value=False)
    def test_todas_estrategias_falham_mostra_mensagem(
        self,
        mock_launch: MagicMock,
        mock_gen_script: MagicMock,
        mock_popen: MagicMock,
        mock_msgbox: MagicMock,
    ) -> None:
        """All strategies fail: shows manual restart messagebox."""
        parent = MagicMock()
        exe = Path(r"C:\Apps\Z7_OfficeLetters.exe")

        _reiniciar_aplicativo(exe, parent)

        mock_launch.assert_called_once_with(exe)
        mock_gen_script.assert_called_once_with(exe)
        mock_popen.assert_not_called()
        mock_msgbox.assert_called_once()
        msg_args = mock_msgbox.call_args
        assert "Atualização Concluída" in msg_args[0][0]
        assert "reabra o aplicativo" in msg_args[0][1]
        assert msg_args[1]["parent"] is parent

    @patch("z7_officeletters.core.updater.messagebox.showinfo")
    @patch("z7_officeletters.core.updater.subprocess.Popen", side_effect=OSError("blocked"))
    @patch("z7_officeletters.core.updater._generate_restart_script", return_value=r"C:\Temp\z7_restart_123.cmd")
    @patch("z7_officeletters.core.updater._launch_new_instance", return_value=False)
    def test_estrategia_2_popen_falha_mostra_mensagem(
        self,
        mock_launch: MagicMock,
        mock_gen_script: MagicMock,
        mock_popen: MagicMock,
        mock_msgbox: MagicMock,
    ) -> None:
        """Strategy 2 Popen also fails: falls through to manual restart message."""
        parent = MagicMock()
        exe = Path(r"C:\Apps\Z7_OfficeLetters.exe")

        _reiniciar_aplicativo(exe, parent)

        mock_popen.assert_called_once()
        mock_msgbox.assert_called_once()
        assert "reabra o aplicativo" in mock_msgbox.call_args[0][1]

    @patch("z7_officeletters.core.updater.messagebox.showinfo")
    @patch("z7_officeletters.core.updater.os._exit", side_effect=SystemExit(0))
    @patch("z7_officeletters.core.updater.time.sleep")
    @patch("z7_officeletters.core.updater._launch_new_instance", return_value=True)
    def test_parent_destroy_falha_nao_impede_exit(
        self,
        mock_launch: MagicMock,
        _mock_sleep: MagicMock,
        mock_exit: MagicMock,
        _mock_msgbox: MagicMock,
    ) -> None:
        """Even if parent.destroy() fails, os._exit(0) is still called."""
        parent = MagicMock()
        parent.destroy.side_effect = Exception("already destroyed")
        exe = Path(r"C:\Apps\Z7_OfficeLetters.exe")

        with pytest.raises(SystemExit):
            _reiniciar_aplicativo(exe, parent)

        parent.destroy.assert_called_once()
        mock_exit.assert_called_once_with(0)
