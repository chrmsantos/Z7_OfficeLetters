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
import sys
import threading
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
    PASTA_LOGS,
    PASTA_PLANILHA,
    PASTA_PROPOSITURAS,
    PASTA_SAIDA,
    BASE_DIR,
)
from z7_officeletters.core import config as _config
from z7_officeletters.core.documents import criar_modelo_planilha
from z7_officeletters.core.files import listar_proposituras
from z7_officeletters.core.api_key import carregar_api_key, migrar_chave_do_registro, carregar_modelo_ia, salvar_modelo_ia
from z7_officeletters.gui.constants import _C, _DARK, _LIGHT
from z7_officeletters.gui.workers.processor import run_processing_worker

__all__ = ["AutoOficiosApp"]


class AutoOficiosApp(ctk.CTk):
    """Root application window."""

    def __init__(self) -> None:
        super().__init__()
        self._theme: str = "dark"
        self._load_saved_theme()

        self.title(f"Z7 OfficeLetters v{APP_VERSION} — Gerador Legislativo")
        self.geometry("1140x680")
        self.minsize(920, 580)
        self.configure(fg_color=_C["bg"])
        self._maximize_on_startup()
        self.after(0, self._maximize_on_startup)

        _icon = Path(__file__).parent.parent.parent.parent / "icon.ico"
        if _icon.exists():
            self.iconbitmap(str(_icon))

        self._queue: queue.Queue[tuple[Any, ...]] = queue.Queue()
        self._processing = False
        self._cancel_event = threading.Event()
        self._prop_paths: list[str] = []
        self._stored_key: str = ""

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._run_init_sync()
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
        for p in (PASTA_LOGS, PASTA_PROPOSITURAS, PASTA_SAIDA, PASTA_PLANILHA):
            Path(p).mkdir(parents=True, exist_ok=True)
        try:
            if getattr(sys, "frozen", False):
                modelo = Path(sys.executable).parent / MODELO_PLANILHA
            else:
                modelo = Path(__file__).parent.parent.parent.parent / MODELO_PLANILHA
            if not modelo.exists():
                criar_modelo_planilha(modelo)
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

        prop_files: list[Path] = []
        try:
            prop_files = listar_proposituras()
        except Exception:  # noqa: BLE001
            pass

        session_state: dict[str, Any] = {}
        try:
            session_path = Path(BASE_DIR) / "last_session.json"
            if session_path.exists():
                session_state = json.loads(session_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass

        self._on_init_ready(loaded_key, loaded_model, prop_files, session_state)

    def _on_init_ready(
        self,
        loaded_key: str,
        loaded_model: str,
        prop_files: list[Path],
        session_state: dict[str, Any],
    ) -> None:
        self._stored_key = loaded_key
        if loaded_model:
            self._modelo_ia_var.set(loaded_model)
            import z7_officeletters.core.ai as _ai  # noqa: PLC0415
            _ai.MODELO_IA = loaded_model

        if "numero_oficio" in session_state:
            self._num_var.set(session_state["numero_oficio"])
        if "redator" in session_state:
            self._sigla_var.set(session_state["redator"])
        if "data" in session_state:
            self._data_var.set(session_state["data"])

        saved_props = [p for p in session_state.get("proposituras", []) if Path(p).exists()]
        if saved_props:
            self._prop_paths = saved_props
            self._prop_listbox.delete(0, tk.END)
            for p in saved_props:
                self._prop_listbox.insert(tk.END, Path(p).name)
        else:
            self._prop_paths = [str(p) for p in prop_files]
            self._prop_listbox.delete(0, tk.END)
            for p in prop_files:
                self._prop_listbox.insert(tk.END, p.name)

    def _load_saved_theme(self) -> None:
        try:
            session_path = Path(BASE_DIR) / "last_session.json"
            if session_path.exists():
                saved = json.loads(session_path.read_text(encoding="utf-8"))
                saved_theme = saved.get("theme", "dark")
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
        hdr = ctk.CTkFrame(self, fg_color=_C["card"], corner_radius=0, height=76)
        hdr.grid(row=0, column=0, columnspan=2, sticky="ew")
        hdr.grid_propagate(False)
        hdr.grid_columnconfigure(0, weight=1)
        hdr.grid_columnconfigure(1, weight=0)

        title_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="w", padx=24, pady=(18, 0))

        ctk.CTkLabel(
            title_frame, text="Z7 OFFICELETTERS",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=_C["text"],
        ).pack(side="left")

        ctk.CTkLabel(
            title_frame,
            text=f"   Gerador de Ofícios Legislativos  •  v{APP_VERSION}",
            font=ctk.CTkFont(size=13),
            text_color=_C["dim"],
        ).pack(side="left", pady=4)

        _theme_icon = "☀" if self._theme == "dark" else "🌙"
        _theme_tip  = "Tema Claro" if self._theme == "dark" else "Tema Escuro"
        ctk.CTkButton(
            hdr,
            text=f"{_theme_icon}  {_theme_tip}",
            font=ctk.CTkFont(size=12),
            width=120, height=32, corner_radius=8,
            fg_color=_C["panel"], hover_color=_C["border"],
            text_color=_C["dim"],
            border_width=1, border_color=_C["border"],
            command=self._toggle_theme,
        ).grid(row=0, column=1, sticky="e", padx=20, pady=(22, 0))

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
            command=lambda: self._num_var.set(str(max(1, int(self._num_var.get() or 1) - 1))),
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
            command=lambda: self._num_var.set(str(int(self._num_var.get() or 0) + 1)),
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
            height=54, corner_radius=12,
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

        _btn_kw: dict[str, Any] = dict(
            font=ctk.CTkFont(size=12), height=34, corner_radius=10,
            fg_color=_C["panel"], hover_color=_C["border"],
            text_color=_C["dim"], border_width=1, border_color=_C["border"],
        )
        ctk.CTkButton(
            modelos_frame, text="🔧  Avançado",
            command=self._open_avancado, **_btn_kw,
        ).grid(row=0, column=0, sticky="ew")

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
        tb.tag_config("bold",    font=("Consolas", 12, "bold"), foreground=_C["text"])

        summary = ctk.CTkFrame(self._right, fg_color=_C["panel"], corner_radius=10)
        summary.grid(row=5, column=0, sticky="ew", padx=20, pady=(0, 18))
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
            summary, text="📊  Planilha Gerada",
            font=ctk.CTkFont(size=12), height=36, width=110, corner_radius=8,
            fg_color=_C["border"], hover_color=_C["accent2"], text_color=_C["text"],
            command=self._open_spreadsheet_folder,
        ).grid(row=0, column=2, padx=(0, 12), pady=8)

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
            footer, text=f"© {APP_AUTHOR}",
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
    # Theme
    # =========================================================================
    def _toggle_theme(self) -> None:
        if self._processing:
            return

        saved_num = self._num_var.get()
        saved_sigla = self._sigla_var.get()
        saved_data = self._data_var.get()
        try:
            tb = self._log_box._textbox  # type: ignore[attr-defined]
            log_text: str = tb.get("1.0", "end-1c")
        except Exception:  # noqa: BLE001
            log_text = ""

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

        self._prop_listbox.delete(0, tk.END)
        for p in self._prop_paths:
            self._prop_listbox.insert(tk.END, Path(p).name)

        if log_text:
            tb2 = self._log_box._textbox  # type: ignore[attr-defined]
            tb2.configure(state="normal")
            tb2.insert("1.0", log_text)
            tb2.see("end")
            tb2.configure(state="disabled")

    # =========================================================================
    # Interactions
    # =========================================================================
    def _has_api_key(self) -> bool:
        return bool(self._apikey_var.get().strip()) or bool(self._stored_key)

    def _on_redator_selected(self, choice: str) -> None:
        m = re.search(r'\(([^)]+)\)$', choice)
        if m:
            self._sigla_var.set(m.group(1))

    def _refresh_redator_combo(self) -> None:
        values = [f"{n} ({s})" for n, s in _config.MAPA_REDATORES.items()]
        self._sigla_combo.configure(values=values)

    def _refresh_proposituras(self) -> None:
        files = listar_proposituras()
        self._prop_paths = [str(p) for p in files]
        self._prop_listbox.delete(0, tk.END)
        for p in files:
            self._prop_listbox.insert(tk.END, p.name)

    def _browse_file(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Selecionar propositura(s)",
            initialdir=str(Path(PASTA_PROPOSITURAS)),
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

    def _open_output_folder(self) -> None:
        folder = Path(PASTA_SAIDA).resolve()
        folder.mkdir(exist_ok=True)
        os.startfile(str(folder))

    def _open_spreadsheet_folder(self) -> None:
        folder = Path(PASTA_PLANILHA).resolve()
        folder.mkdir(exist_ok=True)
        os.startfile(str(folder))

    def _open_modelo_oficio(self) -> None:
        if getattr(sys, "frozen", False):
            modelo = Path(sys.executable).parent / MODELO_OFICIO
            if not modelo.exists():
                modelo = Path(getattr(sys, "_MEIPASS", "")) / MODELO_OFICIO
        else:
            modelo = Path(__file__).parent.parent.parent.parent / MODELO_OFICIO
        if not modelo.exists():
            messagebox.showwarning(
                "Modelo não encontrado",
                f"O arquivo não foi encontrado:\n{modelo}\n\n"
                "Crie o arquivo modelo_oficio.docx na pasta templates do aplicativo e tente novamente.",
            )
            return
        os.startfile(str(modelo))

    def _open_modelo_planilha(self) -> None:
        if getattr(sys, "frozen", False):
            modelo = Path(sys.executable).parent / MODELO_PLANILHA
        else:
            modelo = Path(__file__).parent.parent.parent.parent / MODELO_PLANILHA
        if not modelo.exists():
            try:
                criar_modelo_planilha(modelo)
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Erro", f"Não foi possível criar o modelo:\n{exc}")
                return
        os.startfile(str(modelo))

    def _open_date_picker(self) -> None:
        from z7_officeletters.gui.dialogs.date_picker import show_date_picker  # noqa: PLC0415
        show_date_picker(self, self._data_var)

    def _open_avancado(self) -> None:
        from z7_officeletters.gui.dialogs.api_key import show_api_key_dialog  # noqa: PLC0415
        from z7_officeletters.gui.dialogs.config_editor import show_config_editor  # noqa: PLC0415
        from z7_officeletters.gui.dialogs.prompt_editor import show_prompt_editor  # noqa: PLC0415

        dlg = ctk.CTkToplevel(self)
        dlg.title("Avançado")
        dlg.geometry("460x390")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.configure(fg_color=_C["bg"])

        dlg.update_idletasks()
        px, py = self.winfo_x(), self.winfo_y()
        pw, ph = self.winfo_width(), self.winfo_height()
        dlg.geometry(f"460x390+{px + (pw - 460) // 2}+{py + (ph - 390) // 2}")

        ctk.CTkLabel(
            dlg, text="CHAVE GEMINI API",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=_C["accent"], anchor="w",
        ).pack(fill="x", padx=20, pady=(18, 2))
        ctk.CTkFrame(dlg, height=1, fg_color=_C["border"]).pack(fill="x", padx=20, pady=(0, 10))

        _dlg_status = ctk.CTkLabel(
            dlg,
            text="✔  Chave configurada" if self._has_api_key() else "⚠  Chave não configurada",
            font=ctk.CTkFont(size=12),
            text_color=_C["success"] if self._has_api_key() else _C["warn"],
            anchor="w",
        )
        _dlg_status.pack(fill="x", padx=22, pady=(4, 0))

        def _update_dlg_status(*_: object) -> None:
            hk = self._has_api_key()
            try:
                _dlg_status.configure(
                    text="✔  Chave configurada" if hk else "⚠  Chave não configurada",
                    text_color=_C["success"] if hk else _C["warn"],
                )
            except Exception:  # noqa: BLE001
                pass

        trace_id = self._apikey_var.trace_add("write", _update_dlg_status)

        ctk.CTkButton(
            dlg, text="🔑  Chave de API",
            font=ctk.CTkFont(size=12), height=36, corner_radius=10,
            fg_color=_C["panel"], hover_color=_C["border"],
            text_color=_C["text"], border_width=1, border_color=_C["border"],
            command=lambda: show_api_key_dialog(
                self, self._apikey_var, self._has_api_key,
                lambda k: setattr(self, "_stored_key", k),
            ),
        ).pack(fill="x", padx=20, pady=(10, 0))

        ctk.CTkLabel(
            dlg, text="MODELO IA",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=_C["accent"], anchor="w",
        ).pack(fill="x", padx=20, pady=(14, 2))
        ctk.CTkFrame(dlg, height=1, fg_color=_C["border"]).pack(fill="x", padx=20, pady=(0, 6))

        model_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        model_frame.pack(fill="x", padx=20, pady=(0, 0))
        model_frame.grid_columnconfigure(0, weight=1)

        model_entry = ctk.CTkEntry(
            model_frame, textvariable=self._modelo_ia_var,
            placeholder_text="Ex: gemini-2.0-flash",
            font=ctk.CTkFont(size=13), height=36,
        )
        model_entry.grid(row=0, column=0, sticky="ew")

        def _save_model() -> None:
            import z7_officeletters.core.ai as _ai  # noqa: PLC0415
            modelo = self._modelo_ia_var.get().strip()
            if not modelo:
                from tkinter import messagebox as _mb  # noqa: PLC0415
                _mb.showwarning("Modelo IA", "Informe um nome de modelo.", parent=dlg)
                return
            try:
                salvar_modelo_ia(modelo)
                _ai.MODELO_IA = modelo
            except Exception as exc:  # noqa: BLE001
                from tkinter import messagebox as _mb  # noqa: PLC0415
                _mb.showerror("Modelo IA", f"Não foi possível salvar.\n\n{exc}", parent=dlg)

        ctk.CTkButton(
            model_frame, text="💾", width=36, height=36,
            font=ctk.CTkFont(size=15),
            fg_color=_C["panel"], hover_color=_C["border"],
            text_color=_C["text"],
            command=_save_model,
        ).grid(row=0, column=1, padx=(6, 0))

        ctk.CTkFrame(dlg, height=1, fg_color=_C["border"]).pack(fill="x", padx=20, pady=(12, 10))

        _btn_kw: dict[str, Any] = dict(
            font=ctk.CTkFont(size=12), height=34, corner_radius=10,
            fg_color=_C["panel"], hover_color=_C["border"],
            text_color=_C["dim"], border_width=1, border_color=_C["border"],
        )
        btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 20))
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            btn_frame, text="⚙  Configurações",
            command=lambda: show_config_editor(self, self._refresh_redator_combo),
            **_btn_kw,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 3))

        ctk.CTkButton(
            btn_frame, text="🤖  Prompt IA",
            command=lambda: show_prompt_editor(self), **_btn_kw,
        ).grid(row=0, column=1, sticky="ew", padx=(3, 0))

        ctk.CTkButton(
            btn_frame, text="📝  Template de Ofício",
            command=self._open_modelo_oficio, **_btn_kw,
        ).grid(row=1, column=0, sticky="ew", padx=(0, 3), pady=(4, 0))

        ctk.CTkButton(
            btn_frame, text="📈  Template de Planilha",
            command=self._open_modelo_planilha, **_btn_kw,
        ).grid(row=1, column=1, sticky="ew", padx=(3, 0), pady=(4, 0))

        def _on_close() -> None:
            self._apikey_var.trace_remove("write", trace_id)
            dlg.destroy()

        dlg.protocol("WM_DELETE_WINDOW", _on_close)

    # =========================================================================
    # Log helpers (main thread only)
    # =========================================================================
    def _log(self, text: str, tag: str = "") -> None:
        tb = self._log_box._textbox  # type: ignore[attr-defined]
        tb.configure(state="normal")
        if tag:
            tb.insert("end", text + "\n", tag)
        else:
            tb.insert("end", text + "\n")
        tb.see("end")
        tb.configure(state="disabled")

    def _clear_log(self) -> None:
        tb = self._log_box._textbox  # type: ignore[attr-defined]
        tb.configure(state="normal")
        tb.delete("1.0", "end")
        tb.configure(state="disabled")

    # =========================================================================
    # Processing
    # =========================================================================
    def _limpar_pastas_saida(self) -> None:
        for pasta in (Path(PASTA_SAIDA), Path(PASTA_PLANILHA)):
            if pasta.exists():
                for arq in pasta.iterdir():
                    if arq.is_file():
                        try:
                            send2trash.send2trash(str(arq))
                        except Exception:  # noqa: BLE001
                            pass

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
            messagebox.showerror("Erro de Validação", "Data inválida. Use dd-mm-aaaa.")
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

        pastas = [Path(PASTA_SAIDA), Path(PASTA_PLANILHA)]
        total_files = sum(
            sum(1 for f in p.iterdir() if f.is_file())
            for p in pastas if p.exists()
        )
        if not confirm_cleanup(self, total_files, PASTA_SAIDA, PASTA_PLANILHA):
            return
        self._limpar_pastas_saida()

        self._processing = True
        self._cancel_event.clear()
        self._gen_btn.configure(state="disabled", text="⏳   Processando…")
        self._cancel_btn.grid()
        self._clear_log()
        self._progress.set(0)
        self._progress.configure(progress_color=_C["accent"])
        self._prog_label.configure(text="Iniciando…", text_color=_C["dim"])
        self._prog_pct.configure(text="0 %", text_color=_C["accent"])
        self._summary_label.configure(text="Processando…", text_color=_C["dim"])

        inputs: dict[str, Any] = {
            "num_inicial":  num,
            "sigla":        sigla,
            "data_extenso": data_extenso,
            "data_iso":     data_dt.strftime("%Y-%m-%d"),
            "arquivos":     arquivos,
            "api_key":      api_key,
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
            self._prog_label.configure(
                text=f"Processando moção {current} de {total}…",
                text_color=_C["dim"],
            )
            self._prog_pct.configure(text=f"{int(pct * 100)} %")

        elif kind == "done":
            generated, errors, elapsed = msg[1], msg[2], msg[3]
            self._processing = False
            self._cancel_btn.grid_remove()
            self._cancel_btn.configure(state="normal", text="⏹   CANCELAR")
            mins, secs = divmod(int(elapsed), 60)
            tempo = f"{mins}m {secs}s" if mins else f"{secs}s"
            color = _C["success"] if not errors else _C["warn"]
            self._progress.set(1.0)
            self._progress.configure(progress_color=color)
            self._prog_label.configure(text=f"Concluído em {tempo}", text_color=color)
            self._prog_pct.configure(text="100 %", text_color=color)
            self._gen_btn.configure(state="normal", text="⚡   GERAR OFÍCIOS")
            tag = "success" if not errors else "warn"
            self._log(
                f"\n{'─' * 52}\n"
                f"  ✨  {generated} ofício(s) gerado(s)  •  {errors} erro(s)  •  ⏱ {tempo}\n"
                f"{'─' * 52}",
                tag,
            )
            self._summary_label.configure(
                text=f"✔  {generated} ofício(s) gerado(s)   •   {errors} erro(s)   •   ⏱ {tempo}",
                text_color=color,
            )
            self._save_session_state()

        elif kind == "cancelled":
            done_so_far, total = msg[1], msg[2]
            self._processing = False
            self._cancel_btn.grid_remove()
            self._cancel_btn.configure(state="normal", text="⏹   CANCELAR")
            self._gen_btn.configure(state="normal", text="⚡   GERAR OFÍCIOS")
            self._progress.configure(progress_color=_C["warn"])
            self._prog_label.configure(
                text=f"Cancelado após {done_so_far} de {total} moções.",
                text_color=_C["warn"],
            )
            self._log(f"\n⏹  Processamento cancelado após {done_so_far}/{total} moções.", "warn")
            self._save_session_state()

        elif kind == "error":
            self._processing = False
            self._cancel_btn.grid_remove()
            self._cancel_btn.configure(state="normal", text="⏹   CANCELAR")
            self._gen_btn.configure(state="normal", text="⚡   GERAR OFÍCIOS")
            self._log(f"\n❌  Erro fatal: {msg[1]}", "error")
            self._prog_label.configure(
                text="Erro fatal — verifique o log",
                text_color=_C["error"],
            )
            messagebox.showerror("Erro Fatal", msg[1])

    # =========================================================================
    # Window close
    # =========================================================================
    def _on_close(self) -> None:
        self._save_session_state()
        self.destroy()
