"""Core business-logic sub-package.

Re-exports the public API so callers can use a single import:

    from z7_officeletters.core import formatar_autores, processar_destinatario

Public modules:
    logging_setup: Logging configuration and session ID.
    config: Runtime configuration loaded from ``config.json``.
    authors: Author name resolution and formatting.
    recipients: Recipient address and honorific processing.
    files: File listing and multi-format text extraction.
    ai: Gemini AI integration and prompt management.
    documents: Document generation and filename construction.
    api_key: Secure API key persistence via Windows Credential Manager.
"""

from __future__ import annotations

from z7_officeletters.core.ai import extrair_dados_com_ia, limpar_json_da_resposta, validar_dados_mocao
from z7_officeletters.core.api_key import carregar_api_key, migrar_chave_do_registro
from z7_officeletters.core.authors import formatar_autores, sigla_autor
from z7_officeletters.core.config import MAPA_AUTORES, MAPA_REDATORES, reload_config
from z7_officeletters.core.documents import (
    construir_nome_arquivo,
    criar_modelo_planilha,
    normalizar_numero_mocao,
)
from z7_officeletters.core.files import ler_arquivo_mocoes
from z7_officeletters.core.logging_setup import configurar_logging
from z7_officeletters.core.recipients import processar_destinatario

__all__ = [
    # ai
    "extrair_dados_com_ia",
    "limpar_json_da_resposta",
    "validar_dados_mocao",
    # api_key
    "carregar_api_key",
    "migrar_chave_do_registro",
    # authors
    "formatar_autores",
    "sigla_autor",
    # config
    "MAPA_AUTORES",
    "MAPA_REDATORES",
    "reload_config",
    # documents
    "construir_nome_arquivo",
    "criar_modelo_planilha",
    "normalizar_numero_mocao",
    # files
    "ler_arquivo_mocoes",
    # logging_setup
    "configurar_logging",
    # recipients
    "processar_destinatario",
]
