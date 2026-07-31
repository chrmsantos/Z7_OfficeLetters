"""AI prompt template editor dialog.

Displays the current prompt templates in a tabbed editor so the user can
customise both the moção template and the requerimento de pesar template.
Each template is validated for the ``{texto_mocao}`` placeholder before
being saved to disk and hot-reloaded into ``core.ai``.

Public exports:
    show_prompt_editor: Open the prompt editor dialog.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from z7_officeletters.gui.constants import _C

__all__ = ["show_prompt_editor"]


def show_prompt_editor(parent: ctk.CTk) -> None:
    """Open the AI prompt template editor dialog.

    Args:
        parent: The root window (used to centre the dialog).
    """
    import z7_officeletters.core.ai as _ai  # noqa: PLC0415

    dlg = ctk.CTkToplevel(parent)
    dlg.title("Editor de Prompt IA")
    dlg.geometry("700x600")
    dlg.resizable(True, True)
    dlg.grab_set()
    dlg.configure(fg_color=_C["bg"])

    dlg.update_idletasks()
    px, py = parent.winfo_x(), parent.winfo_y()
    pw, ph = parent.winfo_width(), parent.winfo_height()
    dlg.geometry(f"700x600+{px + (pw - 700) // 2}+{py + (ph - 600) // 2}")

    ctk.CTkLabel(
        dlg, text="PROMPT DA IA",
        font=ctk.CTkFont(size=11, weight="bold"),
        text_color=_C["accent"], anchor="w",
    ).pack(fill="x", padx=20, pady=(18, 2))
    ctk.CTkFrame(dlg, height=1, fg_color=_C["border"]).pack(fill="x", padx=20, pady=(0, 8))

    ctk.CTkLabel(
        dlg,
        text="Use {texto_mocao} como marcador onde o texto da propositura será inserido.",
        font=ctk.CTkFont(size=11),
        text_color=_C["dim"],
        anchor="w",
    ).pack(fill="x", padx=20, pady=(0, 8))

    # ── Tab bar ────────────────────────────────────────────────────────────────
    _active_tab: list[int] = [0]  # 0 = moção, 1 = pesar

    tab_bar = ctk.CTkFrame(dlg, fg_color="transparent")
    tab_bar.pack(fill="x", padx=20, pady=(0, 4))

    editor_mocao = ctk.CTkTextbox(
        dlg,
        font=ctk.CTkFont(family="Consolas", size=12),
        fg_color=_C["panel"], text_color=_C["text"],
        corner_radius=10, wrap="word",
    )
    editor_pesar = ctk.CTkTextbox(
        dlg,
        font=ctk.CTkFont(family="Consolas", size=12),
        fg_color=_C["panel"], text_color=_C["text"],
        corner_radius=10, wrap="word",
    )
    editor_mocao.insert("1.0", _ai.PROMPT_TEMPLATE)
    editor_pesar.insert("1.0", _ai.PROMPT_TEMPLATE_PESAR)

    _tab_btns: list[ctk.CTkButton] = []

    def _switch_tab(idx: int) -> None:
        _active_tab[0] = idx
        if idx == 0:
            editor_pesar.pack_forget()
            editor_mocao.pack(fill="both", expand=True, padx=20, pady=(0, 8))
        else:
            editor_mocao.pack_forget()
            editor_pesar.pack(fill="both", expand=True, padx=20, pady=(0, 8))
        for i, btn in enumerate(_tab_btns):
            btn.configure(
                fg_color=_C["accent"] if i == idx else _C["panel"],
                text_color="#ffffff" if i == idx else _C["dim"],
            )

    for i, label in enumerate(["Moção", "Req. de Pesar"]):
        btn = ctk.CTkButton(
            tab_bar, text=label,
            font=ctk.CTkFont(size=12), height=30, corner_radius=6,
            fg_color=_C["panel"], hover_color=_C["border"],
            text_color=_C["dim"], border_width=1, border_color=_C["border"],
            command=lambda i=i: _switch_tab(i),
        )
        btn.pack(side="left", padx=(0, 4))
        _tab_btns.append(btn)

    _switch_tab(0)

    # ── Bottom action bar ──────────────────────────────────────────────────────
    bot = ctk.CTkFrame(dlg, fg_color=_C["card"], corner_radius=0, height=58)
    bot.pack(fill="x", side="bottom")
    bot.pack_propagate(False)
    bot.grid_columnconfigure(0, weight=1)

    def _restore_default() -> None:
        if _active_tab[0] == 0:
            editor_mocao.delete("1.0", "end")
            editor_mocao.insert("1.0", _ai.PROMPT_TEMPLATE_PADRAO)
        else:
            editor_pesar.delete("1.0", "end")
            editor_pesar.insert("1.0", _ai.PROMPT_TEMPLATE_PESAR_PADRAO)

    def _save() -> None:
        # Save moção template
        tmpl_mocao: str = editor_mocao.get("1.0", "end-1c")
        if "{texto_mocao}" not in tmpl_mocao:
            messagebox.showwarning(
                "Marcador ausente",
                "O prompt de Moção deve conter o marcador {texto_mocao}.",
                parent=dlg,
            )
            _switch_tab(0)
            return
        # Save pesar template
        tmpl_pesar: str = editor_pesar.get("1.0", "end-1c")
        if "{texto_mocao}" not in tmpl_pesar:
            messagebox.showwarning(
                "Marcador ausente",
                "O prompt de Req. de Pesar deve conter o marcador {texto_mocao}.",
                parent=dlg,
            )
            _switch_tab(1)
            return
        try:
            _ai._prompt_file_path().write_text(tmpl_mocao, encoding="utf-8")  # noqa: SLF001
            _ai._prompt_pesar_file_path().write_text(tmpl_pesar, encoding="utf-8")  # noqa: SLF001
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Erro ao Salvar", str(exc), parent=dlg)
            return
        _ai.PROMPT_TEMPLATE = tmpl_mocao  # type: ignore[assignment]
        _ai.PROMPT_TEMPLATE_PESAR = tmpl_pesar  # type: ignore[assignment]
        messagebox.showinfo("Salvo", "Prompts salvos com sucesso!", parent=dlg)
        dlg.destroy()

    ctk.CTkButton(
        bot, text="↺  Padrão",
        font=ctk.CTkFont(size=13), height=38, width=110, corner_radius=8,
        fg_color=_C["panel"], hover_color=_C["border"], text_color=_C["warn"],
        command=_restore_default,
    ).grid(row=0, column=0, sticky="w", padx=(20, 0), pady=10)

    ctk.CTkButton(
        bot, text="Cancelar",
        font=ctk.CTkFont(size=13), height=38, width=110, corner_radius=8,
        fg_color=_C["panel"], hover_color=_C["border"], text_color=_C["dim"],
        command=dlg.destroy,
    ).grid(row=0, column=1, sticky="e", padx=(0, 8), pady=10)

    ctk.CTkButton(
        bot, text="💾  Salvar",
        font=ctk.CTkFont(size=13, weight="bold"), height=38, width=110,
        corner_radius=8, fg_color=_C["accent"], hover_color=_C["accent2"],
        text_color="#ffffff", command=_save,
    ).grid(row=0, column=2, sticky="e", padx=(0, 20), pady=10)

    dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)

