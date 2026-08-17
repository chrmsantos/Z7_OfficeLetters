"""AI API settings dialog.

Shows fields for the OpenRouter API key and AI model name. The "Salvar" button
persists both values and closes the dialog. A separate "Testar Modelo" button
performs a live connection test and displays the result in an output area.

Public exports:
    show_ai_api_dialog: Open the AI API settings dialog.
"""

from __future__ import annotations

import re
import threading
import webbrowser
from typing import Callable

import customtkinter as ctk

from z7_officeletters.core.api_key import DEFAULT_MODELO_IA, DEFAULT_MODELO_FALLBACK
from z7_officeletters.gui.constants import _C

__all__ = ["show_ai_api_dialog"]

_RE_API_KEY: re.Pattern[str] = re.compile(r"^(sk-or-v1-[0-9a-zA-F]{64}|sk-[0-9A-Za-z\-_]{16,}|[0-9A-Za-z\-_]{16,})$")


def show_ai_api_dialog(
    parent: ctk.CTk,
    apikey_var: ctk.StringVar,
    modelo_ia_var: ctk.StringVar,
    modelo_fallback_var: ctk.StringVar,
    get_stored_key: Callable[[], str],
    on_saved: Callable[[str, str], None],
) -> None:
    """Open the AI API settings dialog.

    Args:
        parent: The root window (used to centre the dialog).
        apikey_var: StringVar bound to the API key entry.
        modelo_ia_var: StringVar bound to the model name entry.
        modelo_fallback_var: StringVar bound to the fallback model name entry.
        get_stored_key: Callable returning the currently persisted key (empty if none).
        on_saved: Callback invoked with ``(api_key, modelo)`` after a successful save.
    """
    from z7_officeletters.core.api_key import salvar_api_key, salvar_modelo_ia, salvar_modelo_fallback, salvar_conta, carregar_conta  # noqa: PLC0415
    import z7_officeletters.core.ai as _ai  # noqa: PLC0415

    _stored_key = get_stored_key()

    # Segurança: nunca exibir a chave armazenada no campo de entrada.
    # O campo começa vazio; o usuário pode digitar uma nova chave.
    apikey_var.set("")

    dlg = ctk.CTkToplevel(parent)
    dlg.title("API de IA (OpenRouter)")
    dlg.geometry("480x700")
    dlg.resizable(False, False)
    dlg.grab_set()
    dlg.configure(fg_color=_C["bg"])

    dlg.update_idletasks()
    px, py = parent.winfo_x(), parent.winfo_y()
    pw, ph = parent.winfo_width(), parent.winfo_height()
    dlg.geometry(f"480x700+{px + (pw - 480) // 2}+{py + (ph - 700) // 2}")

    # ── Section: API Key ───────────────────────────────────────────────────────
    ctk.CTkLabel(
        dlg, text="CHAVE OPENROUTER API",
        font=ctk.CTkFont(size=11, weight="bold"),
        text_color=_C["accent"], anchor="w",
    ).pack(fill="x", padx=20, pady=(18, 2))
    ctk.CTkFrame(dlg, height=1, fg_color=_C["border"]).pack(fill="x", padx=20, pady=(0, 8))

    _current_key = get_stored_key() or apikey_var.get().strip()
    _status_lbl = ctk.CTkLabel(
        dlg,
        text="✔  Chave configurada" if _current_key else "⚠  Chave não configurada",
        font=ctk.CTkFont(size=12),
        text_color=_C["success"] if _current_key else _C["warn"],
        anchor="w",
    )
    _status_lbl.pack(fill="x", padx=22, pady=(0, 2))

    _conta_atual = carregar_conta()
    conta_var = ctk.StringVar(value=_conta_atual)
    _conta_row = ctk.CTkFrame(dlg, fg_color="transparent")
    _conta_row.pack(fill="x", padx=22, pady=(0, 6))
    ctk.CTkLabel(
        _conta_row, text="Conta:",
        font=ctk.CTkFont(size=11),
        text_color=_C["dim"], width=52, anchor="w",
    ).pack(side="left")
    ctk.CTkEntry(
        _conta_row, textvariable=conta_var,
        placeholder_text="seu@email.com",
        font=ctk.CTkFont(size=11), height=26,
        fg_color=_C["panel"], border_color=_C["border"],
        text_color=_C["text"],
    ).pack(side="left", fill="x", expand=True)

    api_frame = ctk.CTkFrame(dlg, fg_color="transparent")
    api_frame.pack(fill="x", padx=20)
    api_frame.grid_columnconfigure(0, weight=1)

    api_entry = ctk.CTkEntry(
        api_frame, textvariable=apikey_var,
        placeholder_text="Cole sua chave sk-or-v1-… aqui",
        font=ctk.CTkFont(size=13), height=36,
        show="•",
    )
    api_entry.grid(row=0, column=0, sticky="ew")
    api_entry.focus_set()

    # ── Section: AI Model ──────────────────────────────────────────────────────
    ctk.CTkLabel(
        dlg, text="MODELO IA",
        font=ctk.CTkFont(size=11, weight="bold"),
        text_color=_C["accent"], anchor="w",
    ).pack(fill="x", padx=20, pady=(14, 2))
    ctk.CTkFrame(dlg, height=1, fg_color=_C["border"]).pack(fill="x", padx=20, pady=(0, 8))

    model_frame = ctk.CTkFrame(dlg, fg_color="transparent")
    model_frame.pack(fill="x", padx=20)
    model_frame.grid_columnconfigure(0, weight=1)

    ctk.CTkEntry(
        model_frame, textvariable=modelo_ia_var,
        placeholder_text=f"Ex: {DEFAULT_MODELO_IA}",
        font=ctk.CTkFont(size=13), height=36,
    ).grid(row=0, column=0, sticky="ew")

    # ── Section: Fallback Model ───────────────────────────────────────────────
    ctk.CTkLabel(
        dlg, text="MODELO FALLBACK (alternativa temporária)",
        font=ctk.CTkFont(size=11, weight="bold"),
        text_color=_C["accent"], anchor="w",
    ).pack(fill="x", padx=20, pady=(14, 2))
    ctk.CTkFrame(dlg, height=1, fg_color=_C["border"]).pack(fill="x", padx=20, pady=(0, 8))

    fallback_frame = ctk.CTkFrame(dlg, fg_color="transparent")
    fallback_frame.pack(fill="x", padx=20)
    fallback_frame.grid_columnconfigure(0, weight=1)

    ctk.CTkEntry(
        fallback_frame, textvariable=modelo_fallback_var,
        placeholder_text=f"Ex: {DEFAULT_MODELO_FALLBACK}",
        font=ctk.CTkFont(size=13), height=36,
    ).grid(row=0, column=0, sticky="ew")

    ctk.CTkLabel(
        dlg,
        text="Usado automaticamente quando o modelo principal estiver lento/indisponível.",
        font=ctk.CTkFont(size=10),
        text_color=_C["dim"], anchor="w",
    ).pack(fill="x", padx=22, pady=(2, 0))

    # ── Output area ────────────────────────────────────────────────────────────
    ctk.CTkLabel(
        dlg, text="SAÍDA",
        font=ctk.CTkFont(size=10, weight="bold"),
        text_color=_C["dim"], anchor="w",
    ).pack(fill="x", padx=22, pady=(14, 2))

    output_box = ctk.CTkTextbox(
        dlg,
        font=ctk.CTkFont(family="Consolas", size=11),
        fg_color=_C["panel"], text_color=_C["text"],
        corner_radius=8, height=130,
        state="disabled",
    )
    output_box.pack(fill="x", padx=20)

    tb = output_box._textbox  # type: ignore[attr-defined]
    tb.tag_config("success", foreground=_C["success"])
    tb.tag_config("error",   foreground=_C["error"])
    tb.tag_config("warn",    foreground=_C["warn"])
    tb.tag_config("dim",     foreground=_C["dim"])

    def _append(text: str, tag: str = "") -> None:
        tb.configure(state="normal")
        if tag:
            tb.insert("end", text + "\n", tag)
        else:
            tb.insert("end", text + "\n")
        tb.see("end")
        tb.configure(state="disabled")

    def _clear_output() -> None:
        tb.configure(state="normal")
        tb.delete("1.0", "end")
        tb.configure(state="disabled")

    # ── Buttons ────────────────────────────────────────────────────────────────
    save_btn = ctk.CTkButton(
        dlg,
        text="💾  Salvar",
        font=ctk.CTkFont(size=13, weight="bold"),
        height=44, corner_radius=10,
        fg_color=_C["accent"], hover_color=_C["accent2"],
        text_color="#ffffff",
    )
    save_btn.pack(fill="x", padx=20, pady=(14, 4))

    test_btn = ctk.CTkButton(
        dlg,
        text="🧪  Testar Modelo",
        font=ctk.CTkFont(size=12),
        height=36, corner_radius=8,
        fg_color=_C["panel"], hover_color=_C["border"],
        text_color=_C["text"], border_width=1, border_color=_C["border"],
    )
    test_btn.pack(fill="x", padx=20, pady=(0, 4))

    ctk.CTkButton(
        dlg,
        text="🌐  OpenRouter Keys",
        font=ctk.CTkFont(size=12),
        height=32, corner_radius=8,
        fg_color="transparent", hover_color=_C["border"],
        text_color=_C["dim"], border_width=1, border_color=_C["border"],
        command=lambda: webbrowser.open("https://openrouter.ai/keys"),
    ).pack(fill="x", padx=20, pady=(0, 20))

    def _validate_inputs() -> tuple[str, str] | None:
        """Validate inputs and return (effective_key, model) or None on failure."""
        _clear_output()
        api_key = apikey_var.get().strip()
        modelo = modelo_ia_var.get().strip()
        effective_key = api_key or get_stored_key()

        if not effective_key:
            _append("⚠  Informe uma chave de API.", "warn")
            return None
        if not modelo:
            _append("⚠  Informe um nome de modelo.", "warn")
            return None
        if api_key and not _RE_API_KEY.match(api_key):
            _append(
                "✘  Formato de chave inválido.\n"
                '   Chaves OpenRouter costumam ter o formato "sk-or-v1-…".',
                "error",
            )
            return None
        return effective_key, modelo

    def _save_settings(api_key: str, modelo: str) -> None:
        """Persist API key, account and model to disk and update runtime state."""
        if api_key and api_key != get_stored_key():
            salvar_api_key(api_key)
            dlg.after(0, lambda: _append("✔  Chave salva.", "success"))
        else:
            dlg.after(0, lambda: _append("ℹ  Usando chave já armazenada.", "dim"))
        _conta = conta_var.get().strip()
        if _conta:
            salvar_conta(_conta)
        salvar_modelo_ia(modelo)
        _ai.MODELO_IA = modelo
        dlg.after(0, lambda: _append("✔  Modelo salvo.", "success"))
        modelo_fb = modelo_fallback_var.get().strip()
        if modelo_fb:
            salvar_modelo_fallback(modelo_fb)
            _ai.MODELO_FALLBACK = modelo_fb
            dlg.after(0, lambda: _append(f"✔  Modelo fallback salvo: {modelo_fb}", "success"))

    def _on_save() -> None:
        validated = _validate_inputs()
        if validated is None:
            return
        effective_key, modelo = validated

        save_btn.configure(state="disabled")
        test_btn.configure(state="disabled")
        _append("Salvando chave e modelo…", "dim")

        def _do_save() -> None:
            try:
                _save_settings(effective_key, modelo)
                dlg.after(0, lambda: _close_and_save(effective_key, modelo))
            except Exception as exc:  # noqa: BLE001
                err_msg = str(exc)
                dlg.after(0, lambda: _append(f"✘  Falha ao salvar: {err_msg}", "error"))
            finally:
                try:
                    dlg.after(0, lambda: (
                        save_btn.configure(state="normal"),
                        test_btn.configure(state="normal"),
                    ))
                except Exception:  # noqa: BLE001
                    pass

        threading.Thread(target=_do_save, daemon=True).start()

    def _on_test() -> None:
        validated = _validate_inputs()
        if validated is None:
            return
        effective_key, modelo = validated

        test_btn.configure(state="disabled")
        save_btn.configure(state="disabled")

        def _do_test() -> None:
            try:
                from openai import OpenAI  # noqa: PLC0415

                dlg.after(0, lambda: _append("Testando conexão com a API OpenRouter…", "dim"))

                cliente = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=effective_key,
                )
                response = cliente.chat.completions.create(
                    model=modelo,
                    messages=[{"role": "user", "content": "Responda apenas com a palavra: OK"}],
                )
                resp_text: str = ""
                if getattr(response, "choices", None) and len(response.choices) > 0:
                    resp_text = (response.choices[0].message.content or "").strip()

                if not resp_text:
                    raise ValueError("A IA não retornou conteúdo na resposta.")

                dlg.after(0, lambda: _append("✔  IA respondeu — configuração válida.", "success"))
                dlg.after(0, lambda: _append(f"   Resposta: {resp_text}"))

                try:
                    dlg.after(
                        0,
                        lambda: _status_lbl.configure(
                            text="✔  Chave configurada",
                            text_color=_C["success"],
                        ),
                    )
                except Exception:  # noqa: BLE001
                    pass

            except Exception as exc:  # noqa: BLE001
                err_msg = str(exc)
                dlg.after(0, lambda: _append(f"✘  Falha na validação: {err_msg}", "error"))
            finally:
                try:
                    dlg.after(0, lambda: (
                        test_btn.configure(state="normal"),
                        save_btn.configure(state="normal"),
                    ))
                except Exception:  # noqa: BLE001
                    pass

        threading.Thread(target=_do_test, daemon=True).start()

    def _close_and_save(effective_key: str, modelo: str) -> None:
        """Close the dialog after a successful save."""
        on_saved(effective_key, modelo)
        dlg.destroy()

    save_btn.configure(command=_on_save)
    test_btn.configure(command=_on_test)

    def _on_close() -> None:
        # Segurança: sempre limpar a chave digitada ao fechar sem salvar
        apikey_var.set("")
        dlg.destroy()

    dlg.protocol("WM_DELETE_WINDOW", _on_close)
