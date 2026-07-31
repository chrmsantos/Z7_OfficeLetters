"""OpenRouter API key dialog.

Shows a secure entry field for the user to paste their OpenRouter API key, with
a toggle to reveal/hide the key and a Save button that persists the key to
the Windows Credential Manager.

Public exports:
    show_api_key_dialog: Open the API key editor dialog.
"""

from __future__ import annotations

from tkinter import messagebox
from typing import Callable

import customtkinter as ctk

from z7_officeletters.gui.constants import _C

__all__ = ["show_api_key_dialog"]


def show_api_key_dialog(
    parent: ctk.CTk,
    apikey_var: ctk.StringVar,
    has_key: Callable[[], bool],
    on_saved: Callable[[str], None],
) -> None:
    """Open the OpenRouter API key editor dialog.

    Args:
        parent: The root window (used to centre the dialog).
        apikey_var: StringVar bound to the entry widget.
        has_key: Callable returning ``True`` if a key is already stored.
        on_saved: Callback invoked with the new key string after a successful save.
    """
    from z7_officeletters.core.api_key import salvar_api_key  # noqa: PLC0415

    apikey_visible: list[bool] = [False]

    dlg = ctk.CTkToplevel(parent)
    dlg.title("Chave de API (OpenRouter)")
    dlg.geometry("460x220")
    dlg.resizable(False, False)
    dlg.grab_set()
    dlg.configure(fg_color=_C["bg"])

    dlg.update_idletasks()
    px, py = parent.winfo_x(), parent.winfo_y()
    pw, ph = parent.winfo_width(), parent.winfo_height()
    dlg.geometry(f"460x220+{px + (pw - 460) // 2}+{py + (ph - 220) // 2}")

    ctk.CTkLabel(
        dlg, text="CHAVE OPENROUTER API",
        font=ctk.CTkFont(size=11, weight="bold"),
        text_color=_C["accent"], anchor="w",
    ).pack(fill="x", padx=20, pady=(18, 2))
    ctk.CTkFrame(dlg, height=1, fg_color=_C["border"]).pack(fill="x", padx=20, pady=(0, 10))

    api_frame = ctk.CTkFrame(dlg, fg_color="transparent")
    api_frame.pack(fill="x", padx=20)
    api_frame.grid_columnconfigure(0, weight=1)

    entry = ctk.CTkEntry(
        api_frame, textvariable=apikey_var,
        placeholder_text="Cole sua chave aqui…",
        font=ctk.CTkFont(size=13), height=42,
        show="•",
    )
    entry.grid(row=0, column=0, sticky="ew")
    entry.focus_set()

    def _toggle_visibility() -> None:
        apikey_visible[0] = not apikey_visible[0]
        entry.configure(show="" if apikey_visible[0] else "•")

    ctk.CTkButton(
        api_frame, text="👁", width=42, height=42,
        font=ctk.CTkFont(size=16),
        fg_color=_C["panel"], hover_color=_C["border"],
        text_color=_C["text"],
        command=_toggle_visibility,
    ).grid(row=0, column=1, padx=(6, 0))

    status_label = ctk.CTkLabel(
        dlg,
        text="✔  Chave configurada" if has_key() else "⚠  Chave não configurada",
        font=ctk.CTkFont(size=11),
        text_color=_C["success"] if has_key() else _C["warn"],
        anchor="w",
    )
    status_label.pack(fill="x", padx=22, pady=(4, 0))

    def _update_status(*_: object) -> None:
        hk = has_key() or bool(apikey_var.get().strip())
        try:
            status_label.configure(
                text="✔  Chave configurada" if hk else "⚠  Chave não configurada",
                text_color=_C["success"] if hk else _C["warn"],
            )
        except Exception:  # noqa: BLE001
            pass

    trace_id = apikey_var.trace_add("write", _update_status)

    def _save_key() -> None:
        api_key = apikey_var.get().strip()
        if not api_key:
            messagebox.showwarning("Chave de API", "Informe uma chave para salvar.", parent=dlg)
            return
        try:
            salvar_api_key(api_key)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(
                "Chave de API",
                f"Não foi possível salvar a chave.\n\n{exc}",
                parent=dlg,
            )
            return

        on_saved(api_key)
        apikey_var.set("")
        messagebox.showinfo("Chave de API", "Chave salva com sucesso.", parent=dlg)

    btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
    btn_frame.pack(fill="x", padx=20, pady=(14, 0))
    btn_frame.grid_columnconfigure(0, weight=1)
    btn_frame.grid_columnconfigure(1, weight=1)

    ctk.CTkButton(
        btn_frame, text="Salvar",
        font=ctk.CTkFont(size=12), height=34, corner_radius=10,
        fg_color=_C["accent"], hover_color=_C["accent2"],
        text_color="#ffffff",
        command=_save_key,
    ).grid(row=0, column=0, sticky="ew", padx=(0, 3))

    ctk.CTkButton(
        btn_frame, text="Fechar",
        font=ctk.CTkFont(size=12), height=34, corner_radius=10,
        fg_color=_C["panel"], hover_color=_C["border"],
        text_color=_C["dim"],
        border_width=1, border_color=_C["border"],
        command=dlg.destroy,
    ).grid(row=0, column=1, sticky="ew", padx=(3, 0))

    def _on_close() -> None:
        apikey_var.trace_remove("write", trace_id)
        dlg.destroy()

    dlg.protocol("WM_DELETE_WINDOW", _on_close)
