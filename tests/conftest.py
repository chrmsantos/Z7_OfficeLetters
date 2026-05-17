"""Shared test fixtures and helpers for the z7_officeletters test suite."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Shared data-builder helpers (available as plain functions for test modules)
# ---------------------------------------------------------------------------

def make_dados_requerimento_validos(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid requerimento de pesar data dict."""
    base: dict[str, Any] = {
        "numero_requerimento": "45",
        "falecido": "João da Silva",
        "autores": ["Alex Dantas"],
        "destinatarios": [{"nome": "Fulano de Tal"}],
    }
    base.update(overrides)
    return base


def make_dados_mocao_validos(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid motion-data dict."""
    base: dict[str, Any] = {
        "tipo_mocao": "Aplauso",
        "numero_mocao": "123",
        "autores": ["Alex Dantas"],
        "destinatarios": [{"nome": "Fulano de Tal"}],
    }
    base.update(overrides)
    return base


def make_dest_simples(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid PF recipient dict."""
    base: dict[str, Any] = {
        "tipo": "PF",
        "nome": "João Silva",
        "is_prefeito": False,
        "is_instituicao": False,
        "cargo_ou_tratamento": "",
        "endereco": "",
        "email": "",
        "genero": "M",
    }
    base.update(overrides)
    return base


def make_dest_pj(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid PJ recipient dict."""
    base: dict[str, Any] = {
        "tipo": "PJ",
        "nome": "Empresa Exemplo S.A.",
        "endereco": "",
        "email": "",
        "genero": "M",
    }
    base.update(overrides)
    return base


def make_dest_coletivo(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid Coletivo recipient dict."""
    base: dict[str, Any] = {
        "tipo": "Coletivo",
        "nome": "Associação dos Moradores",
        "endereco": "",
        "email": "",
        "genero": "M",
    }
    base.update(overrides)
    return base


def make_ai_response(payload: dict[str, Any]) -> MagicMock:
    """Return a fake Gemini response whose ``.text`` is compact JSON."""
    import json

    mock = MagicMock()
    mock.text = json.dumps(payload)
    mock.usage_metadata.prompt_token_count = 10
    mock.usage_metadata.candidates_token_count = 5
    mock.usage_metadata.total_token_count = 15
    return mock


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def dados_mocao_validos() -> dict[str, Any]:
    return make_dados_mocao_validos()


@pytest.fixture()
def dados_requerimento_validos() -> dict[str, Any]:
    return make_dados_requerimento_validos()


@pytest.fixture()
def dest_simples() -> dict[str, Any]:
    return make_dest_simples()
