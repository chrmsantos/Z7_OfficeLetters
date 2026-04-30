"""Z7 OfficeLetters — Gerador de Ofícios Legislativos.

Este pacote expõe a versão da aplicação e os re-exports públicos
usados pela interface gráfica e pelos scripts auxiliares.

Public exports:
    APP_NAME: Nome do produto.
    APP_VERSION: Versão atual no formato CalVer/SemVer.
    APP_AUTHOR: Nome do autor.
"""

from __future__ import annotations

__all__ = ["APP_NAME", "APP_VERSION", "APP_AUTHOR"]

APP_NAME: str = "Z7 OfficeLetters"
APP_VERSION: str = "2.1.6-beta3"
APP_AUTHOR: str = "Christian Martin dos Santos"
