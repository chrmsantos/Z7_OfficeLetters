"""Main application window for Z7 OfficeLetters.

Composes all panels and dialogs into a single ``customtkinter`` window.
The class is intentionally large because it owns the complete UI state;
individual panels and dialogs are kept in their own modules to reduce
cognitive load when editing them.

Public exports:
    AutoOficiosApp: The root CTk window class; instantiate and call
        ``mainloop()`` to start the application.
"""

from __future__ import annotations

import json
import os
import queue
import re
import shutil
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
import tkinter as tk
from typing import Any

import customtkinter as ctk
import send2trash

from z7_officeletters import APP_VERSION, APP_AUTHOR
from z7_officeletters.constants import (
    MESES_PT,
    MODELO_OFICIO,
    MODELO_PLANILHA,
    MODELO_REQUERIMENTO_PESAR,
    MODELO_ENVELOPE,
    PASTA_LOGS,
    PASTA_PLANILHA,
    PASTA_SAIDA,
    PASTA_ENVELOPES,
    BASE_DIR,
    ENDERECAMENTO_PADRAO,
)
from z7_officeletters.core import config as _config
from z7_officeletters.core.documents import criar_modelo_planilha, criar_modelo_envelope
from z7_officeletters.core.api_key import carregar_api_key, migrar_chave_do_registro, carregar_modelo_ia
from z7_officeletters.core.logging_setup import configurar_logging
from z7_officeletters.gui.constants import _C, _DARK, _LIGHT
from z7_officeletters.gui.workers.processor import run_processing_worker
from z7_officeletters.core.updater import obter_ultima_versao, comparar_versoes

__all__ = ["AutoOficiosApp"]


class AutoOficiosApp(ctk.CTk):
    """Root application window."""

    def __init__(self) -> None:
        super().__init__()
        self._theme: str = "light"
        ctk.set_appearance_mode("light")
        self._load_saved_theme()

        self.title(f"Z7 OfficeLetters v{APP_VERSION} — Gerador Legislativo")
        self.geometry("1140x680")
        self.minsize(920, 580)
        self.configure(fg_color=_C["bg"])

        _icon = Path(__file__).parent.parent.parent.parent / "icon.ico"
        if _icon.exists():
            self.iconbitmap(str(_icon))

        self._queue: queue.Queue[tuple[Any, ...]] = queue.Queue()
        self._processing = False
        self._proc_start_time: float = 0.0
        self._cancel_event = threading.Event()
        self._prop_paths: list[str] = []
        self._stored_key: str = ""
        self._log_entries: list[tuple[str, str]] = []  # (text, tag) for theme rebuild
        self._log_has_placeholder: bool = False
        self._summary_color_tag = "dim"
        self._progress_color_tag = "accent"
        self._prog_label_color_tag = "dim"
        self._prog_pct_color_tag = "accent"

        # AI Chat state variables
        self._chat_history: list[dict[str, str]] = []
        self._custom_instructions: str = ""
        self._showing_chat: bool = True

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._post_startup_greeting()
        self.after(0, self._maximize_on_startup)
        threading.Thread(target=self._run_init_bg, daemon=True).start()
        self._poll_queue()

    # =========================================================================
    # Startup helpers
    # =========================================================================
    def _maximize_on_startup(self) -> None:
        try:
            self.state("zoomed")
            return
        except tk.TclError:
            pass
        try:
            self.attributes("-zoomed", True)
            return
        except tk.TclError:
            pass
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        self.geometry(f"{screen_w}x{screen_h}+0+0")

    def _run_init_sync(self) -> None:
        """Legacy name kept for compat — delegates to the background worker."""
        pass

    def _run_init_bg(self) -> None:
        for p in (PASTA_LOGS, PASTA_SAIDA, PASTA_PLANILHA, PASTA_ENVELOPES):
            Path(p).mkdir(parents=True, exist_ok=True)
        configurar_logging()

        # Clean up any leftover old executable from a previous update
        try:
            old_exe = Path(sys.executable + ".old")
            if old_exe.exists():
                old_exe.unlink()
        except Exception:
            pass
        try:
            if getattr(sys, "frozen", False):
                modelo = Path(sys.executable).parent / MODELO_PLANILHA
            else:
                modelo = Path(__file__).parent.parent.parent.parent / MODELO_PLANILHA
            if not modelo.exists():
                criar_modelo_planilha(modelo)
        except Exception:  # noqa: BLE001
            pass
        try:
            if getattr(sys, "frozen", False):
                modelo_env = Path(sys.executable).parent / MODELO_ENVELOPE
            else:
                modelo_env = Path(__file__).parent.parent.parent.parent / MODELO_ENVELOPE
            if not modelo_env.exists():
                criar_modelo_envelope(modelo_env)
        except Exception:  # noqa: BLE001
            pass
        # Copy bundled .docx templates next to the exe so the user can edit them.
        if getattr(sys, "frozen", False):
            try:
                _meipass = Path(getattr(sys, "_MEIPASS", ""))
                _exe_dir = Path(sys.executable).parent
                for tmpl in (MODELO_OFICIO, MODELO_REQUERIMENTO_PESAR, MODELO_ENVELOPE):
                    dest = _exe_dir / tmpl
                    if not dest.exists():
                        src = _meipass / tmpl
                        if src.exists():
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(src, dest)
            except Exception:  # noqa: BLE001
                pass

        loaded_key = ""
        loaded_model = ""
        try:
            migrar_chave_do_registro()
            loaded_key = carregar_api_key()
            loaded_model = carregar_modelo_ia()
        except Exception:  # noqa: BLE001
            pass

        session_state: dict[str, Any] = {}
        try:
            session_path = Path(BASE_DIR) / "last_session.json"
            if session_path.exists():
                session_state = json.loads(session_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass

        self.after(0, lambda: self._on_init_ready(loaded_key, loaded_model, session_state))

    def _on_init_ready(
        self,
        loaded_key: str,
        loaded_model: str,
        session_state: dict[str, Any],
    ) -> None:
        self._stored_key = loaded_key
        if loaded_model:
            self._modelo_ia_var.set(loaded_model)
            import z7_officeletters.core.ai as _ai  # noqa: PLC0415
            _ai.MODELO_IA = loaded_model

        self._update_ai_status()

        if "numero_oficio" in session_state:
            self._num_var.set(session_state["numero_oficio"])
        if "redator" in session_state:
            self._sigla_var.set(session_state["redator"])
        if "data" in session_state:
            self._data_var.set(session_state["data"])

        saved_props = [p for p in session_state.get("proposituras", []) if Path(p).exists()]
        self._prop_paths = saved_props

        if "summary_text" in session_state:
            self._summary_color_tag = session_state.get("summary_color_tag", "dim")
            self._summary_label.configure(
                text=session_state["summary_text"],
                text_color=_C.get(self._summary_color_tag, _C["dim"]),
            )
        
        if "progress_value" in session_state:
            self._progress.set(session_state["progress_value"])
            self._progress_color_tag = session_state.get("progress_color_tag", "accent")
            self._progress.configure(
                progress_color=_C.get(self._progress_color_tag, _C["accent"])
            )
            
        if "prog_label_text" in session_state:
            self._prog_label_color_tag = session_state.get("prog_label_color_tag", "dim")
            self._prog_label.configure(
                text=session_state["prog_label_text"],
                text_color=_C.get(self._prog_label_color_tag, _C["dim"]),
            )
            
        if "prog_pct_text" in session_state:
            self._prog_pct_color_tag = session_state.get("prog_pct_color_tag", "accent")
            self._prog_pct.configure(
                text=session_state["prog_pct_text"],
                text_color=_C.get(self._prog_pct_color_tag, _C["accent"]),
            )

        if "log_entries" in session_state:
            self._log_entries = []
            tb = self._log_box._textbox  # type: ignore[attr-defined]  # noqa: SLF001
            tb.configure(state="normal")
            tb.delete("1.0", "end")
            
            log_has_placeholder = session_state.get("log_has_placeholder", False)
            self._log_has_placeholder = log_has_placeholder
            
            for entry in session_state["log_entries"]:
                text, tag = entry[0], entry[1]
                self._log_entries.append((text, tag))
                if tag:
                    tb.insert("end", text + "\n", tag)
                else:
                    tb.insert("end", text + "\n")
            tb.see("end")
            tb.configure(state="disabled")
        self._prop_listbox.delete(0, tk.END)
        for p in saved_props:
            self._prop_listbox.insert(tk.END, Path(p).name)

    def _load_saved_theme(self) -> None:
        try:
            session_path = Path(BASE_DIR) / "last_session.json"
            if session_path.exists():
                saved = json.loads(session_path.read_text(encoding="utf-8"))
                saved_theme = saved.get("theme", "light")
                if saved_theme != self._theme:
                    self._theme = saved_theme
                    ctk.set_appearance_mode(saved_theme)
                    _C.clear()
                    _C.update(_LIGHT if saved_theme == "light" else _DARK)
        except Exception:  # noqa: BLE001
            pass

    def _save_session_state(self) -> None:
        state: dict[str, Any] = {
            "numero_oficio": self._num_var.get(),
            "redator": self._sigla_var.get(),
            "data": self._data_var.get(),
            "proposituras": [p for p in self._prop_paths if Path(p).exists()],
            "theme": self._theme,
            "log_entries": self._log_entries,
            "log_has_placeholder": getattr(self, "_log_has_placeholder", False),
            "summary_text": self._summary_label.cget("text"),
            "summary_color_tag": getattr(self, "_summary_color_tag", "dim"),
            "progress_value": self._progress.get(),
            "progress_color_tag": getattr(self, "_progress_color_tag", "accent"),
            "prog_label_text": self._prog_label.cget("text"),
            "prog_label_color_tag": getattr(self, "_prog_label_color_tag", "dim"),
            "prog_pct_text": self._prog_pct.cget("text"),
            "prog_pct_color_tag": getattr(self, "_prog_pct_color_tag", "accent"),
        }
        try:
            session_path = Path(BASE_DIR) / "last_session.json"
            session_path.write_text(
                json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:  # noqa: BLE001
            pass

    # =========================================================================
    # UI Construction
    # =========================================================================
    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=0, minsize=370)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)

        self._build_header()
        self._build_left_panel()
        self._build_right_panel()
        self._build_footer()

    def _build_header(self) -> None:
        hdr = ctk.CTkFrame(self, fg_color=_C["card"], corner_radius=0, height=90)
        hdr.grid(row=0, column=0, columnspan=2, sticky="ew")
        hdr.grid_propagate(False)
        hdr.grid_columnconfigure(0, weight=1)
        hdr.grid_columnconfigure(1, weight=0)
        hdr.grid_columnconfigure(2, weight=0)

        title_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="w", padx=24, pady=(14, 0))
        title_frame.grid_columnconfigure(0, weight=0)

        name_row = ctk.CTkFrame(title_frame, fg_color="transparent")
        name_row.grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            name_row, text="Z7 OFFICELETTERS",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=_C["text"],
        ).pack(side="left")

        badge = ctk.CTkFrame(name_row, fg_color=_C["accent"], corner_radius=10)
        badge.pack(side="left", padx=(12, 0), pady=(2, 0))
        ctk.CTkLabel(
            badge, text=f"v{APP_VERSION}",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#ffffff",
        ).pack(padx=10, pady=(2, 3))

        ctk.CTkLabel(
            title_frame,
            text="Automatize ofícios legislativos com IA",
            font=ctk.CTkFont(size=12),
            text_color=_C["dim"],
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))

        # Update button
        self._update_btn = ctk.CTkButton(
            hdr,
            text="🔄  Atualizar",
            font=ctk.CTkFont(size=12),
            width=110, height=32, corner_radius=8,
            fg_color=_C["panel"], hover_color=_C["border"],
            text_color=_C["dim"],
            border_width=1, border_color=_C["border"],
            command=self._check_for_updates_user,
        )
        self._update_btn.grid(row=0, column=1, sticky="e", padx=(0, 10), pady=(30, 0))

        # Theme button
        _theme_icon = "☀" if self._theme == "dark" else "🌙"
        _theme_tip  = "Tema Claro" if self._theme == "dark" else "Tema Escuro"
        self._theme_btn = ctk.CTkButton(
            hdr,
            text=f"{_theme_icon}  {_theme_tip}",
            font=ctk.CTkFont(size=12),
            width=120, height=32, corner_radius=8,
            fg_color=_C["panel"], hover_color=_C["border"],
            text_color=_C["dim"],
            border_width=1, border_color=_C["border"],
            command=self._toggle_theme,
        )
        self._theme_btn.grid(row=0, column=2, sticky="e", padx=20, pady=(30, 0))

    def _build_left_panel(self) -> None:
        self._left = ctk.CTkFrame(self, fg_color=_C["card"], corner_radius=16)
        self._left.grid(row=1, column=0, sticky="nsew", padx=(14, 7), pady=12)
        self._left.grid_columnconfigure(0, weight=1)
        self._left.grid_rowconfigure(14, weight=1)

        self._section_title(self._left, 0, "CONFIGURAÇÃO")
        self._divider(self._left, 1)

        top_frame = ctk.CTkFrame(self._left, fg_color="transparent")
        top_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 14))
        top_frame.grid_columnconfigure(0, weight=2)
        top_frame.grid_columnconfigure(1, weight=1)
        top_frame.grid_columnconfigure(2, weight=2)

        for col, label in enumerate(["Nº do Ofício Inicial", "Redator", "Data dos Ofícios"]):
            ctk.CTkLabel(
                top_frame, text=label,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=_C["text"], anchor="w",
            ).grid(row=0, column=col, sticky="w", padx=(0 if col == 0 else 8, 0), pady=(0, 4))

        self._num_var = ctk.StringVar(value="1")
        num_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        num_frame.grid(row=1, column=0, sticky="ew")
        num_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            num_frame, text="−", width=36, height=42,
            font=ctk.CTkFont(size=18),
            fg_color=_C["panel"], hover_color=_C["border"],
            text_color=_C["text"], border_width=1, border_color=_C["border"],
            corner_radius=8,
            command=lambda: self._decrement_num(),
        ).grid(row=0, column=0)

        self._num_entry = ctk.CTkEntry(
            num_frame, textvariable=self._num_var,
            placeholder_text="Ex: 300",
            font=ctk.CTkFont(size=15), height=42, justify="center",
        )
        self._num_entry.grid(row=0, column=1, sticky="ew", padx=4)

        ctk.CTkButton(
            num_frame, text="+", width=36, height=42,
            font=ctk.CTkFont(size=18),
            fg_color=_C["panel"], hover_color=_C["border"],
            text_color=_C["text"], border_width=1, border_color=_C["border"],
            corner_radius=8,
            command=lambda: self._increment_num(),
        ).grid(row=0, column=2)

        self._sigla_var = ctk.StringVar()
        _redator_values = [f"{n} ({s})" for n, s in _config.MAPA_REDATORES.items()]
        self._sigla_combo = ctk.CTkComboBox(
            top_frame, variable=self._sigla_var,
            values=_redator_values,
            font=ctk.CTkFont(size=13), height=42,
            command=self._on_redator_selected,
        )
        self._sigla_combo.grid(row=1, column=1, sticky="ew", padx=(8, 0))

        self._data_var = ctk.StringVar(value=datetime.now().strftime("%d/%m/%Y"))
        self._data_btn = ctk.CTkButton(
            top_frame,
            textvariable=self._data_var,
            font=ctk.CTkFont(size=15), height=42, anchor="w",
            fg_color=_C["panel"], hover_color=_C["border"],
            text_color=_C["text"], border_width=2, border_color=_C["border"],
            command=self._open_date_picker,
        )
        self._data_btn.grid(row=1, column=2, sticky="ew", padx=(8, 0))

        self._field_label(self._left, 9, "Propositura(s)")

        _list_outer = ctk.CTkFrame(self._left, fg_color=_C["border"], corner_radius=8)
        _list_outer.grid(row=10, column=0, sticky="ew", padx=20, pady=(0, 6))
        _list_outer.grid_columnconfigure(0, weight=1)

        self._prop_listbox = tk.Listbox(
            _list_outer, height=4,
            font=("Segoe UI", 12),
            bg=_C["panel"], fg=_C["text"],
            selectbackground=_C["accent"], selectforeground="#ffffff",
            activestyle="none", bd=0, highlightthickness=0, relief="flat",
        )
        _sb = tk.Scrollbar(_list_outer, orient="vertical", command=self._prop_listbox.yview)
        self._prop_listbox.configure(yscrollcommand=_sb.set)
        self._prop_listbox.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        _sb.pack(side="right", fill="y", pady=4)

        prop_btn_frame = ctk.CTkFrame(self._left, fg_color="transparent")
        prop_btn_frame.grid(row=11, column=0, sticky="ew", padx=20, pady=(0, 12))
        prop_btn_frame.grid_columnconfigure(0, weight=1)
        prop_btn_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            prop_btn_frame, text="📂  Adicionar", height=34,
            font=ctk.CTkFont(size=12), corner_radius=8,
            fg_color=_C["panel"], hover_color=_C["border"],
            text_color=_C["text"], border_width=1, border_color=_C["border"],
            command=self._browse_file,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 3))

        ctk.CTkButton(
            prop_btn_frame, text="✕  Remover", height=34,
            font=ctk.CTkFont(size=12), corner_radius=8,
            fg_color=_C["panel"], hover_color=_C["border"],
            text_color=_C["error"], border_width=1, border_color=_C["border"],
            command=self._remove_propositura,
        ).grid(row=0, column=1, sticky="ew", padx=(3, 0))

        self._apikey_var = ctk.StringVar(value="")
        self._modelo_ia_var = ctk.StringVar(value="")
        self._action_frame = ctk.CTkFrame(self._left, fg_color="transparent")
        self._action_frame.grid(row=15, column=0, columnspan=1, sticky="ew", padx=20, pady=(0, 10))
        self._action_frame.grid_columnconfigure(0, weight=3)
        self._action_frame.grid_columnconfigure(1, weight=0)

        self._gen_btn = ctk.CTkButton(
            self._action_frame,
            text="⚡   GERAR OFÍCIOS",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=54, corner_radius=16,
            fg_color=_C["accent"], hover_color=_C["accent2"],
            text_color="#ffffff",
            command=self._start_processing,
        )
        self._gen_btn.grid(row=0, column=0, sticky="ew")

        self._cancel_btn = ctk.CTkButton(
            self._action_frame,
            text="⏹   CANCELAR",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=54, corner_radius=12,
            fg_color=_C["panel"], hover_color=_C["error"],
            text_color=_C["error"],
            border_width=1, border_color=_C["error"],
            command=self._request_cancel,
        )
        self._cancel_btn.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        self._cancel_btn.grid_remove()

        modelos_frame = ctk.CTkFrame(self._left, fg_color="transparent")
        modelos_frame.grid(row=17, column=0, sticky="ew", padx=20, pady=(0, 18))
        modelos_frame.grid_columnconfigure(0, weight=1)
        modelos_frame.grid_columnconfigure(1, weight=1)

        _btn_kw: dict[str, Any] = dict(
            font=ctk.CTkFont(size=12), height=34, corner_radius=10,
            fg_color=_C["panel"], hover_color=_C["border"],
            text_color=_C["dim"], border_width=1, border_color=_C["border"],
        )
        ctk.CTkButton(
            modelos_frame, text="🔧  Avançado",
            command=self._open_avancado, **_btn_kw,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 3))

        ctk.CTkButton(
            modelos_frame, text="🧹  Limpar",
            command=self._confirmar_e_limpar_tudo, **_btn_kw,
        ).grid(row=0, column=1, sticky="ew", padx=(3, 0))

        self._ai_status_label = ctk.CTkLabel(
            self._left, text="",
            font=ctk.CTkFont(size=11),
            text_color=_C["dim"], anchor="center",
        )
        self._ai_status_label.grid(row=18, column=0, sticky="ew", padx=20, pady=(6, 14))
        self._update_ai_status()

    def _build_right_panel(self) -> None:
        self._right = ctk.CTkFrame(self, fg_color=_C["card"], corner_radius=16)
        self._right.grid(row=1, column=1, sticky="nsew", padx=(7, 14), pady=12)
        self._right.grid_columnconfigure(0, weight=1)
        self._right.grid_rowconfigure(4, weight=1)

        self._section_title(self._right, 0, "LOG DE PROCESSAMENTO")
        self._divider(self._right, 1)

        prog_frame = ctk.CTkFrame(self._right, fg_color="transparent")
        prog_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 10))
        prog_frame.grid_columnconfigure(0, weight=1)

        self._progress = ctk.CTkProgressBar(
            prog_frame, height=16, corner_radius=8,
            progress_color=_C["accent"], fg_color=_C["panel"],
        )
        self._progress.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        self._progress.set(0)

        self._prog_label = ctk.CTkLabel(
            prog_frame, text="Aguardando início…",
            font=ctk.CTkFont(size=12), text_color=_C["dim"], anchor="w",
        )
        self._prog_label.grid(row=1, column=0, sticky="w")

        self._prog_pct = ctk.CTkLabel(
            prog_frame, text="0 %",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=_C["accent"],
        )
        self._prog_pct.grid(row=1, column=1, sticky="e")

        ctk.CTkLabel(
            self._right, text="SAÍDA",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=_C["dim"], anchor="w",
        ).grid(row=3, column=0, sticky="w", padx=22, pady=(4, 2))

        self._log_box = ctk.CTkTextbox(
            self._right,
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color=_C["panel"], text_color=_C["text"],
            corner_radius=10, activate_scrollbars=True, wrap="word",
            state="disabled",
        )
        self._log_box.grid(row=4, column=0, sticky="nsew", padx=20, pady=(0, 10))

        tb = self._log_box._textbox  # type: ignore[attr-defined]
        tb.tag_config("success", foreground=_C["success"])
        tb.tag_config("error",   foreground=_C["error"])
        tb.tag_config("warn",    foreground=_C["warn"])
        tb.tag_config("dim",     foreground=_C["dim"])
        tb.tag_config("accent",  foreground=_C["accent"])
        tb.tag_config("bold",        font=("Consolas", 12, "bold"), foreground=_C["text"])
        tb.tag_config("placeholder", foreground=_C["dim"])
        if not self._log_entries:
            tb.configure(state="normal")
            tb.insert(
                "1.0",
                "\n\n\n\n        📋   Adicione proposituras e clique em Gerar\n",
                "placeholder",
            )
            tb.configure(state="disabled")
            self._log_has_placeholder = True
        else:
            self._log_has_placeholder = False

        # AI Chat UI input controls
        self._chat_input_frame = ctk.CTkFrame(self._right, fg_color="transparent")
        self._chat_input_frame.grid(row=5, column=0, sticky="ew", padx=20, pady=(0, 10))
        self._chat_input_frame.grid_columnconfigure(0, weight=1)
        self._chat_input_frame.grid_columnconfigure(1, weight=0)

        self._chat_entry = ctk.CTkTextbox(
            self._chat_input_frame,
            font=ctk.CTkFont(size=13),
            height=54,
            wrap="word",
        )
        self._chat_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        # Placeholder implementation for CTkTextbox
        self._chat_placeholder = "Digite instruções complementares ou converse com a IA..."
        self._chat_has_placeholder = True
        self._chat_entry.insert("1.0", self._chat_placeholder)
        self._chat_entry.configure(text_color=_C["dim"])

        def _on_focus_in(event: Any) -> None:
            if self._chat_has_placeholder:
                self._chat_entry.delete("1.0", "end")
                self._chat_entry.configure(text_color=_C["text"])
                self._chat_has_placeholder = False

        def _on_focus_out(event: Any) -> None:
            content = self._chat_entry.get("1.0", "end-1c").strip()
            if not content:
                self._chat_entry.delete("1.0", "end")
                self._chat_entry.insert("1.0", self._chat_placeholder)
                self._chat_entry.configure(text_color=_C["dim"])
                self._chat_has_placeholder = True

        self._chat_entry.bind("<FocusIn>", _on_focus_in)
        self._chat_entry.bind("<FocusOut>", _on_focus_out)
        self._chat_entry.bind("<Control-Return>", lambda event: (self._send_chat_message(), "break")[1])

        self._chat_send_btn = ctk.CTkButton(
            self._chat_input_frame,
            text="Enviar",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=80,
            height=54,
            fg_color=_C["accent"], hover_color=_C["accent2"],
            text_color="#ffffff",
            command=self._send_chat_message,
        )
        self._chat_send_btn.grid(row=0, column=1)

        summary = ctk.CTkFrame(self._right, fg_color=_C["panel"], corner_radius=10)
        summary.grid(row=6, column=0, sticky="ew", padx=20, pady=(0, 18))
        summary.grid_columnconfigure(0, weight=1)

        self._summary_label = ctk.CTkLabel(
            summary, text="Nenhum processamento realizado ainda.",
            font=ctk.CTkFont(size=12), text_color=_C["dim"], anchor="w",
        )
        self._summary_label.grid(row=0, column=0, sticky="w", padx=16, pady=10)

        ctk.CTkButton(
            summary, text="📁  Ofícios Gerados",
            font=ctk.CTkFont(size=12), height=36, width=110, corner_radius=8,
            fg_color=_C["border"], hover_color=_C["accent2"], text_color=_C["text"],
            command=self._open_output_folder,
        ).grid(row=0, column=1, padx=(0, 6), pady=8)

        ctk.CTkButton(
            summary, text="✉  Envelopes Gerados",
            font=ctk.CTkFont(size=12), height=36, width=130, corner_radius=8,
            fg_color=_C["border"], hover_color=_C["accent2"], text_color=_C["text"],
            command=self._open_envelopes_folder,
        ).grid(row=0, column=2, padx=(0, 6), pady=8)

        ctk.CTkButton(
            summary, text="📊  Planilha Gerada",
            font=ctk.CTkFont(size=12), height=36, width=110, corner_radius=8,
            fg_color=_C["border"], hover_color=_C["accent2"], text_color=_C["text"],
            command=self._open_spreadsheet_folder,
        ).grid(row=0, column=3, padx=(0, 12), pady=8)

    def _build_footer(self) -> None:
        import webbrowser  # noqa: PLC0415

        footer = ctk.CTkFrame(self, fg_color=_C["card"], corner_radius=0, height=42)
        footer.grid(row=2, column=0, columnspan=2, sticky="ew")
        footer.grid_propagate(False)
        footer.grid_columnconfigure(0, weight=1)
        footer.grid_columnconfigure(1, weight=0)
        footer.grid_columnconfigure(2, weight=0)

        ctk.CTkLabel(
            footer,
            text=(
                f"Z7 OfficeLetters v{APP_VERSION}  •  Licenced under GPLv3  •  "
                "Powered by Gemini AI  •  Câmara Municipal de Santa Bárbara d'Oeste/SP"
            ),
            font=ctk.CTkFont(size=10), text_color=_C["dim"],
        ).grid(row=0, column=0, sticky="w", padx=16, pady=6)

        ctk.CTkButton(
            footer, text="👨‍💻  Repositório",
            font=ctk.CTkFont(size=10), width=110, height=26, corner_radius=6,
            fg_color="transparent", border_width=1, border_color=_C["border"],
            text_color=_C["dim"], hover_color=_C["bg"],
            command=lambda: webbrowser.open("https://github.com/chrmsantos/Z7_OfficeLetters"),
        ).grid(row=0, column=1, sticky="e", padx=(0, 8), pady=6)

        ctk.CTkLabel(
            footer, text=f"© {APP_AUTHOR}  •  Dharma, virtude e gratidão.",
            font=ctk.CTkFont(size=10), text_color=_C["dim"],
        ).grid(row=0, column=2, sticky="e", padx=16, pady=6)

    # =========================================================================
    # Widget helpers
    # =========================================================================
    def _section_title(self, parent: ctk.CTkFrame, row: int, text: str) -> None:
        ctk.CTkLabel(
            parent, text=text,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=_C["accent"], anchor="w",
        ).grid(row=row, column=0, sticky="w", padx=20, pady=(20, 4))

    def _divider(self, parent: ctk.CTkFrame, row: int) -> None:
        ctk.CTkFrame(parent, height=1, fg_color=_C["border"]).grid(
            row=row, column=0, sticky="ew", padx=20, pady=(0, 14))

    def _field_label(self, parent: ctk.CTkFrame, row: int, text: str) -> None:
        ctk.CTkLabel(
            parent, text=text,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=_C["text"], anchor="w",
        ).grid(row=row, column=0, sticky="w", padx=20, pady=(0, 4))

    # =========================================================================
    # AI status
    # =========================================================================
    def _update_ai_status(self) -> None:
        model = self._modelo_ia_var.get() or "gemini-3.5-flash"
        has_key = bool(self._apikey_var.get().strip()) or bool(self._stored_key)
        if has_key:
            text = f"🤖 {model}  •  ✔ Validado"
            color = _C["success"]
        else:
            text = f"🤖 {model}  •  ⚠ Chave não configurada"
            color = _C["warn"]
        self._ai_status_label.configure(text=text, text_color=color)

    def _post_startup_greeting(self) -> None:
        greeting = (
            "Olá! Sou o assistente de IA do Z7 OfficeLetters. 🤖\n\n"
            "Estou pronto para ajudar você a automatizar a extração de dados e geração de ofícios.\n\n"
            "Antes de iniciarmos, você tem alguma instrução complementar? Por exemplo:\n"
            "  1. Prefere algum tratamento especial para autoridades municipais?\n"
            "  2. Deseja que eu omita ou destaque alguma informação específica no corpo dos documentos?\n"
            "  3. Algum formato específico para datas ou nomes?\n\n"
            "Digite suas preferências no campo abaixo e envie, ou clique diretamente em 'GERAR OFÍCIOS' para usar as regras padrão!"
        )
        self._log(greeting, "success")

    def _send_chat_message(self) -> None:
        if getattr(self, "_chat_has_placeholder", False):
            return
        msg = self._chat_entry.get("1.0", "end-1c").strip()
        if not msg:
            return

        if self._processing:
            return

        # If we had run an execution, logs are shown. Let's redraw the chat first!
        if not self._showing_chat:
            self._redraw_chat()
            self._showing_chat = True

        self._log(f"\nVocê: {msg}", "accent")
        self._chat_entry.delete("1.0", "end")
        self._chat_entry.insert("1.0", self._chat_placeholder)
        self._chat_entry.configure(text_color=_C["dim"])
        self._chat_has_placeholder = True

        api_key = self._apikey_var.get().strip() or self._stored_key
        if not api_key:
            self._log(
                "\n🤖 Assistente: Para que eu possa responder e processar suas instruções complementares, "
                "por favor, informe e salve a chave da API Gemini no painel esquerdo ou em 'Avançado'.",
                "warn",
            )
            return

        self._chat_entry.configure(state="disabled")
        self._chat_send_btn.configure(state="disabled", text="Enviando...")

        def _chat_thread() -> None:
            try:
                from google import genai  # noqa: PLC0415
                from google.genai import types  # noqa: PLC0415

                cliente = genai.Client(api_key=api_key)
                model = self._modelo_ia_var.get() or "gemini-3.5-flash"

                system_instruction = (
                    "Você é o assistente de IA do Z7 OfficeLetters, um aplicativo de automação de ofícios legislativos. "
                    "Seu objetivo é ajudar o usuário a configurar e refinar as instruções personalizadas para a extração de dados das proposituras. "
                    "Responda a perguntas do usuário sobre a tarefa e confirme as regras ou preferências que ele deseja aplicar. "
                    "Seja conciso, profissional e prestativo. Lembre-se que você está em um chat antes da execução da tarefa."
                )

                contents = []
                for h in self._chat_history:
                    contents.append(
                        types.Content(
                            role=h["role"],
                            parts=[types.Part.from_text(text=h["content"])],
                        )
                    )
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=msg)],
                    )
                )

                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.7,
                )

                response = cliente.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )

                resp_text = (response.text or "").strip()
                self._chat_history.append({"role": "user", "content": msg})
                self._chat_history.append({"role": "model", "content": resp_text})

                if not self._custom_instructions:
                    self._custom_instructions = msg
                else:
                    self._custom_instructions += f"\n- {msg}"

                def _success() -> None:
                    self._log(f"\n🤖 Assistente: {resp_text}\n", "success")
                    self._chat_entry.configure(state="normal")
                    self._chat_send_btn.configure(state="normal", text="Enviar")
                    self._chat_entry.focus()

                self.after(0, _success)

            except Exception as exc:  # noqa: BLE001
                def _error(err_msg: str) -> None:
                    self._log(f"\n❌ Erro ao obter resposta da IA: {err_msg}", "error")
                    self._chat_entry.configure(state="normal")
                    self._chat_send_btn.configure(state="normal", text="Enviar")

                self.after(0, lambda: _error(str(exc)))

        threading.Thread(target=_chat_thread, daemon=True).start()

    def _redraw_chat(self) -> None:
        self._log_entries.clear()
        tb = self._log_box._textbox  # type: ignore[attr-defined]  # noqa: SLF001
        tb.configure(state="normal")
        tb.delete("1.0", "end")

        greeting = (
            "Olá! Sou o assistente de IA do Z7 OfficeLetters. 🤖\n\n"
            "Estou pronto para ajudar você a automatizar a extração de dados e geração de ofícios.\n\n"
            "Antes de iniciarmos, você tem alguma instrução complementar? Por exemplo:\n"
            "  1. Prefere algum tratamento especial para autoridades municipais?\n"
            "  2. Deseja que eu omita ou destaque alguma informação específica no corpo dos documentos?\n"
            "  3. Algum formato específico para datas ou nomes?\n\n"
            "Digite suas preferências no campo abaixo e envie, ou clique diretamente em 'GERAR OFÍCIOS' para usar as regras padrão!"
        )
        self._log(greeting, "success")

        for msg in self._chat_history:
            if msg["role"] == "user":
                self._log(f"\nVocê: {msg['content']}", "accent")
            else:
                 self._log(f"\n🤖 Assistente: {msg['content']}\n", "success")

    def _enable_chat_controls(self) -> None:
        self._chat_entry.configure(state="normal")
        self._chat_send_btn.configure(state="normal", text="Enviar")

    def _disable_chat_controls(self) -> None:
        self._chat_entry.configure(state="disabled")
        self._chat_send_btn.configure(state="disabled")

    # =========================================================================
    # Theme
    # =========================================================================
    def _toggle_theme(self) -> None:
        if self._processing:
            return

        saved_num = self._num_var.get()
        saved_sigla = self._sigla_var.get()
        saved_data = self._data_var.get()
        saved_modelo = self._modelo_ia_var.get()
        saved_key = self._apikey_var.get()
        saved_log_entries = list(self._log_entries)  # snapshot for tag-aware restore
        saved_summary_text = self._summary_label.cget("text")
        saved_summary_tag = getattr(self, "_summary_color_tag", "dim")
        saved_progress_val = self._progress.get()
        saved_progress_tag = getattr(self, "_progress_color_tag", "accent")
        saved_prog_label_text = self._prog_label.cget("text")
        saved_prog_label_tag = getattr(self, "_prog_label_color_tag", "dim")
        saved_prog_pct_text = self._prog_pct.cget("text")
        saved_prog_pct_tag = getattr(self, "_prog_pct_color_tag", "accent")
        try:
            tb = self._log_box._textbox  # type: ignore[attr-defined]  # noqa: SLF001
            _ = tb.get("1.0", "end-1c")  # ensure textbox is initialised
        except Exception:  # noqa: BLE001
            pass

        if self._theme == "dark":
            self._theme = "light"
            ctk.set_appearance_mode("light")
            _C.clear()
            _C.update(_LIGHT)
        else:
            self._theme = "dark"
            ctk.set_appearance_mode("dark")
            _C.clear()
            _C.update(_DARK)

        self.configure(fg_color=_C["bg"])

        for widget in self.grid_slaves():
            widget.destroy()

        self._build_ui()
        self._num_var.set(saved_num)
        self._sigla_var.set(saved_sigla)
        self._data_var.set(saved_data)
        self._modelo_ia_var.set(saved_modelo)
        self._apikey_var.set(saved_key)
        self._log_entries = saved_log_entries
        self._update_ai_status()

        self._prop_listbox.delete(0, tk.END)
        for p in self._prop_paths:
            self._prop_listbox.insert(tk.END, Path(p).name)

        # Restore log with colour tags
        if saved_log_entries:
            tb2 = self._log_box._textbox  # type: ignore[attr-defined]  # noqa: SLF001
            tb2.configure(state="normal")
            for entry_text, entry_tag in saved_log_entries:
                if entry_tag:
                    tb2.insert("end", entry_text + "\n", entry_tag)
                else:
                    tb2.insert("end", entry_text + "\n")
            tb2.see("end")
            tb2.configure(state="disabled")

        self._summary_color_tag = saved_summary_tag
        self._summary_label.configure(
            text=saved_summary_text,
            text_color=_C.get(saved_summary_tag, _C["dim"]),
        )
        self._progress.set(saved_progress_val)
        self._progress_color_tag = saved_progress_tag
        self._progress.configure(
            progress_color=_C.get(saved_progress_tag, _C["accent"])
        )
        self._prog_label_color_tag = saved_prog_label_tag
        self._prog_label.configure(
            text=saved_prog_label_text,
            text_color=_C.get(saved_prog_label_tag, _C["dim"]),
        )
        self._prog_pct_color_tag = saved_prog_pct_tag
        self._prog_pct.configure(
            text=saved_prog_pct_text,
            text_color=_C.get(saved_prog_pct_tag, _C["accent"]),
        )

    # =========================================================================
    # Interactions
    # =========================================================================
    def _has_api_key(self) -> bool:
        return bool(self._apikey_var.get().strip()) or bool(self._stored_key)

    def _decrement_num(self) -> None:
        try:
            self._num_var.set(str(max(1, int(self._num_var.get()) - 1)))
        except ValueError:
            self._num_var.set("1")

    def _increment_num(self) -> None:
        try:
            self._num_var.set(str(int(self._num_var.get()) + 1))
        except ValueError:
            self._num_var.set("1")

    def _on_redator_selected(self, choice: str) -> None:
        m = re.search(r'\(([^)]+)\)$', choice)
        if m:
            self._sigla_var.set(m.group(1))

    def _refresh_redator_combo(self) -> None:
        values = [f"{n} ({s})" for n, s in _config.MAPA_REDATORES.items()]
        self._sigla_combo.configure(values=values)

    def _browse_file(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Selecionar propositura(s)",
            initialdir=str(BASE_DIR),
            filetypes=[
                ("Documentos", "*.txt *.docx *.doc *.odt *.pdf"),
                ("Todos os arquivos", "*.*"),
            ],
        )
        if not paths:
            return
        existing = set(self._prop_paths)
        for p in paths:
            if p not in existing:
                self._prop_paths.append(p)
                self._prop_listbox.insert(tk.END, Path(p).name)
                existing.add(p)

    def _remove_propositura(self) -> None:
        sel = self._prop_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        self._prop_listbox.delete(idx)
        self._prop_paths.pop(idx)

    def _open_destinatarios_padrao(self) -> None:
        if getattr(sys, "frozen", False):
            _app_root = Path(sys.executable).parent
        else:
            _app_root = Path(__file__).parent.parent.parent.parent
        arquivo = _app_root / ENDERECAMENTO_PADRAO
        if not arquivo.exists():
            messagebox.showwarning(
                "Arquivo não encontrado",
                f"O arquivo de destinatários padrão não foi encontrado:\n{arquivo}",
            )
            return
        os.startfile(str(arquivo))

    def _open_output_folder(self) -> None:
        folder = Path(PASTA_SAIDA).resolve()
        folder.mkdir(exist_ok=True)
        os.startfile(str(folder))

    def _open_envelopes_folder(self) -> None:
        folder = Path(PASTA_ENVELOPES).resolve()
        folder.mkdir(exist_ok=True)
        os.startfile(str(folder))

    def _open_spreadsheet_folder(self) -> None:
        folder = Path(PASTA_PLANILHA).resolve()
        folder.mkdir(exist_ok=True)
        os.startfile(str(folder))

    def _open_pasta_templates(self) -> None:
        if getattr(sys, "frozen", False):
            pasta = Path(sys.executable).parent / "templates"
        else:
            pasta = Path(__file__).parent.parent.parent.parent / "templates"
        pasta.mkdir(parents=True, exist_ok=True)
        os.startfile(str(pasta))

    def _open_date_picker(self) -> None:
        from z7_officeletters.gui.dialogs.date_picker import show_date_picker  # noqa: PLC0415
        show_date_picker(self, self._data_var)

    def _open_avancado(self) -> None:
        from z7_officeletters.gui.dialogs.ai_api import show_ai_api_dialog  # noqa: PLC0415
        from z7_officeletters.gui.dialogs.config_editor import show_config_editor  # noqa: PLC0415
        from z7_officeletters.gui.dialogs.prompt_editor import show_prompt_editor  # noqa: PLC0415

        dlg = ctk.CTkToplevel(self)
        dlg.title("Avançado")
        dlg.geometry("460x262")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.configure(fg_color=_C["bg"])

        dlg.update_idletasks()
        px, py = self.winfo_x(), self.winfo_y()
        pw, ph = self.winfo_width(), self.winfo_height()
        dlg.geometry(f"460x262+{px + (pw - 460) // 2}+{py + (ph - 262) // 2}")

        _btn_kw: dict[str, Any] = dict(
            font=ctk.CTkFont(size=12), height=34, corner_radius=10,
            fg_color=_C["panel"], hover_color=_C["border"],
            text_color=_C["dim"], border_width=1, border_color=_C["border"],
        )

        ctk.CTkLabel(
            dlg, text="FERRAMENTAS",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=_C["accent"], anchor="w",
        ).pack(fill="x", padx=20, pady=(18, 2))
        ctk.CTkFrame(dlg, height=1, fg_color=_C["border"]).pack(fill="x", padx=20, pady=(0, 10))

        btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 20))
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)

        def _open_ai_api() -> None:
            def _on_ai_saved(key: str, modelo: str) -> None:
                self._stored_key = key
                self._apikey_var.set("")
                self._update_ai_status()

            show_ai_api_dialog(
                self,
                self._apikey_var,
                self._modelo_ia_var,
                lambda: self._stored_key,
                _on_ai_saved,
            )

        ctk.CTkButton(
            btn_frame, text="🔑  API de IA",
            command=_open_ai_api, **_btn_kw,
        ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 4))

        ctk.CTkButton(
            btn_frame, text="⚙  Configurações",
            command=lambda: show_config_editor(self, self._refresh_redator_combo),
            **_btn_kw,
        ).grid(row=1, column=0, sticky="ew", padx=(0, 3))

        ctk.CTkButton(
            btn_frame, text="🤖  Prompt IA",
            command=lambda: show_prompt_editor(self), **_btn_kw,
        ).grid(row=1, column=1, sticky="ew", padx=(3, 0))

        ctk.CTkButton(
            btn_frame, text="📁  Templates",
            command=self._open_pasta_templates, **_btn_kw,
        ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        ctk.CTkButton(
            btn_frame, text="📋  Destinatários Padrão",
            command=self._open_destinatarios_padrao, **_btn_kw,
        ).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        dlg.protocol("WM_DELETE_WINDOW", dlg.destroy)

    # =========================================================================
    # Log helpers (main thread only)
    # =========================================================================
    def _log(self, text: str, tag: str = "") -> None:
        self._log_entries.append((text, tag))
        tb = self._log_box._textbox  # type: ignore[attr-defined]  # noqa: SLF001
        tb.configure(state="normal")
        if getattr(self, "_log_has_placeholder", False):
            tb.delete("1.0", "end")
            self._log_has_placeholder = False
        if tag:
            tb.insert("end", text + "\n", tag)
        else:
            tb.insert("end", text + "\n")
        tb.see("end")
        tb.configure(state="disabled")

    def _clear_log(self) -> None:
        self._log_entries.clear()
        tb = self._log_box._textbox  # type: ignore[attr-defined]  # noqa: SLF001
        tb.configure(state="normal")
        tb.delete("1.0", "end")
        tb.insert(
            "1.0",
            "\n\n\n\n        📋   Adicione proposituras e clique em Gerar\n",
            "placeholder",
        )
        tb.configure(state="disabled")
        self._log_has_placeholder = True

    # =========================================================================
    # Processing
    # =========================================================================
    def _limpar_pastas_saida(self) -> None:
        for pasta in (Path(PASTA_SAIDA), Path(PASTA_PLANILHA), Path(PASTA_ENVELOPES)):
            if pasta.exists():
                for arq in pasta.iterdir():
                    if arq.is_file():
                        try:
                            send2trash.send2trash(str(arq))
                        except Exception:  # noqa: BLE001
                            pass

    def _confirmar_e_limpar_tudo(self) -> None:
        if self._processing:
            return

        if not messagebox.askyesno(
            "Confirmar Limpeza",
            "Deseja realmente limpar todos os dados da tela, arquivos anexos e pastas de saída?\n\n"
            "Esta ação excluirá todos os ofícios, envelopes e planilhas gerados, enviando-os para a Lixeira.",
            parent=self,
        ):
            return

        # 1. Clear screen inputs
        self._num_var.set("1")
        self._sigla_var.set("")
        self._sigla_combo.set("")
        self._data_var.set(datetime.now().strftime("%d/%m/%Y"))

        # 2. Clear attached files
        self._prop_paths = []
        self._prop_listbox.delete(0, tk.END)

        # 3. Clear logs
        self._clear_log()

        # 4. Reset summary
        self._summary_label.configure(
            text="Nenhum processamento realizado ainda.",
            text_color=_C["dim"],
        )
        self._summary_color_tag = "dim"

        # 5. Reset progress bar & labels
        self._progress.set(0)
        self._progress_color_tag = "accent"
        self._progress.configure(progress_color=_C["accent"])

        self._prog_label.configure(text="Aguardando início…", text_color=_C["dim"])
        self._prog_label_color_tag = "dim"

        self._prog_pct.configure(text="0 %", text_color=_C["accent"])
        self._prog_pct_color_tag = "accent"

        # 6. Clear output files
        self._limpar_pastas_saida()

        # 7. Persist empty state
        self._save_session_state()

        messagebox.showinfo("Limpeza Concluída", "Tudo limpo com sucesso!", parent=self)

    def _start_processing(self) -> None:
        if self._processing:
            return

        try:
            num = int(self._num_var.get())
            if num < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Erro de Validação", "Número do ofício inválido.")
            return

        sigla = self._sigla_var.get().strip().lower()
        if not sigla:
            messagebox.showerror("Erro de Validação", "Informe as iniciais do redator.")
            return

        data_str = self._data_var.get().strip()
        try:
            data_dt = datetime.strptime(data_str, "%d/%m/%Y")
        except ValueError:
            messagebox.showerror("Erro de Validação", "Data inválida. Use dd/mm/aaaa.")
            return

        arquivos = [a for a in self._prop_paths if Path(a).exists()]
        if not arquivos:
            messagebox.showerror(
                "Erro de Validação",
                "Adicione pelo menos um arquivo de propositura válido.",
            )
            return

        api_key = self._apikey_var.get().strip() or self._stored_key
        if not api_key:
            messagebox.showerror("Erro de Validação", "Informe a chave da API Gemini.")
            return

        data_extenso = f"{data_dt.day} de {MESES_PT[data_dt.month]} de {data_dt.year}"

        from z7_officeletters.gui.dialogs.confirmation import confirm_cleanup  # noqa: PLC0415

        pastas = [Path(PASTA_SAIDA), Path(PASTA_PLANILHA), Path(PASTA_ENVELOPES)]
        total_files = sum(
            sum(1 for f in p.iterdir() if f.is_file())
            for p in pastas if p.exists()
        )
        if not confirm_cleanup(self, total_files, PASTA_SAIDA, PASTA_PLANILHA):
            return
        self._limpar_pastas_saida()

        self._processing = True
        self._showing_chat = False
        self._disable_chat_controls()
        self._proc_start_time = time.time()
        self._cancel_event.clear()
        self._gen_btn.configure(state="disabled", text="⏳   Processando…")
        self._cancel_btn.grid()
        self._clear_log()
        self._progress.set(0)
        self._progress.configure(progress_color=_C["accent"])
        self._progress_color_tag = "accent"
        self._prog_label.configure(text="Iniciando…", text_color=_C["dim"])
        self._prog_label_color_tag = "dim"
        self._prog_pct.configure(text="0 %", text_color=_C["accent"])
        self._prog_pct_color_tag = "accent"
        self._summary_label.configure(text="Processando…", text_color=_C["dim"])
        self._summary_color_tag = "dim"

        inputs: dict[str, Any] = {
            "num_inicial":  num,
            "sigla":        sigla,
            "data_extenso": data_extenso,
            "data_iso":     data_dt.strftime("%Y-%m-%d"),
            "arquivos":     arquivos,
            "api_key":      api_key,
            "instrucoes_complementares": self._custom_instructions,
        }
        run_processing_worker(inputs, self._queue, self._cancel_event)

    def _request_cancel(self) -> None:
        self._cancel_event.set()
        self._cancel_btn.configure(state="disabled", text="Cancelando…")

    # =========================================================================
    # Queue polling
    # =========================================================================
    def _poll_queue(self) -> None:
        try:
            while True:
                self._handle_msg(self._queue.get_nowait())
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _handle_msg(self, msg: tuple[Any, ...]) -> None:
        kind = msg[0]

        if kind == "log":
            self._log(msg[1], msg[2])

        elif kind == "progress":
            current, total = msg[1], msg[2]
            pct = current / total if total else 0
            self._progress.set(pct)
            bar_color = _C["warn"] if pct < 0.4 else (_C["accent"] if pct < 0.8 else _C["success"])
            self._progress.configure(progress_color=bar_color)
            if current >= total > 0:
                self._prog_label.configure(
                    text="Gerando documentos…",
                    text_color=_C["dim"],
                )
            else:
                eta_str = ""
                if current > 0 and self._proc_start_time:
                    elapsed = time.time() - self._proc_start_time
                    remaining = (elapsed / current) * (total - current)
                    mins, secs = divmod(int(remaining), 60)
                    eta_str = (
                        f"  ·  ~{mins}m {secs:02d}s restantes"
                        if mins
                        else f"  ·  ~{secs}s restantes"
                    )
                self._prog_label.configure(
                    text=f"Analisando propositura {current + 1} de {total}…{eta_str}",
                    text_color=_C["dim"],
                )
            self._prog_pct.configure(text=f"{int(pct * 100)} %", text_color=bar_color)

        elif kind == "done":
            generated, errors, elapsed, total_tokens = msg[1], msg[2], msg[3], msg[4]
            self._processing = False
            self._enable_chat_controls()
            self._cancel_btn.grid_remove()
            self._cancel_btn.configure(state="normal", text="⏹   CANCELAR")
            mins, secs = divmod(int(elapsed), 60)
            tempo = f"{mins}m {secs}s" if mins else f"{secs}s"
            color = _C["success"] if not errors else _C["warn"]
            self._progress.set(1.0)
            self._progress.configure(progress_color=color)
            self._progress_color_tag = "success" if not errors else "warn"
            self._prog_label.configure(text=f"Concluído em {tempo}", text_color=color)
            self._prog_label_color_tag = "success" if not errors else "warn"
            self._prog_pct.configure(text="100 %", text_color=color)
            self._prog_pct_color_tag = "success" if not errors else "warn"
            self._gen_btn.configure(state="normal", text="⚡   GERAR OFÍCIOS")
            tag = "success" if not errors else "warn"
            tokens_str = f"  •  🔢 {total_tokens:,} tokens" if total_tokens > 0 else ""
            self._log(
                f"\n{'─' * 52}\n"
                f"  ✨  {generated} ofício(s) gerado(s)  •  {errors} erro(s)  •  ⏱ {tempo}{tokens_str}\n"
                f"{'─' * 52}",
                tag,
            )
            summary_tokens = f"   •   🔢 {total_tokens:,} tokens" if total_tokens > 0 else ""
            self._summary_label.configure(
                text=f"✔  {generated} ofício(s) gerado(s)   •   {errors} erro(s)   •   ⏱ {tempo}{summary_tokens}",
                text_color=color,
            )
            self._summary_color_tag = tag
            self._save_session_state()

        elif kind == "cancelled":
            done_so_far, total, label = msg[1], msg[2], msg[3]
            self._processing = False
            self._enable_chat_controls()
            self._cancel_btn.grid_remove()
            self._cancel_btn.configure(state="normal", text="⏹   CANCELAR")
            self._gen_btn.configure(state="normal", text="⚡   GERAR OFÍCIOS")
            self._progress.configure(progress_color=_C["warn"])
            self._progress_color_tag = "warn"
            self._prog_label.configure(
                text=f"Cancelado após {done_so_far} de {total} {label}.",
                text_color=_C["warn"],
            )
            self._prog_label_color_tag = "warn"
            self._log(f"\n⏹  Processamento cancelado após {done_so_far}/{total} {label}.", "warn")
            self._save_session_state()

        elif kind == "error":
            self._processing = False
            self._enable_chat_controls()
            self._cancel_btn.grid_remove()
            self._cancel_btn.configure(state="normal", text="⏹   CANCELAR")
            self._gen_btn.configure(state="normal", text="⚡   GERAR OFÍCIOS")
            self._log(f"\n❌  Erro fatal: {msg[1]}", "error")
            self._prog_label.configure(
                text="Erro fatal — verifique o log",
                text_color=_C["error"],
            )
            self._prog_label_color_tag = "error"
            messagebox.showerror("Erro Fatal", msg[1])

    # =========================================================================
    # Auto-Update System
    # =========================================================================
    def _check_for_updates_user(self) -> None:
        if self._processing:
            return

        self._update_btn.configure(state="disabled", text="⏳ Checando...")

        def _bg_check() -> None:
            try:
                tag_name, download_url = obter_ultima_versao()
                versao_limpa = tag_name.lstrip("vV")

                def _handle_result() -> None:
                    self._update_btn.configure(state="normal", text="🔄  Atualizar")
                    if comparar_versoes(versao_limpa, APP_VERSION):
                        if messagebox.askyesno(
                            "Atualização Disponível",
                            f"Uma nova versão estável ({tag_name}) está disponível!\n\n"
                            f"Sua versão atual: {APP_VERSION}\n"
                            f"Nova versão: {versao_limpa}\n\n"
                            "Deseja baixar e instalar a atualização agora?",
                            parent=self,
                        ):
                            self._mostrar_janela_download(download_url, tag_name)
                    else:
                        messagebox.showinfo(
                            "Sem Atualizações",
                            f"Você já está utilizando a versão mais recente ({APP_VERSION}).",
                            parent=self,
                        )

                self.after(0, _handle_result)
            except Exception as exc:
                def _handle_err() -> None:
                    self._update_btn.configure(state="normal", text="🔄  Atualizar")
                    messagebox.showerror(
                        "Erro de Atualização",
                        f"Não foi possível verificar atualizações:\n{exc}",
                        parent=self,
                    )
                self.after(0, _handle_err)

        threading.Thread(target=_bg_check, daemon=True).start()

    def _mostrar_janela_download(self, download_url: str, versao: str) -> None:
        if not getattr(sys, "frozen", False):
            messagebox.showinfo(
                "Modo de Desenvolvimento",
                f"Atualização {versao} está disponível, mas o processo de auto-atualização "
                "só se aplica à versão compilada (.exe).\n\n"
                "Para testar, baixe o binário ou empacote o projeto usando o PyInstaller.",
                parent=self,
            )
            return

        dlg = ctk.CTkToplevel(self)
        dlg.title("Baixando Atualização")
        dlg.geometry("400x180")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.configure(fg_color=_C["bg"])

        dlg.update_idletasks()
        px, py = self.winfo_x(), self.winfo_y()
        pw, ph = self.winfo_width(), self.winfo_height()
        dlg.geometry(f"400x180+{px + (pw - 400) // 2}+{py + (ph - 180) // 2}")

        ctk.CTkLabel(
            dlg,
            text=f"Baixando versão {versao}...",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=_C["text"],
            anchor="w",
        ).pack(fill="x", padx=24, pady=(20, 10))

        prog_bar = ctk.CTkProgressBar(
            dlg,
            height=16,
            corner_radius=8,
            progress_color=_C["accent"],
            fg_color=_C["panel"],
        )
        prog_bar.pack(fill="x", padx=24, pady=5)
        prog_bar.set(0.0)

        prog_lbl = ctk.CTkLabel(
            dlg,
            text="Conectando...",
            font=ctk.CTkFont(size=11),
            text_color=_C["dim"],
            anchor="w",
        )
        prog_lbl.pack(fill="x", padx=24, pady=(2, 10))

        download_cancelled = threading.Event()

        def _cancel() -> None:
            download_cancelled.set()
            dlg.destroy()

        ctk.CTkButton(
            dlg,
            text="Cancelar",
            font=ctk.CTkFont(size=12),
            height=34,
            width=100,
            corner_radius=8,
            fg_color=_C["panel"],
            hover_color=_C["error"],
            text_color=_C["text"],
            command=_cancel,
        ).pack(pady=(5, 10))

        def _bg_download() -> None:
            temp_path = sys.executable + ".tmp"
            try:
                import urllib.request  # noqa: PLC0415

                req = urllib.request.Request(
                    download_url,
                    headers={"User-Agent": "Z7_OfficeLetters-Updater"},
                )
                with urllib.request.urlopen(req, timeout=20) as response:
                    total_size = int(response.info().get("Content-Length", 0))
                    bytes_downloaded = 0

                    with open(temp_path, "wb") as f:
                        while not download_cancelled.is_set():
                            chunk = response.read(65536)  # 64 KB
                            if not chunk:
                                break
                            f.write(chunk)
                            bytes_downloaded += len(chunk)

                            if total_size:
                                pct = bytes_downloaded / total_size
                                def _update(p: float, bd: int, ts: int) -> None:
                                    if dlg.winfo_exists():
                                        prog_bar.set(p)
                                        prog_lbl.configure(
                                            text=f"Baixado {bd / (1024 * 1024):.1f} MB de {ts / (1024 * 1024):.1f} MB ({int(p * 100)}%)"
                                        )
                                self.after(0, _update, pct, bytes_downloaded, total_size)

                    if download_cancelled.is_set():
                        try:
                            Path(temp_path).unlink()
                        except Exception:
                            pass
                        return

                if Path(temp_path).stat().st_size == 0:
                    raise RuntimeError("O arquivo baixado está vazio.")

                old_exe = sys.executable + ".old"
                try:
                    if Path(old_exe).exists():
                        Path(old_exe).unlink()
                except Exception:
                    pass

                os.rename(sys.executable, old_exe)
                os.rename(temp_path, sys.executable)

                def _success() -> None:
                    if dlg.winfo_exists():
                        dlg.destroy()
                    messagebox.showinfo(
                        "Atualização Concluída",
                        "A atualização foi baixada com sucesso!\n\n"
                        "O aplicativo será reiniciado automaticamente na nova versão.",
                        parent=self,
                    )
                    import subprocess  # noqa: PLC0415
                    subprocess.Popen([sys.executable])
                    self._on_close()

                self.after(0, _success)

            except Exception as exc:
                try:
                    if Path(temp_path).exists():
                        Path(temp_path).unlink()
                except Exception:
                    pass

                def _error(err: str) -> None:
                    if dlg.winfo_exists():
                        dlg.destroy()
                    messagebox.showerror(
                        "Erro no Download",
                        f"Ocorreu um erro ao baixar a atualização:\n{err}",
                        parent=self,
                    )
                self.after(0, _error, str(exc))

        threading.Thread(target=_bg_download, daemon=True).start()

    # =========================================================================
    # Window close
    # =========================================================================
    def _on_close(self) -> None:
        self._save_session_state()
        self.destroy()
