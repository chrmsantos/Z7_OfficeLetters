"""Self-updater logic for Z7 OfficeLetters.

Handles checking the GitHub Releases API for new updates and comparing version
strings using SemVer.

Public exports:
    obter_ultima_versao: Query GitHub for the latest release details.
    comparar_versoes: Compare two version strings.
"""

from __future__ import annotations

import json
import re
import urllib.request
from typing import Tuple

from z7_officeletters.core.logging_setup import logger

__all__ = ["obter_ultima_versao", "comparar_versoes"]


def parse_version(v_str: str) -> tuple[int, ...]:
    """Parse a version string into a tuple of integers for comparison.

    Examples:
        "v3.1.6" -> (3, 1, 6)
        "3.10.1" -> (3, 10, 1)
    """
    return tuple(int(x) for x in re.findall(r"\d+", v_str))


def comparar_versoes(v1: str, v2: str) -> bool:
    """Compare two version strings (SemVer style).

    Returns:
        True if v1 is strictly greater than v2, False otherwise.
    """
    try:
        return parse_version(v1) > parse_version(v2)
    except Exception as exc:
        logger.warning("Falha ao comparar versões %r e %r: %s", v1, v2, exc)
        return False


def obter_ultima_versao() -> tuple[str, str]:
    """Query the GitHub Releases API for the latest stable release of the project.

    Returns:
        A tuple (tag_name, browser_download_url) for the Z7_OfficeLetters.exe asset.

    Raises:
        RuntimeError: If the request fails, returns invalid JSON, or if the
            required executable asset is missing from the release.
    """
    url = "https://api.github.com/repos/chrmsantos/Z7_OfficeLetters/releases/latest"
    req = urllib.request.Request(url, headers={"User-Agent": "Z7_OfficeLetters-Updater"})

    try:
        logger.info("Verificando atualizações no GitHub: %s", url)
        with urllib.request.urlopen(req, timeout=10) as response:
            status = response.status
            if status != 200:
                raise RuntimeError(f"Servidor respondeu com código HTTP {status}")
            data = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        logger.error("Falha ao consultar a API do GitHub: %s", exc)
        raise RuntimeError(f"Erro ao conectar com o servidor de atualizações: {exc}") from exc

    tag_name = data.get("tag_name")
    if not tag_name:
        raise RuntimeError("A resposta do servidor de atualizações não continha informações de versão (tag_name).")

    assets = data.get("assets", [])
    download_url = ""
    for asset in assets:
        if asset.get("name") == "Z7_OfficeLetters.exe":
            download_url = asset.get("browser_download_url", "")
            break

    if not download_url:
        raise RuntimeError(
            f"A nova versão ({tag_name}) está disponível, mas o arquivo executável "
            "'Z7_OfficeLetters.exe' não foi publicado nos anexos da release ainda."
        )

    logger.info("Última versão disponível encontrada: %s", tag_name)
    return tag_name, download_url
