"""Runtime configuration loader for Z7 OfficeLetters.

Reads ``config.json`` at import time and exposes the parsed data as
module-level variables.  The GUI calls ``reload_config()`` after the user
saves changes in the config editor so that the next generation run picks up
the updated values without restarting the application.

Public exports:
    PrefeitoConfig: TypedDict for the mayor section.
    ConfigData: TypedDict for the full config file.
    MAPA_AUTORES: Mapping of author names to their file-name siglas.
    MAPA_REDATORES: Mapping of drafter names to their siglas.
    PREFEITO: Mayor name and address block.
    CONFIG: Full parsed config dict.
    carregar_config: Reads and returns the config file contents.
    reload_config: Re-reads config.json and updates all module variables.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TypedDict

__all__ = [
    "PrefeitoConfig",
    "ConfigData",
    "MAPA_AUTORES",
    "MAPA_REDATORES",
    "PREFEITO",
    "CONFIG",
    "carregar_config",
    "reload_config",
]


class PrefeitoConfig(TypedDict):
    """Mayor name and address used in the letter footer."""

    nome: str
    endereco: str


class ConfigData(TypedDict, total=False):
    """Shape of config.json."""

    _comentario: str
    prefeito: PrefeitoConfig
    autores: dict[str, str]
    vereadores_feminino: list[str]
    redatores: dict[str, str]


def carregar_config() -> ConfigData:
    """Read and return the contents of ``config.json``.

    When running as a frozen PyInstaller executable the search order is:
    1. ``config.json`` next to the ``.exe`` (user-editable, takes priority).
    2. ``config.json`` bundled inside ``_MEIPASS`` (shipped default).

    Returns:
        Parsed configuration dictionary.
    """
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        beside_exe = exe_dir / "config.json"
        if beside_exe.exists():
            config_path = beside_exe
        else:
            meipass = Path(getattr(sys, "_MEIPASS", ""))
            config_path = meipass / "config.json"
    else:
        config_path = Path(__file__).parent.parent.parent.parent / "config.json"

    try:
        with config_path.open(encoding="utf-8") as fh:
            data: ConfigData = json.load(fh)
        return data
    except Exception as exc:
        try:
            logger.warning("Falha ao carregar configuração de '%s': %s. Usando fallback.", config_path, exc)
        except Exception:
            print(f"Falha ao carregar configuração de '{config_path}': {exc}. Usando fallback.", file=sys.stderr)
        
        return {
            "_comentario": "Configuração padrão de fallback devido a erro de leitura.",
            "prefeito": {
                "nome": "Prefeito Municipal",
                "endereco": "Praça Central, s/n - Centro"
            },
            "autores": {},
            "vereadores_feminino": [],
            "redatores": {}
        }


# ── Module-level state (mutated by reload_config) ────────────────────────────

CONFIG: ConfigData = carregar_config()

MAPA_AUTORES: dict[str, str] = CONFIG.get("autores", {})
MAPA_REDATORES: dict[str, str] = CONFIG.get("redatores", {})
PREFEITO: PrefeitoConfig = CONFIG.get(
    "prefeito", PrefeitoConfig(nome="", endereco="")
)


def reload_config() -> None:
    """Re-read ``config.json`` and refresh all module-level variables.

    Called by the GUI config editor after the user saves changes so the next
    generation run uses the updated author and recipient data without
    restarting the application.
    """
    global CONFIG, MAPA_AUTORES, MAPA_REDATORES, PREFEITO  # noqa: PLW0603

    CONFIG = carregar_config()
    MAPA_AUTORES = CONFIG.get("autores", {})
    MAPA_REDATORES = CONFIG.get("redatores", {})
    PREFEITO = CONFIG.get("prefeito", PrefeitoConfig(nome="", endereco=""))
