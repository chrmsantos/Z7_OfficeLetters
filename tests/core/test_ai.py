"""Tests for z7_officeletters.core.ai."""

from __future__ import annotations

import json
import logging
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import make_ai_response, make_dados_mocao_validos, make_dados_requerimento_validos
from z7_officeletters.core.ai import (
    extrair_dados_com_ia,
    limpar_json_da_resposta,
    validar_dados_mocao,
    validar_dados_requerimento_pesar,
)
from z7_officeletters.gui.constants import detectar_tipo_propositura, numero_propositura
from z7_officeletters.core.documents import construir_nome_arquivo


# =============================================================================
# limpar_json_da_resposta
# =============================================================================
class TestLimparJsonDaResposta:

    def test_json_puro_sem_marcador(self) -> None:
        assert limpar_json_da_resposta('{"k": 1}') == '{"k": 1}'

    def test_marcador_json(self) -> None:
        texto = '```json\n{"tipo_mocao": "Aplauso"}\n```'
        assert limpar_json_da_resposta(texto) == '{"tipo_mocao": "Aplauso"}'

    def test_marcador_generico(self) -> None:
        texto = '```\n{"tipo_mocao": "Apelo"}\n```'
        assert limpar_json_da_resposta(texto) == '{"tipo_mocao": "Apelo"}'

    def test_espacos_e_quebras_extras(self) -> None:
        texto = '  \n```json\n{"a": 1}\n```\n  '
        assert limpar_json_da_resposta(texto) == '{"a": 1}'

    def test_resultado_e_json_valido_apos_limpeza(self) -> None:
        texto = '```json\n{"tipo_mocao": "Aplauso", "numero_mocao": "42"}\n```'
        assert json.loads(limpar_json_da_resposta(texto))["numero_mocao"] == "42"

    def test_json_array_retornado_intacto(self) -> None:
        texto = '```json\n[{"tipo_mocao": "Apelo"}]\n```'
        parsed = json.loads(limpar_json_da_resposta(texto))
        assert isinstance(parsed, list) and parsed[0]["tipo_mocao"] == "Apelo"


# =============================================================================
# validar_dados_mocao
# =============================================================================
class TestValidarDadosMocao:

    def test_dados_completos_nao_levanta(self) -> None:
        validar_dados_mocao(make_dados_mocao_validos())

    def test_tipo_apelo_valido(self) -> None:
        validar_dados_mocao(make_dados_mocao_validos(tipo_mocao="Apelo"))

    def test_tipo_invalido(self) -> None:
        with pytest.raises(ValueError, match="tipo_mocao"):
            validar_dados_mocao(make_dados_mocao_validos(tipo_mocao="Homenagem"))

    @pytest.mark.parametrize("campo", ["tipo_mocao", "numero_mocao", "autores", "destinatarios"])
    def test_campo_ausente_levanta(self, campo: str) -> None:
        d = make_dados_mocao_validos()
        del d[campo]
        with pytest.raises(ValueError):
            validar_dados_mocao(d)

    def test_autores_lista_vazia(self) -> None:
        with pytest.raises(ValueError):
            validar_dados_mocao(make_dados_mocao_validos(autores=[]))

    def test_destinatarios_lista_vazia(self) -> None:
        with pytest.raises(ValueError):
            validar_dados_mocao(make_dados_mocao_validos(destinatarios=[]))

    def test_autores_nao_e_lista(self) -> None:
        with pytest.raises(ValueError, match="lista"):
            validar_dados_mocao(make_dados_mocao_validos(autores="Alex Dantas"))

    def test_destinatarios_nao_e_lista(self) -> None:
        with pytest.raises(ValueError, match="lista"):
            validar_dados_mocao(make_dados_mocao_validos(destinatarios={"nome": "X"}))

    def test_destinatario_sem_nome(self) -> None:
        with pytest.raises(ValueError, match="nome"):
            validar_dados_mocao(make_dados_mocao_validos(destinatarios=[{"nome": ""}]))

    def test_destinatario_sem_chave_nome(self) -> None:
        with pytest.raises(ValueError, match="nome"):
            validar_dados_mocao(make_dados_mocao_validos(destinatarios=[{"cargo": "X"}]))

    def test_multiplos_destinatarios_validos(self) -> None:
        validar_dados_mocao(make_dados_mocao_validos(
            destinatarios=[{"nome": "Fulano"}, {"nome": "Ciclano"}]
        ))

    def test_segundo_destinatario_sem_nome_levanta(self) -> None:
        with pytest.raises(ValueError):
            validar_dados_mocao(make_dados_mocao_validos(
                destinatarios=[{"nome": "Fulano"}, {"nome": ""}]
            ))


# =============================================================================
# extrair_dados_com_ia
# =============================================================================
class TestExtrairDadosComIA:
    """All Gemini calls are mocked."""

    def _client(self, *responses: Any) -> MagicMock:
        client = MagicMock()
        client.models.generate_content.side_effect = list(responses)
        return client

    # --- Happy path ---
    def test_retorna_dados_validos_na_primeira_tentativa(self) -> None:
        client = self._client(make_ai_response(make_dados_mocao_validos()))
        r = extrair_dados_com_ia("MOÇÃO Nº 1 texto", client)
        assert r["tipo_mocao"] == "Aplauso"
        assert r["numero_mocao"] == "123"

    def test_aceita_resposta_com_markdown_json_fence(self) -> None:
        payload = make_dados_mocao_validos()
        mock_resp = MagicMock()
        mock_resp.text = f"```json\n{json.dumps(payload)}\n```"
        client = self._client(mock_resp)
        assert extrair_dados_com_ia("MOÇÃO", client)["tipo_mocao"] == "Aplauso"

    def test_aceita_resposta_em_lista(self) -> None:
        mock_resp = MagicMock()
        mock_resp.text = json.dumps([make_dados_mocao_validos()])
        client = self._client(mock_resp)
        assert extrair_dados_com_ia("MOÇÃO", client)["tipo_mocao"] == "Aplauso"

    # --- Retry on invalid response ---
    def test_retenta_quando_json_invalido(self) -> None:
        bad = MagicMock()
        bad.text = "não é json"
        good = make_ai_response(make_dados_mocao_validos())
        client = self._client(bad, good)
        r = extrair_dados_com_ia("MOÇÃO", client)
        assert r["tipo_mocao"] == "Aplauso"
        assert client.models.generate_content.call_count == 2

    def test_retenta_quando_tipo_mocao_invalido(self) -> None:
        bad = make_ai_response(make_dados_mocao_validos(tipo_mocao="Homenagem"))
        good = make_ai_response(make_dados_mocao_validos())
        client = self._client(bad, good)
        r = extrair_dados_com_ia("MOÇÃO", client)
        assert r["tipo_mocao"] == "Aplauso"
        assert client.models.generate_content.call_count == 2

    def test_levanta_apos_todas_as_tentativas_falharem(self) -> None:
        bad = MagicMock()
        bad.text = "não é json"
        client = self._client(*([bad] * 5))
        with pytest.raises((ValueError, json.JSONDecodeError)):
            extrair_dados_com_ia("MOÇÃO", client)
        assert client.models.generate_content.call_count == 5

    # --- Rate limit (429) ---
    def test_aguarda_e_retenta_em_rate_limit(self) -> None:
        good = make_ai_response(make_dados_mocao_validos())
        client = self._client(
            Exception("Error 429: retry_delay { seconds: 1 }"),
            good,
        )
        with patch("time.sleep") as mock_sleep:
            r = extrair_dados_com_ia("MOÇÃO", client)
        assert mock_sleep.call_count >= 1
        assert all(args == (1,) for args, _ in mock_sleep.call_args_list)
        assert r["tipo_mocao"] == "Aplauso"

    def test_extrai_espera_do_retry_delay(self) -> None:
        good = make_ai_response(make_dados_mocao_validos())
        client = self._client(
            Exception("Error 429: retry_delay { seconds: 10 }"),
            good,
        )
        with patch("time.sleep") as mock_sleep:
            extrair_dados_com_ia("MOÇÃO", client)
        total_slept = sum(args[0] for args, _ in mock_sleep.call_args_list)
        assert total_slept == 12

    def test_erro_nao_429_relancado_imediatamente(self) -> None:
        client = self._client(ConnectionError("falha de rede"))
        with pytest.raises(ConnectionError):
            extrair_dados_com_ia("MOÇÃO", client)
        assert client.models.generate_content.call_count == 1

    # --- Logging ---
    def test_loga_resposta_bruta_em_debug(self, caplog: pytest.LogCaptureFixture) -> None:
        client = self._client(make_ai_response(make_dados_mocao_validos()))
        with caplog.at_level(logging.DEBUG, logger="z7_officeletters"):
            extrair_dados_com_ia("MOÇÃO", client)
        assert any("Resposta bruta" in r.message for r in caplog.records)

    def test_loga_warning_em_resposta_invalida(self, caplog: pytest.LogCaptureFixture) -> None:
        bad = MagicMock()
        bad.text = "não é json"
        good = make_ai_response(make_dados_mocao_validos())
        client = self._client(bad, good)
        with caplog.at_level(logging.WARNING, logger="z7_officeletters"):
            extrair_dados_com_ia("MOÇÃO", client)
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_resposta_longa_nao_aparece_inteira_no_log(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        long_text = "x" * 2000
        bad = MagicMock()
        bad.text = long_text
        good = make_ai_response(make_dados_mocao_validos())
        client = self._client(bad, good)
        with caplog.at_level(logging.DEBUG, logger="z7_officeletters"):
            extrair_dados_com_ia("MOÇÃO", client)
        bruta_msgs = [r.message for r in caplog.records if "Resposta bruta" in r.message]
        assert all(len(m) < len(long_text) for m in bruta_msgs)


# =============================================================================
# detectar_tipo_propositura
# =============================================================================
class TestDetectarTipoPropositura:

    def test_mocao_detectada(self) -> None:
        assert detectar_tipo_propositura("MOÇÃO Nº 124\nTexto da moção.") == "mocao"

    def test_mocao_acento_grau(self) -> None:
        assert detectar_tipo_propositura("MOÇÃO N° 50 texto") == "mocao"

    def test_requerimento_detectado(self) -> None:
        assert detectar_tipo_propositura("REQUERIMENTO Nº 45\nTexto.") == "requerimento_pesar"

    def test_requerimento_de_pesar_detectado(self) -> None:
        assert detectar_tipo_propositura("REQUERIMENTO DE PESAR Nº 12\nTexto.") == "requerimento_pesar"

    def test_requerimento_case_insensitive(self) -> None:
        assert detectar_tipo_propositura("Requerimento nº 7 texto") == "requerimento_pesar"

    def test_texto_vazio_retorna_mocao(self) -> None:
        assert detectar_tipo_propositura("") == "mocao"

    def test_texto_sem_cabecalho_retorna_mocao(self) -> None:
        assert detectar_tipo_propositura("Texto sem cabeçalho.") == "mocao"


# =============================================================================
# numero_propositura
# =============================================================================
class TestNumeroPropositura:

    def test_mocao_numero_extraido(self) -> None:
        assert numero_propositura("MOÇÃO Nº 124\nTexto da moção.") == 124

    def test_mocao_acento_grau(self) -> None:
        assert numero_propositura("MOÇÃO N° 50 texto") == 50

    def test_requerimento_numero_extraido(self) -> None:
        assert numero_propositura("REQUERIMENTO Nº 45\nTexto.") == 45

    def test_requerimento_de_pesar_numero_extraido(self) -> None:
        assert numero_propositura("REQUERIMENTO DE PESAR Nº 12\nTexto.") == 12

    def test_sem_numero_retorna_zero(self) -> None:
        assert numero_propositura("Texto sem cabeçalho.") == 0

    def test_texto_vazio_retorna_zero(self) -> None:
        assert numero_propositura("") == 0


# =============================================================================
# validar_dados_requerimento_pesar
# =============================================================================
class TestValidarDadosRequerimentoPesar:

    def test_dados_completos_nao_levanta(self) -> None:
        validar_dados_requerimento_pesar(make_dados_requerimento_validos())

    def test_falecido_vazio_nao_levanta(self) -> None:
        # falecido é opcional
        validar_dados_requerimento_pesar(make_dados_requerimento_validos(falecido=""))

    def test_falecido_ausente_nao_levanta(self) -> None:
        d = make_dados_requerimento_validos()
        del d["falecido"]
        validar_dados_requerimento_pesar(d)

    @pytest.mark.parametrize("campo", ["numero_requerimento", "autores", "destinatarios"])
    def test_campo_obrigatorio_ausente_levanta(self, campo: str) -> None:
        d = make_dados_requerimento_validos()
        del d[campo]
        with pytest.raises(ValueError):
            validar_dados_requerimento_pesar(d)

    def test_autores_lista_vazia_levanta(self) -> None:
        with pytest.raises(ValueError):
            validar_dados_requerimento_pesar(make_dados_requerimento_validos(autores=[]))

    def test_destinatarios_lista_vazia_levanta(self) -> None:
        with pytest.raises(ValueError):
            validar_dados_requerimento_pesar(make_dados_requerimento_validos(destinatarios=[]))

    def test_destinatario_sem_nome_levanta(self) -> None:
        with pytest.raises(ValueError, match="nome"):
            validar_dados_requerimento_pesar(
                make_dados_requerimento_validos(destinatarios=[{"nome": ""}])
            )


# =============================================================================
# extrair_dados_com_ia — requerimento de pesar routing
# =============================================================================
class TestExtrairDadosComIARequerimento:
    """Verify that tipo_propositura='requerimento_pesar' routes correctly."""

    def _client(self, *responses: Any) -> MagicMock:
        client = MagicMock()
        client.models.generate_content.side_effect = list(responses)
        return client

    def test_retorna_dados_validos_requerimento(self) -> None:
        client = self._client(make_ai_response(make_dados_requerimento_validos()))
        r = extrair_dados_com_ia(
            "REQUERIMENTO Nº 45 texto", client, tipo_propositura="requerimento_pesar"
        )
        assert r["numero_requerimento"] == "45"
        assert r["falecido"] == "João da Silva"

    def test_retenta_quando_numero_requerimento_ausente(self) -> None:
        bad = make_ai_response({"autores": ["A"], "destinatarios": [{"nome": "X"}]})
        good = make_ai_response(make_dados_requerimento_validos())
        client = self._client(bad, good)
        r = extrair_dados_com_ia("REQUERIMENTO", client, tipo_propositura="requerimento_pesar")
        assert r["numero_requerimento"] == "45"
        assert client.models.generate_content.call_count == 2


# =============================================================================
# construir_nome_arquivo — tipo_propositura parameter
# =============================================================================
class TestConstruirNomeArquivoTipoPropositura:

    def test_mocao_formato_padrao(self) -> None:
        nome = construir_nome_arquivo("001", "ajc", "Aplauso", "124", "E-mail", "João Silva", "ad", 2026)
        assert "Moção de Aplauso" in nome
        assert "Req." not in nome

    def test_requerimento_pesar_formato(self) -> None:
        nome = construir_nome_arquivo(
            "001", "ajc", "", "45", "Em Mãos", "João Silva", "ad", 2026,
            tipo_propositura="requerimento_pesar",
        )
        assert "Req. de Pesar" in nome
        assert "Moção" not in nome

    def test_requerimento_pesar_ano_2d(self) -> None:
        nome = construir_nome_arquivo(
            "001", "ajc", "", "45", "carta", "Dest", "ad", 2026,
            tipo_propositura="requerimento_pesar",
        )
        assert "45-26" in nome

    def test_requerimento_pesar_sem_caracteres_invalidos(self) -> None:
        nome = construir_nome_arquivo(
            "001", "ajc", "", "45", "E-mail", "Dest: X/Y", "ad", 2026,
            tipo_propositura="requerimento_pesar",
        )
        import re
        assert not re.search(r'[\\/*?:"<>|]', nome)
