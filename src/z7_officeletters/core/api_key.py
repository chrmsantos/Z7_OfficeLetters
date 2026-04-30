"""Secure API key persistence using Windows Credential Manager.

Provides functions to store, retrieve, and migrate the Gemini API key.
The key is stored encrypted in the Windows Credential Manager via the
``keyring`` library, replacing the legacy plain-text Windows Registry entry.

Public exports:
    KEYRING_SERVICE: Service name used as the Credential Manager namespace.
    KEYRING_USERNAME: Username key within the service.
    KEYRING_MODEL_USERNAME: Username key for the AI model name.
    DEFAULT_MODELO_IA: Default Gemini model name.
    salvar_api_key: Persist an API key to the Credential Manager.
    carregar_api_key: Retrieve the stored API key.
    salvar_modelo_ia: Persist the AI model name to the Credential Manager.
    carregar_modelo_ia: Retrieve the stored AI model name.
    migrar_chave_do_registro: One-time migration from the legacy Registry entry.
"""

from __future__ import annotations

from z7_officeletters.core.logging_setup import logger

__all__ = [
    "KEYRING_SERVICE",
    "KEYRING_USERNAME",
    "KEYRING_MODEL_USERNAME",
    "DEFAULT_MODELO_IA",
    "salvar_api_key",
    "carregar_api_key",
    "salvar_modelo_ia",
    "carregar_modelo_ia",
    "migrar_chave_do_registro",
]

KEYRING_SERVICE: str = "z7_officeletters"
KEYRING_USERNAME: str = "gemini_api_key"
KEYRING_MODEL_USERNAME: str = "gemini_model"
DEFAULT_MODELO_IA: str = "gemini-2.0-flash"


def salvar_api_key(chave: str) -> None:
    """Persist the Gemini API key in the Windows Credential Manager.

    Also sets the ``GEMINI_API_KEY`` environment variable in the current
    process so that libraries that read ``os.environ`` pick it up immediately.

    Args:
        chave: The Gemini API key string to store.
    """
    import keyring  # noqa: PLC0415 — lazy: avoids ~500 ms startup cost
    import os  # noqa: PLC0415

    keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, chave)
    os.environ["GEMINI_API_KEY"] = chave
    logger.info("GEMINI_API_KEY persistida no Credential Manager do Windows.")


def carregar_api_key() -> str:
    """Retrieve the Gemini API key from the Windows Credential Manager.

    Returns:
        The stored API key, or an empty string if none is found.
    """
    import keyring  # noqa: PLC0415

    return keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME) or ""


def salvar_modelo_ia(modelo: str) -> None:
    """Persist the AI model name in the Windows Credential Manager.

    Args:
        modelo: The Gemini model name string to store (e.g. ``"gemini-2.0-flash"``).
    """
    import keyring  # noqa: PLC0415

    keyring.set_password(KEYRING_SERVICE, KEYRING_MODEL_USERNAME, modelo)
    logger.info("Modelo IA '%s' persistido no Credential Manager do Windows.", modelo)


def carregar_modelo_ia() -> str:
    """Retrieve the stored AI model name from the Windows Credential Manager.

    Returns:
        The stored model name, or :data:`DEFAULT_MODELO_IA` if none is found.
    """
    import keyring  # noqa: PLC0415

    return keyring.get_password(KEYRING_SERVICE, KEYRING_MODEL_USERNAME) or DEFAULT_MODELO_IA


def migrar_chave_do_registro() -> None:
    """Migrate a plain-text API key from the Windows Registry to Credential Manager.

    This one-time migration reads the ``GEMINI_API_KEY`` value stored in
    ``HKCU\\Environment`` (the legacy storage location), saves it securely via
    ``salvar_api_key()``, then deletes the plain-text registry value.

    The function is a no-op if the registry value does not exist or has already
    been migrated.
    """
    import winreg  # noqa: PLC0415 — Windows-only; available in the frozen build

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            "Environment",
            access=winreg.KEY_READ | winreg.KEY_SET_VALUE,
        ) as reg:
            try:
                value, _ = winreg.QueryValueEx(reg, "GEMINI_API_KEY")
            except FileNotFoundError:
                return  # Nothing to migrate.

            if value:
                salvar_api_key(value)
                logger.info("GEMINI_API_KEY migrada do registro para o Credential Manager.")

            try:
                winreg.DeleteValue(reg, "GEMINI_API_KEY")
                logger.info("Valor GEMINI_API_KEY removido do registro do Windows.")
            except FileNotFoundError:
                pass

    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha ao migrar GEMINI_API_KEY do registro: %s", exc)
