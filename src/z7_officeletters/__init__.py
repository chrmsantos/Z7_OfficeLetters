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


def _read_version() -> str:
    try:
        from importlib.metadata import version
        return version("z7-officeletters")
    except Exception:
        return "4.1.8"  # fallback para builds congelados sem metadados


APP_NAME: str = "Z7 OfficeLetters"
APP_VERSION: str = _read_version()
APP_AUTHOR: str = "CMS"
