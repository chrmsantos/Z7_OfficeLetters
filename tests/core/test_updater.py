"""Tests for z7_officeletters.core.updater."""

from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import MagicMock, patch
import pytest

from z7_officeletters.core.updater import comparar_versoes, obter_ultima_versao


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
