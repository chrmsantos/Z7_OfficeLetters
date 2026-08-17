"""Cleanup confirmation dialog.

Shows a modal warning that lists the output folders whose contents will be
moved to the Recycle Bin before the next generation run, and asks the user to
confirm or cancel.

Public exports:
    confirm_cleanup: Show the confirmation dialog; return ``True`` if confirmed.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import customtkinter as ctk

from z7_officeletters.gui.constants import _C

if TYPE_CHECKING:
    pass

__all__ = ["confirm_cleanup"]


def confirm_cleanup(parent: ctk.CTk, total_files: int, pasta_saida: str, pasta_planilha: str, pasta_propos_fonte: str = "") -> bool:
    """Show a modal warning and ask the user to confirm the cleanup.

    Args:
        parent: The root window (used to centre the dialog).
        total_files: Total number of files that will be moved to the Recycle Bin.
        pasta_saida: Path string of the output (letters) folder.
        pasta_planilha: Path string of the spreadsheet folder.
        pasta_propos_fonte: Path string of the proposituras source folder (optional).

    Returns:
        ``True`` if the user clicks "Prosseguir", ``False`` otherwise.
    """
    if total_files == 0:
        return True

    confirmado: list[bool] = [False]

    dlg = ctk.CTkToplevel(parent)
    dlg.title("Confirmar execução")
    dlg.resizable(False, False)
    dlg.grab_set()
    dlg.configure(fg_color=_C["bg"])
    dlg.update_idletasks()

    pw, ph = parent.winfo_width(), parent.winfo_height()
    px, py = parent.winfo_x(), parent.winfo_y()
    W, H = 460, 230
    dlg.geometry(f"{W}x{H}+{px + (pw - W) // 2}+{py + (ph - H) // 2}")

    ctk.CTkLabel(
        dlg, text="⚠  Atenção",
        font=ctk.CTkFont(size=15, weight="bold"),
        text_color=_C["text"],
    ).pack(padx=24, pady=(20, 6), anchor="w")

    ctk.CTkFrame(dlg, height=1, fg_color=_C["border"]).pack(fill="x", padx=20, pady=(0, 10))

    _nomes = [
        "  • " + Path(pasta_saida).name,
        "  • " + Path(pasta_planilha).name,
    ]
    if pasta_propos_fonte:
        _nomes.append("  • " + Path(pasta_propos_fonte).name)
    _desc = (
        f"Os {total_files} arquivo(s) nas pastas abaixo serão enviados para a Lixeira "
        f"antes da geração:\n\n" + "\n".join(_nomes)
    )
    ctk.CTkLabel(
        dlg, text=_desc,
        font=ctk.CTkFont(size=12),
        text_color=_C["dim"],
        justify="left", wraplength=420,
    ).pack(padx=24, pady=(0, 16), anchor="w")

    btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
    btn_frame.pack(fill="x", padx=20, pady=(0, 18))
    btn_frame.grid_columnconfigure(0, weight=1)
    btn_frame.grid_columnconfigure(1, weight=1)

    def _confirmar() -> None:
        confirmado[0] = True
        dlg.destroy()

    def _cancelar() -> None:
        dlg.destroy()

    ctk.CTkButton(
        btn_frame, text="Prosseguir",
        font=ctk.CTkFont(size=12), height=34, corner_radius=10,
        fg_color=_C["accent"], hover_color=_C["accent2"],
        text_color="#ffffff",
        command=_confirmar,
    ).grid(row=0, column=0, sticky="ew", padx=(0, 3))

    ctk.CTkButton(
        btn_frame, text="Cancelar",
        font=ctk.CTkFont(size=12), height=34, corner_radius=10,
        fg_color=_C["panel"], hover_color=_C["border"],
        text_color=_C["dim"],
        border_width=1, border_color=_C["border"],
        command=_cancelar,
    ).grid(row=0, column=1, sticky="ew", padx=(3, 0))

    dlg.protocol("WM_DELETE_WINDOW", _cancelar)
    dlg.wait_window()
    return confirmado[0]
