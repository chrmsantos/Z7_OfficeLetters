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
