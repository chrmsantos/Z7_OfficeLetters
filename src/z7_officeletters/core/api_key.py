"""Secure API key persistence using Windows Credential Manager.

Provides functions to store, retrieve, and migrate the OpenRouter API key.
The key is stored encrypted in the Windows Credential Manager via the
``keyring`` library.

Public exports:
    KEYRING_SERVICE: Service name used as the Credential Manager namespace.
    KEYRING_USERNAME: Username key within the service for OpenRouter API key.
    KEYRING_MODEL_USERNAME: Username key for the AI model name.
    KEYRING_FALLBACK_MODEL_USERNAME: Username key for the fallback AI model name.
    DEFAULT_MODELO_IA: Default OpenRouter AI model name.
    DEFAULT_MODELO_FALLBACK: Default fallback AI model name.
    salvar_api_key: Persist an API key to the Credential Manager.
    carregar_api_key: Retrieve the stored API key.
    salvar_modelo_ia: Persist the AI model name to the Credential Manager.
    carregar_modelo_ia: Retrieve the stored AI model name.
    migrar_chave_do_registro: One-time migration from legacy storage entries.
"""

from __future__ import annotations

from z7_officeletters.core.logging_setup import logger

__all__ = [
    "KEYRING_SERVICE",
    "KEYRING_USERNAME",
    "KEYRING_MODEL_USERNAME",
    "KEYRING_FALLBACK_MODEL_USERNAME",
    "KEYRING_ACCOUNT_USERNAME",
    "DEFAULT_MODELO_IA",
    "DEFAULT_MODELO_FALLBACK",
    "salvar_api_key",
    "carregar_api_key",
    "salvar_modelo_ia",
    "carregar_modelo_ia",
    "salvar_modelo_fallback",
    "carregar_modelo_fallback",
    "salvar_conta",
    "carregar_conta",
    "migrar_chave_do_registro",
]

KEYRING_SERVICE: str = "z7_officeletters"
KEYRING_USERNAME: str = "openrouter_api_key"
KEYRING_MODEL_USERNAME: str = "openrouter_model"
KEYRING_FALLBACK_MODEL_USERNAME: str = "openrouter_fallback_model"
KEYRING_ACCOUNT_USERNAME: str = "google_account"
DEFAULT_MODELO_IA: str = "deepseek/deepseek-chat"
DEFAULT_MODELO_FALLBACK: str = "google/gemini-2.5-flash"
DEFAULT_CONTA: str = "sentineltray"
DEFAULT_API_KEY: str = ""


def salvar_api_key(chave: str) -> None:
    """Persist the OpenRouter API key in the Windows Credential Manager.

    Also sets the ``OPENROUTER_API_KEY`` environment variable in the current
    process so that libraries that read ``os.environ`` pick it up immediately.

    Args:
        chave: The OpenRouter API key string to store.
    """
    import keyring  # noqa: PLC0415 — lazy: avoids ~500 ms startup cost
    import os  # noqa: PLC0415

    keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, chave)
    os.environ["OPENROUTER_API_KEY"] = chave
    logger.info("OPENROUTER_API_KEY persistida no Credential Manager do Windows.")


def carregar_api_key() -> str:
    """Retrieve the OpenRouter API key from the Windows Credential Manager.

    Returns:
        The stored API key, or the default API key if none is found.
    """
    import keyring  # noqa: PLC0415

    key = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
    if not key:
        # Fallback for legacy key name
        legacy_key = keyring.get_password(KEYRING_SERVICE, "gemini_api_key")
        if legacy_key:
            salvar_api_key(legacy_key)
            return legacy_key
    return key or DEFAULT_API_KEY


def salvar_modelo_ia(modelo: str) -> None:
    """Persist the AI model name in the Windows Credential Manager.

    Args:
        modelo: The model name string to store (e.g. ``"deepseek/deepseek-chat"``).
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

    modelo = keyring.get_password(KEYRING_SERVICE, KEYRING_MODEL_USERNAME)
    _legacy_models = {"gemini-2.5-flash", "meta-llama/llama-3.3-70b-instruct:free"}
    if not modelo or modelo in _legacy_models:
        return DEFAULT_MODELO_IA
    return modelo


def salvar_modelo_fallback(modelo: str) -> None:
    """Persist the fallback AI model name in the Windows Credential Manager.

    Args:
        modelo: The fallback model name string to store
            (e.g. ``"google/gemini-2.5-flash"``).
    """
    import keyring  # noqa: PLC0415

    keyring.set_password(KEYRING_SERVICE, KEYRING_FALLBACK_MODEL_USERNAME, modelo)
    logger.info("Modelo fallback IA '%s' persistido no Credential Manager.", modelo)


def carregar_modelo_fallback() -> str:
    """Retrieve the stored fallback AI model name from the Windows Credential Manager.

    Returns:
        The stored fallback model name, or :data:`DEFAULT_MODELO_FALLBACK`
        if none is found.
    """
    import keyring  # noqa: PLC0415

    modelo = keyring.get_password(KEYRING_SERVICE, KEYRING_FALLBACK_MODEL_USERNAME)
    if not modelo:
        return DEFAULT_MODELO_FALLBACK
    return modelo


def salvar_conta(conta: str) -> None:
    """Persist the user account e-mail in the Windows Credential Manager."""
    import keyring  # noqa: PLC0415

    keyring.set_password(KEYRING_SERVICE, KEYRING_ACCOUNT_USERNAME, conta)


def carregar_conta() -> str:
    """Retrieve the stored user account e-mail, or the default account."""
    import keyring  # noqa: PLC0415

    return keyring.get_password(KEYRING_SERVICE, KEYRING_ACCOUNT_USERNAME) or DEFAULT_CONTA


def migrar_chave_do_registro() -> None:
    """Migrate a plain-text API key from the Windows Registry to Credential Manager.

    This one-time migration reads the ``GEMINI_API_KEY`` or ``OPENROUTER_API_KEY``
    value stored in ``HKCU\\Environment`` (the legacy storage location), saves it securely via
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
            for reg_var in ("OPENROUTER_API_KEY", "GEMINI_API_KEY"):
                try:
                    value, _ = winreg.QueryValueEx(reg, reg_var)
                except FileNotFoundError:
                    continue

                if value:
                    salvar_api_key(value)
                    logger.info("%s migrada do registro para o Credential Manager.", reg_var)

                try:
                    winreg.DeleteValue(reg, reg_var)
                    logger.info("Valor %s removido do registro do Windows.", reg_var)
                except FileNotFoundError:
                    pass

    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha ao migrar chave do registro: %s", exc)

