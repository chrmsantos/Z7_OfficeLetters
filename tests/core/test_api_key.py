"""Tests for z7_officeletters.core.api_key."""

from __future__ import annotations

import logging
import os
from unittest.mock import MagicMock, patch

import pytest

import z7_officeletters.core.api_key as _api_key_mod
from z7_officeletters.core.api_key import (
    KEYRING_SERVICE,
    KEYRING_USERNAME,
    KEYRING_ACCOUNT_USERNAME,
    DEFAULT_API_KEY,
    DEFAULT_CONTA,
    carregar_api_key,
    migrar_chave_do_registro,
    salvar_api_key,
    salvar_conta,
    carregar_conta,
)



# =============================================================================
# salvar_api_key
# =============================================================================
class TestSalvarApiKey:

    def test_escreve_no_keyring_e_no_ambiente(self) -> None:
        with patch("keyring.set_password") as mock_set, \
                patch.dict(os.environ, {}, clear=False):
            salvar_api_key("minha-chave")
            mock_set.assert_called_once_with(KEYRING_SERVICE, KEYRING_USERNAME, "minha-chave")
            assert os.environ["OPENROUTER_API_KEY"] == "minha-chave"

    def test_chave_diferente_sobrescreve_ambiente(self) -> None:
        with patch("keyring.set_password"), \
                patch.dict(os.environ, {"OPENROUTER_API_KEY": "velha"}, clear=False):
            salvar_api_key("nova-chave")
            assert os.environ["OPENROUTER_API_KEY"] == "nova-chave"

    def test_loga_apos_salvar(self, caplog: pytest.LogCaptureFixture) -> None:
        with patch("keyring.set_password"), \
                caplog.at_level(logging.INFO, logger="z7_officeletters"):
            salvar_api_key("x")
        assert any("OPENROUTER_API_KEY" in r.message for r in caplog.records)


# =============================================================================
# carregar_api_key
# =============================================================================
class TestCarregarApiKey:

    def test_retorna_chave_do_keyring(self) -> None:
        with patch("keyring.get_password", return_value="chave-secreta"):
            assert carregar_api_key() == "chave-secreta"

    def test_retorna_chave_padrao_quando_nao_ha_chave(self) -> None:
        with patch("keyring.get_password", return_value=None):
            assert carregar_api_key() == DEFAULT_API_KEY

    def test_consulta_servico_e_usuario_corretos(self) -> None:
        with patch("keyring.get_password") as mock_get:
            mock_get.return_value = "k"
            carregar_api_key()
            mock_get.assert_called_with(KEYRING_SERVICE, KEYRING_USERNAME)


# =============================================================================
# salvar_conta
# =============================================================================
class TestSalvarConta:

    def test_escreve_no_keyring(self) -> None:
        with patch("keyring.set_password") as mock_set:
            salvar_conta("teste@email.com")
            mock_set.assert_called_once_with(KEYRING_SERVICE, KEYRING_ACCOUNT_USERNAME, "teste@email.com")


# =============================================================================
# carregar_conta
# =============================================================================
class TestCarregarConta:

    def test_retorna_conta_do_keyring(self) -> None:
        with patch("keyring.get_password", return_value="outra@email.com"):
            assert carregar_conta() == "outra@email.com"

    def test_retorna_conta_padrao_quando_nao_ha_conta(self) -> None:
        with patch("keyring.get_password", return_value=None):
            assert carregar_conta() == DEFAULT_CONTA

    def test_consulta_servico_e_usuario_corretos(self) -> None:
        with patch("keyring.get_password") as mock_get:
            mock_get.return_value = "c"
            carregar_conta()
            mock_get.assert_called_once_with(KEYRING_SERVICE, KEYRING_ACCOUNT_USERNAME)


# =============================================================================
# migrar_chave_do_registro
# =============================================================================
class TestMigrarChaveDoRegistro:

    def _patch_winreg(
        self, key_value: str | None
    ) -> tuple[Any, Any, Any, Any, MagicMock]:
        mock_reg = MagicMock()
        mock_reg.__enter__ = MagicMock(return_value=mock_reg)
        mock_reg.__exit__ = MagicMock(return_value=False)

        query_side_effect = None if key_value is not None else FileNotFoundError

        def fake_query(reg: object, name: str) -> tuple[str, int]:
            if query_side_effect:
                raise query_side_effect()
            return (key_value, 1)  # type: ignore[return-value]

        import winreg
        p_open = patch("winreg.OpenKey", return_value=mock_reg)
        p_query = patch("winreg.QueryValueEx", side_effect=fake_query)
        p_delete = patch("winreg.DeleteValue")
        p_set = patch("keyring.set_password")
        return p_open, p_query, p_delete, p_set, mock_reg  # type: ignore[return-value]

    def test_migra_chave_existente(self) -> None:
        p_open, p_query, p_delete, p_set, _ = self._patch_winreg("chave-antiga")
        with p_open, p_query, p_delete as mock_del, p_set as mock_set:
            migrar_chave_do_registro()
            assert mock_set.called
            assert mock_del.called

    def test_nao_faz_nada_se_chave_ausente(self) -> None:
        p_open, p_query, p_delete, p_set, _ = self._patch_winreg(None)
        with p_open, p_query, p_delete as mock_del, p_set as mock_set:
            migrar_chave_do_registro()
            mock_set.assert_not_called()
            mock_del.assert_not_called()

    def test_tolerante_a_falha_no_registro(self, caplog: pytest.LogCaptureFixture) -> None:
        with patch("winreg.OpenKey", side_effect=OSError("sem acesso")), \
                caplog.at_level(logging.WARNING, logger="z7_officeletters"):
            migrar_chave_do_registro()
        assert any("Falha" in r.message for r in caplog.records)
