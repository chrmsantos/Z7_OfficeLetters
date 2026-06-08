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
import urllib.error
import urllib.request
from typing import Tuple

from z7_officeletters.core.logging_setup import logger

__all__ = ["obter_ultima_versao", "comparar_versoes"]


def parse_version(v_str: str) -> tuple[tuple[int, ...], tuple[int, tuple[str | int, ...]]]:
    """Parse a version string into a structure suitable for SemVer comparison.

    Handles major, minor, patch and optional pre-release tag (e.g., v3.2.0-rc1).
    """
    clean_v = v_str.strip().lstrip("vV").split("+")[0]
    parts = clean_v.split("-", 1)
    version_part = parts[0]
    prerelease_part = parts[1] if len(parts) > 1 else ""

    version_nums = tuple(int(x) for x in re.findall(r"\d+", version_part))
    if len(version_nums) < 3:
        version_nums = version_nums + (0,) * (3 - len(version_nums))

    if not prerelease_part:
        # Stable release compares greater than pre-release.
        # We return a tuple starting with 1 to indicate stable.
        return (version_nums, (1, ()))

    # Pre-release compares lower than stable release.
    # We return a tuple starting with 0 to indicate pre-release.
    pre_elements: list[str | int] = []
    for item in prerelease_part.split("."):
        for subitem in re.findall(r"[a-zA-Z]+|\d+", item):
            if subitem.isdigit():
                pre_elements.append(int(subitem))
            else:
                pre_elements.append(subitem.lower())

    return (version_nums, (0, tuple(pre_elements)))


def comparar_versoes(v1: str, v2: str) -> bool:
    """Compare two version strings (SemVer style).

    Returns:
        True if v1 is strictly greater than v2, False otherwise.
    """
    try:
        p1 = parse_version(v1)
        p2 = parse_version(v2)

        # Compare main version numbers (major, minor, patch)
        if p1[0] != p2[0]:
            return p1[0] > p2[0]

        # Compare stable vs pre-release
        if p1[1][0] != p2[1][0]:
            return p1[1][0] > p2[1][0]

        # If both are stable and their main version is equal, they are equal
        if p1[1][0] == 1:
            return False

        # Both are pre-releases, compare their elements
        pre1 = p1[1][1]
        pre2 = p2[1][1]

        for e1, e2 in zip(pre1, pre2):
            if type(e1) is type(e2):
                if e1 != e2:
                    return e1 > e2  # type: ignore[operator]
            else:
                # Numeric identifiers always have lower precedence than non-numeric
                return isinstance(e1, str)

        # If all compared elements are equal, the one with more elements is greater
        return len(pre1) > len(pre2)
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
    except urllib.error.HTTPError as http_exc:
        if http_exc.code == 403:
            logger.error("Limite de requisições da API do GitHub excedido.")
            raise RuntimeError(
                "Limite de requisições da API do GitHub excedido para o seu IP. "
                "Por favor, aguarde alguns minutos e tente novamente."
            ) from http_exc
        raise RuntimeError(f"Servidor respondeu com código HTTP {http_exc.code}") from http_exc
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
