"""Z7 OfficeLetters — Gerador de Ofícios Legislativos.

Este pacote expõe a versão da aplicação e os re-exports públicos
usados pela interface gráfica e pelos scripts auxiliares.

Public exports:
    APP_NAME: Nome do produto.
    APP_VERSION: Versão atual no formato CalVer/SemVer.
    APP_AUTHOR: Nome do autor.
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

__all__ = ["APP_NAME", "APP_VERSION", "APP_AUTHOR"]


def _read_version() -> str:
    """Return the application version from package metadata or a fallback.

    Resolution order:
   0. ``version.txt`` written next to the executable by the self-updater —
       ensures the version persists correctly across updates even when the
       bundled PKG-INFO or hardcoded fallback is stale.
    1. ``pyproject.toml`` — the single source of truth (development mode).
    2. Bundled ``PKG-INFO`` inside the egg-info directory — works in a frozen
       PyInstaller executable where the egg-info is shipped as data.
    3. ``importlib.metadata`` — fallback when the package is pip-installed.
    4. Hardcoded fallback (must be kept in sync with ``pyproject.toml``).
    """
    import re as _re  # noqa: PLC0415

    # 0. Check for version.txt written by the self-updater (frozen mode only).
    #    This is the most reliable source after an update because it is written
    #    atomically by the updater with the exact version that was downloaded.
    if getattr(_sys, "frozen", False):
        try:
            _version_file = _Path(_sys.executable).parent / "version.txt"  # type: ignore[attr-defined]
            if _version_file.exists():
                _ver = _version_file.read_text(encoding="utf-8").strip()
                if _re.match(r"^\d+\.\d+\.\d+", _ver):
                    return _ver
        except Exception:  # noqa: BLE001
            pass

    # 1. Read directly from pyproject.toml (most reliable in dev mode)
    if not getattr(_sys, "frozen", False):
        try:
            _pyproject = _Path(__file__).resolve().parent.parent.parent / "pyproject.toml"
            if _pyproject.exists():
                _text = _pyproject.read_text(encoding="utf-8")
                _match = _re.search(r'^version\s*=\s*"([^"]+)"', _text, _re.MULTILINE)
                if _match:
                    return _match.group(1)
        except Exception:  # noqa: BLE001
            pass

    # 2. Parse PKG-INFO from the bundled egg-info (frozen / PyInstaller)
    try:
        if getattr(_sys, "frozen", False):
            _base = _Path(_sys._MEIPASS)  # type: ignore[attr-defined]
        else:
            _base = _Path(__file__).resolve().parent.parent.parent
        _pkg_info = _base / "z7_officeletters.egg-info" / "PKG-INFO"
        if _pkg_info.exists():
            for _line in _pkg_info.read_text(encoding="utf-8").splitlines():
                if _line.startswith("Version:"):
                    return _line.split(":", 1)[1].strip()
    except Exception:  # noqa: BLE001
        pass

    # 3. importlib.metadata (works when the package is installed via pip)
    try:
        from importlib.metadata import version as _pkg_version  # noqa: PLC0415

        return _pkg_version("z7-officeletters")
    except Exception:  # noqa: BLE001
        pass

    # 4. Hardcoded fallback — keep in sync with pyproject.toml
    return "4.11.0"


APP_NAME: str = "Z7 OfficeLetters"
APP_VERSION: str = _read_version()
APP_AUTHOR: str = "CMS"
