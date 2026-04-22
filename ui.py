"""
ui.py — Interface gráfica para o ZWave OfficeLetters.
Execute:  python ui.py
Requer:   customtkinter  (pip install customtkinter)
"""
from __future__ import annotations

import os
import queue
import re
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any

import customtkinter as ctk
import auto_oficios as _ao

# ─── Aparência padrão ─────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ─── Paleta de cores ──────────────────────────────────────────────────────────
_DARK: dict[str, str] = {
    "bg":      "#0f111a",
    "card":    "#1a1d2e",
    "panel":   "#22253a",
    "border":  "#2e3150",
    "accent":  "#4f8ef7",
    "accent2": "#3a7aee",
    "success": "#57c77c",
    "error":   "#f07178",
    "warn":    "#ffb454",
    "text":    "#cdd6f4",
    "dim":     "#6c7086",
}
_C = _DARK

# Pre-compiled regex — avoids recompiling on every processed batch
_RE_MOCAO_SPLIT = re.compile(r'(?=MOCÃO Nº)')


# =============================================================================
# Main Application
# =============================================================================
class AutoOficiosApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"ZWave OfficeLetters v{_ao.APP_VERSION} — Gerador Legislativo")
        self.geometry("1140x720")
        self.minsize(920, 620)
        self.configure(fg_color=_C["bg"])

        # Ícone da janela (quando executado como .py; o exe usa o ícone do spec)
        _icon = Path(__file__).parent / "icon.ico"
        if _icon.exists():
            self.iconbitmap(str(_icon))

        self._queue: queue.Queue[tuple[Any, ...]] = queue.Queue()
        self._processing = False
        self._cancel_event = threading.Event()
        self._prop_files: dict[str, str] = {}

        self._build_ui()
        self.after(0, self._refresh_proposituras)   # defer disk scan; window renders first
        self.after(10, self._load_api_key_async)    # defer registry/keyring init; window renders first
        self._poll_queue()

    # =========================================================================
    # UI Construction
    # =========================================================================
    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=0, minsize=370)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=0)   # header
        self.grid_rowconfigure(1, weight=1)   # main
        self.grid_rowconfigure(2, weight=0)   # footer

        self._build_header()
        self._build_left_panel()
        self._build_right_panel()
        self._build_footer()

    # ── Header ────────────────────────────────────────────────────────────────
    def _build_header(self) -> None:
        hdr = ctk.CTkFrame(self, fg_color=_C["card"], corner_radius=0, height=68)
        hdr.grid(row=0, column=0, columnspan=2, sticky="ew")
        hdr.grid_propagate(False)
        hdr.grid_columnconfigure(0, weight=1)
        hdr.grid_columnconfigure(1, weight=0)

        title_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="w", padx=24, pady=(10, 0))

        ctk.CTkLabel(
            title_frame,
            text="🏙  ZWAVE OFFICELETTERS",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=_C["text"],
        ).pack(side="left")

        ctk.CTkLabel(
            title_frame,
            text=f"   Gerador de Ofícios Legislativos  •  v{_ao.APP_VERSION}",
            font=ctk.CTkFont(size=13),
            text_color=_C["dim"],
        ).pack(side="left", pady=4)


    # ── Left Panel (inputs) ───────────────────────────────────────────────────
    def _build_left_panel(self) -> None:
        self._left = ctk.CTkFrame(self, fg_color=_C["card"], corner_radius=16)
        self._left.grid(row=1, column=0, sticky="nsew", padx=(14, 7), pady=12)
        self._left.grid_columnconfigure(0, weight=1)
        self._left.grid_rowconfigure(14, weight=1)  # spacer

        self._section_title(self._left, 0, "CONFIGURAÇÃO")
        self._divider(self._left, 1)

        # ── Número do ofício ──────────────────────────────────────────────────
        self._field_label(self._left, 2, "Número do Ofício Inicial")

        num_frame = ctk.CTkFrame(self._left, fg_color="transparent")
        num_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 14))
        num_frame.grid_columnconfigure(0, weight=1)

        self._num_var = ctk.StringVar(value="1")
        self._num_entry = ctk.CTkEntry(
            num_frame, textvariable=self._num_var,
            placeholder_text="Ex: 300",
            font=ctk.CTkFont(size=15), height=42,
        )
        self._num_entry.grid(row=0, column=0, sticky="ew")

        ctk.CTkButton(
            num_frame, text="−", width=38, height=42,
            font=ctk.CTkFont(size=17, weight="bold"),
            fg_color=_C["panel"], hover_color=_C["border"],
            text_color=_C["text"],
            command=lambda: self._step_num(-1),
        ).grid(row=0, column=1, padx=(6, 0))

        ctk.CTkButton(
            num_frame, text="+", width=38, height=42,
            font=ctk.CTkFont(size=17, weight="bold"),
            fg_color=_C["panel"], hover_color=_C["border"],
            text_color=_C["text"],
            command=lambda: self._step_num(1),
        ).grid(row=0, column=2, padx=(4, 0))

        # ── Iniciais do redator ───────────────────────────────────────────────
        self._field_label(self._left, 4, "Iniciais do Redator")
        self._sigla_var = ctk.StringVar()
        ctk.CTkEntry(
            self._left, textvariable=self._sigla_var,
            placeholder_text="Ex: xyz",
            font=ctk.CTkFont(size=15), height=42,
        ).grid(row=5, column=0, sticky="ew", padx=20, pady=(0, 14))

        # ── Data ──────────────────────────────────────────────────────────────
        self._field_label(self._left, 6, "Data dos Ofícios")
        self._data_var = ctk.StringVar(value=datetime.now().strftime("%d/%m/%Y"))

        self._data_btn = ctk.CTkButton(
            self._left,
            textvariable=self._data_var,
            font=ctk.CTkFont(size=15),
            height=42, anchor="w",
            fg_color=_C["panel"], hover_color=_C["border"],
            text_color=_C["text"], border_width=2,
            border_color=_C["border"],
            command=self._open_date_picker,
        )
        self._data_btn.grid(row=7, column=0, sticky="ew", padx=20, pady=(0, 14))

        # ── Propositura ───────────────────────────────────────────────────────
        self._field_label(self._left, 9, "Propositura")

        prop_frame = ctk.CTkFrame(self._left, fg_color="transparent")
        prop_frame.grid(row=10, column=0, sticky="ew", padx=20, pady=(0, 14))
        prop_frame.grid_columnconfigure(0, weight=1)

        self._prop_var = ctk.StringVar()
        self._prop_combo = ctk.CTkComboBox(
            prop_frame, variable=self._prop_var,
            font=ctk.CTkFont(size=13), height=42,
            values=[], state="readonly",
        )
        self._prop_combo.grid(row=0, column=0, sticky="ew")

        ctk.CTkButton(
            prop_frame, text="↺", width=42, height=42,
            font=ctk.CTkFont(size=18),
            fg_color=_C["panel"], hover_color=_C["border"],
            text_color=_C["accent"],
            command=self._refresh_proposituras,
        ).grid(row=0, column=1, padx=(6, 0))

        ctk.CTkButton(
            prop_frame, text="📂", width=42, height=42,
            font=ctk.CTkFont(size=16),
            fg_color=_C["panel"], hover_color=_C["border"],
            text_color=_C["text"],
            command=self._browse_file,
        ).grid(row=0, column=2, padx=(4, 0))

        # ── Chave Gemini API ──────────────────────────────────────────────────
        self._field_label(self._left, 11, "Chave Gemini API")

        api_frame = ctk.CTkFrame(self._left, fg_color="transparent")
        api_frame.grid(row=12, column=0, sticky="ew", padx=20, pady=(0, 4))
        api_frame.grid_columnconfigure(0, weight=1)

        env_key = ""  # populated asynchronously after window renders; see _load_api_key_async
        self._apikey_var = ctk.StringVar(value=env_key)
        self._apikey_visible = False
        self._apikey_entry = ctk.CTkEntry(
            api_frame, textvariable=self._apikey_var,
            placeholder_text="Cole sua chave aqui…",
            font=ctk.CTkFont(size=13), height=42, show="•",
        )
        self._apikey_entry.grid(row=0, column=0, sticky="ew")
        self._apikey_var.trace_add("write", self._on_apikey_changed)

        ctk.CTkButton(
            api_frame, text="👁", width=42, height=42,
            font=ctk.CTkFont(size=16),
            fg_color=_C["panel"], hover_color=_C["border"],
            text_color=_C["text"],
            command=self._toggle_key_visibility,
        ).grid(row=0, column=1, padx=(6, 0))

        self._key_status = ctk.CTkLabel(
            self._left,
            text="⚠  Chave não configurada",
            font=ctk.CTkFont(size=11),
            text_color=_C["warn"],
            anchor="w",
        )
        self._key_status.grid(row=13, column=0, sticky="w", padx=22, pady=(0, 6))

        # ── Spacer + Botões ────────────────────────────────────────────────────
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
        self._cancel_btn.grid_remove()  # hidden until processing starts

        modelos_frame = ctk.CTkFrame(self._left, fg_color="transparent")
        modelos_frame.grid(row=17, column=0, sticky="ew", padx=20, pady=(0, 18))
        modelos_frame.grid_columnconfigure(0, weight=1)
        modelos_frame.grid_columnconfigure(1, weight=1)

        _btn_kw: dict[str, Any] = dict(
            font=ctk.CTkFont(size=12),
            height=34, corner_radius=10,
            fg_color=_C["panel"], hover_color=_C["border"],
            text_color=_C["dim"],
            border_width=1, border_color=_C["border"],
        )
        ctk.CTkButton(
            modelos_frame, text="📝  Ofício",
            command=self._open_modelo_oficio, **_btn_kw,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 3))
        ctk.CTkButton(
            modelos_frame, text="📈  Planilha",
            command=self._open_modelo_planilha, **_btn_kw,
        ).grid(row=0, column=1, sticky="ew", padx=(3, 0))

    # ── Right Panel (log + results) ───────────────────────────────────────────
    def _build_right_panel(self) -> None:
        self._right = ctk.CTkFrame(self, fg_color=_C["card"], corner_radius=16)
        self._right.grid(row=1, column=1, sticky="nsew", padx=(7, 14), pady=12)
        self._right.grid_columnconfigure(0, weight=1)
        self._right.grid_rowconfigure(4, weight=1)   # log textbox expands

        self._section_title(self._right, 0, "LOG DE PROCESSAMENTO")
        self._divider(self._right, 1)

        # ── Progress ──────────────────────────────────────────────────────────
        prog_frame = ctk.CTkFrame(self._right, fg_color="transparent")
        prog_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 10))
        prog_frame.grid_columnconfigure(0, weight=1)

        self._progress = ctk.CTkProgressBar(
            prog_frame, height=16, corner_radius=8,
            progress_color=_C["accent"],
            fg_color=_C["panel"],
        )
        self._progress.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        self._progress.set(0)

        self._prog_label = ctk.CTkLabel(
            prog_frame,
            text="Aguardando início…",
            font=ctk.CTkFont(size=12),
            text_color=_C["dim"],
            anchor="w",
        )
        self._prog_label.grid(row=1, column=0, sticky="w")

        self._prog_pct = ctk.CTkLabel(
            prog_frame, text="0 %",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=_C["accent"],
        )
        self._prog_pct.grid(row=1, column=1, sticky="e")

        # ── "Saída" sub-title ─────────────────────────────────────────────────
        ctk.CTkLabel(
            self._right, text="SAÍDA",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=_C["dim"],
            anchor="w",
        ).grid(row=3, column=0, sticky="w", padx=22, pady=(4, 2))

        # ── Log textbox ───────────────────────────────────────────────────────
        self._log_box = ctk.CTkTextbox(
            self._right,
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color=_C["panel"],
            text_color=_C["text"],
            corner_radius=10,
            activate_scrollbars=True,
            wrap="word",
            state="disabled",
        )
        self._log_box.grid(row=4, column=0, sticky="nsew", padx=20, pady=(0, 10))

        # Colored tags on the underlying tk.Text widget
        tb = self._log_box._textbox
        tb.tag_config("success", foreground=_C["success"])
        tb.tag_config("error",   foreground=_C["error"])
        tb.tag_config("warn",    foreground=_C["warn"])
        tb.tag_config("dim",     foreground=_C["dim"])
        tb.tag_config("accent",  foreground=_C["accent"])
        tb.tag_config("bold",    font=("Consolas", 12, "bold"),
                      foreground=_C["text"])

        # ── Summary bar ───────────────────────────────────────────────────────
        summary = ctk.CTkFrame(self._right, fg_color=_C["panel"], corner_radius=10)
        summary.grid(row=5, column=0, sticky="ew", padx=20, pady=(0, 18))
        summary.grid_columnconfigure(0, weight=1)

        self._summary_label = ctk.CTkLabel(
            summary,
            text="Nenhum processamento realizado ainda.",
            font=ctk.CTkFont(size=12),
            text_color=_C["dim"],
            anchor="w",
        )
        self._summary_label.grid(row=0, column=0, sticky="w", padx=16, pady=10)

        ctk.CTkButton(
            summary,
            text="📁  Ofícios",
            font=ctk.CTkFont(size=12),
            height=36, width=110, corner_radius=8,
            fg_color=_C["border"], hover_color=_C["accent2"],
            text_color=_C["text"],
            command=self._open_output_folder,
        ).grid(row=0, column=1, padx=(0, 6), pady=8)

        ctk.CTkButton(
            summary,
            text="📊  Planilha",
            font=ctk.CTkFont(size=12),
            height=36, width=110, corner_radius=8,
            fg_color=_C["border"], hover_color=_C["accent2"],
            text_color=_C["text"],
            command=self._open_spreadsheet_folder,
        ).grid(row=0, column=2, padx=(0, 12), pady=8)

    # ── Footer ────────────────────────────────────────────────────────────────
    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color=_C["card"], corner_radius=0, height=30)
        footer.grid(row=2, column=0, columnspan=2, sticky="ew")
        footer.grid_propagate(False)
        footer.grid_columnconfigure(0, weight=1)
        footer.grid_columnconfigure(1, weight=0)

        ctk.CTkLabel(
            footer,
            text=f"ZWave OfficeLetters v{_ao.APP_VERSION}  •  Câmara Municipal de Santa Bárbara d'Oeste/SP  •  Licenced under GPLv3 •  Powered by Gemini AI",
            font=ctk.CTkFont(size=10),
            text_color=_C["dim"],
        ).grid(row=0, column=0, sticky="w", padx=16, pady=6)

        ctk.CTkLabel(
            footer,
            text=f"© {_ao.APP_AUTHOR}",
            font=ctk.CTkFont(size=10),
            text_color=_C["dim"],
        ).grid(row=0, column=1, sticky="e", padx=16, pady=6)

    # =========================================================================
    # Widget helpers
    # =========================================================================
    def _section_title(self, parent: ctk.CTkFrame, row: int, text: str) -> None:
        ctk.CTkLabel(
            parent, text=text,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=_C["accent"],
            anchor="w",
        ).grid(row=row, column=0, sticky="w", padx=20, pady=(20, 4))

    def _divider(self, parent: ctk.CTkFrame, row: int) -> None:
        ctk.CTkFrame(
            parent, height=1, fg_color=_C["border"],
        ).grid(row=row, column=0, sticky="ew", padx=20, pady=(0, 14))

    def _field_label(self, parent: ctk.CTkFrame, row: int, text: str) -> None:
        ctk.CTkLabel(
            parent, text=text,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=_C["text"],
            anchor="w",
        ).grid(row=row, column=0, sticky="w", padx=20, pady=(0, 4))

    # =========================================================================
    # Interactions
    # =========================================================================
    def _on_apikey_changed(self, *_: Any) -> None:
        has_key = bool(self._apikey_var.get().strip())
        self._key_status.configure(
            text="✔  Chave configurada" if has_key else "⚠  Chave não configurada",
            text_color=_C["success"] if has_key else _C["warn"],
        )

    def _load_api_key_async(self) -> None:
        """Runs registry migration and key loading in a background thread.

        Deferred so registry/keyring I/O (~540 ms on first run) does not block
        the window from appearing.  Migration must complete before key loading,
        and both run sequentially in the same thread so ordering is preserved.
        """
        def _fetch() -> None:
            try:
                _ao._migrar_chave_do_registro()  # no-op after first run
                key = _ao._carregar_api_key()
            except Exception:
                key = ""
            self.after(0, lambda: self._apikey_var.set(key))

        threading.Thread(target=_fetch, daemon=True).start()

    def _step_num(self, delta: int) -> None:
        try:
            val = max(1, int(self._num_var.get()) + delta)
        except ValueError:
            val = 1
        self._num_var.set(str(val))

    def _open_date_picker(self) -> None:
        from tkcalendar import Calendar  # lazy import

        popup = ctk.CTkToplevel(self)
        popup.title("Selecionar Data")
        popup.resizable(False, False)
        popup.grab_set()
        popup.configure(fg_color=_C["card"])

        try:
            current = datetime.strptime(self._data_var.get(), "%d/%m/%Y")
        except ValueError:
            current = datetime.now()

        cal = Calendar(
            popup,
            selectmode="day",
            year=current.year,
            month=current.month,
            day=current.day,
            date_pattern="dd/mm/yyyy",
            background=_C["panel"],
            foreground=_C["text"],
            bordercolor=_C["border"],
            headersbackground=_C["bg"],
            headersforeground=_C["accent"],
            selectbackground=_C["accent"],
            selectforeground="#ffffff",
            normalbackground=_C["panel"],
            normalforeground=_C["text"],
            weekendbackground=_C["panel"],
            weekendforeground=_C["dim"],
            othermonthbackground=_C["bg"],
            othermonthforeground=_C["dim"],
            othermonthwebackground=_C["bg"],
            othermonthweforeground=_C["dim"],
            locale="pt_BR",
        )
        cal.pack(padx=14, pady=(14, 6))

        def _confirm() -> None:
            self._data_var.set(cal.get_date())
            popup.destroy()

        ctk.CTkButton(
            popup, text="Confirmar",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=38, corner_radius=8,
            fg_color=_C["accent"], hover_color=_C["accent2"],
            command=_confirm,
        ).pack(fill="x", padx=14, pady=(0, 14))

        popup.update_idletasks()
        x = self.winfo_x() + (self.winfo_width()  - popup.winfo_width())  // 2
        y = self.winfo_y() + (self.winfo_height() - popup.winfo_height()) // 2
        popup.geometry(f"+{x}+{y}")

    def _toggle_key_visibility(self) -> None:
        self._apikey_visible = not self._apikey_visible
        self._apikey_entry.configure(show="" if self._apikey_visible else "•")

    def _refresh_proposituras(self) -> None:
        from auto_oficios import listar_proposituras  # lazy import
        files = listar_proposituras()
        self._prop_files = {p.name: str(p) for p in files}
        names = list(self._prop_files.keys())
        self._prop_combo.configure(values=names)
        if names:
            self._prop_combo.set(names[0])
        else:
            self._prop_combo.set("(nenhum arquivo em proposituras)")

    def _browse_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Selecionar propositura",
            initialdir=str(Path(_ao.PASTA_PROPOSITURAS)),
            filetypes=[
                ("Documentos", "*.txt *.docx *.doc *.odt *.pdf"),
                ("Todos os arquivos", "*.*"),
            ],
        )
        if path:
            name = Path(path).name
            self._prop_files[name] = path
            vals = self._prop_combo.cget("values")
            if name not in vals:
                self._prop_combo.configure(values=list(vals) + [name])
            self._prop_combo.set(name)

    def _open_modelo_oficio(self) -> None:
        if getattr(sys, "frozen", False):
            modelo = Path(sys.executable).parent / "modelo_oficio.docx"
        else:
            modelo = Path(__file__).parent / "modelo_oficio.docx"
        if not modelo.exists():
            messagebox.showwarning(
                "Modelo não encontrado",
                f"O arquivo não foi encontrado:\n{modelo}\n\n"
                "Crie o arquivo modelo_oficio.docx na mesma pasta do aplicativo e tente novamente.",
            )
            return
        os.startfile(str(modelo))

    def _open_modelo_planilha(self) -> None:
        if getattr(sys, "frozen", False):
            modelo = Path(sys.executable).parent / _ao.MODELO_PLANILHA
        else:
            modelo = Path(__file__).parent / _ao.MODELO_PLANILHA
        if not modelo.exists():
            try:
                _ao.criar_modelo_planilha(modelo)
            except Exception as exc:
                messagebox.showerror("Erro", f"Não foi possível criar o modelo:\n{exc}")
                return
        os.startfile(str(modelo))

    def _open_output_folder(self) -> None:
        from auto_oficios import PASTA_SAIDA
        folder = Path(PASTA_SAIDA).resolve()
        folder.mkdir(exist_ok=True)
        os.startfile(str(folder))

    def _open_spreadsheet_folder(self) -> None:
        from auto_oficios import PASTA_PLANILHA
        folder = Path(PASTA_PLANILHA).resolve()
        folder.mkdir(exist_ok=True)
        os.startfile(str(folder))

    # =========================================================================
    # Log helpers (must be called from main thread only)
    # =========================================================================
    def _log(self, text: str, tag: str = "") -> None:
        tb = self._log_box._textbox  # bypass CTk configure overhead for state changes
        tb.configure(state="normal")
        if tag:
            tb.insert("end", text + "\n", tag)
        else:
            tb.insert("end", text + "\n")
        tb.see("end")
        tb.configure(state="disabled")

    def _clear_log(self) -> None:
        tb = self._log_box._textbox
        tb.configure(state="normal")
        tb.delete("1.0", "end")
        tb.configure(state="disabled")

    # =========================================================================
    # Processing
    # =========================================================================
    def _start_processing(self) -> None:
        if self._processing:
            return

        # Validate inputs
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

        prop_name = self._prop_var.get()
        arquivo = self._prop_files.get(prop_name, "")
        if not arquivo or not Path(arquivo).exists():
            messagebox.showerror("Erro de Validação",
                                 "Selecione um arquivo de propositura válido.")
            return

        api_key = self._apikey_var.get().strip()
        if not api_key:
            messagebox.showerror("Erro de Validação", "Informe a chave da API Gemini.")
            return

        from auto_oficios import MESES_PT
        data_extenso = f"{data_dt.day} de {MESES_PT[data_dt.month]} de {data_dt.year}"

        # Reset UI for new run
        self._processing = True
        self._cancel_event.clear()
        self._gen_btn.configure(state="disabled", text="⏳   Processando…")
        self._cancel_btn.grid()  # show cancel button
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
            "arquivo":      arquivo,
            "api_key":      api_key,
        }
        threading.Thread(target=self._worker, args=(inputs,), daemon=True).start()

    def _request_cancel(self) -> None:
        self._cancel_event.set()
        self._cancel_btn.configure(state="disabled", text="Cancelando…")

    def _worker(self, inputs: dict[str, Any]) -> None:
        """Runs in a background thread. Sends messages to self._queue."""
        Q = self._queue
        try:
            from google import genai
            from docxtpl import DocxTemplate
            from openpyxl import Workbook

            log_path = _ao.configurar_logging()
            Q.put(("log", f"📋  Log: {log_path}", "dim"))

            _ao._salvar_api_key_no_ambiente(inputs["api_key"])
            cliente = genai.Client(api_key=inputs["api_key"])

            Q.put(("log", f"📂  Lendo: {Path(inputs['arquivo']).name}", "accent"))
            conteudo = _ao.ler_arquivo_mocoes(inputs["arquivo"])

            textos = _RE_MOCAO_SPLIT.split(conteudo)
            textos = [t.strip() for t in textos if t.strip()]
            total = len(textos)

            Q.put(("log", f"\n✦  {total} moção(ões) encontrada(s). Iniciando IA…\n", "bold"))
            Q.put(("progress", 0, total))

            Path(_ao.PASTA_SAIDA).mkdir(parents=True, exist_ok=True)
            if not Path("modelo_oficio.docx").exists():
                Q.put(("error", "Arquivo 'modelo_oficio.docx' não encontrado."))
                return

            dados_planilha: list[list[str]] = []
            numero_atual = inputs["num_inicial"]
            year = int(inputs["data_iso"][:4])
            erros = 0
            inicio = time.time()

            for i, texto in enumerate(textos, 1):
                if self._cancel_event.is_set():
                    Q.put(("cancelled", i - 1, total))
                    return

                Q.put(("log", f"─── Moção {i}/{total} ─────────────────────────", "dim"))
                Q.put(("progress", i - 1, total))

                try:
                    dados = _ao.extrair_dados_com_ia(texto, cliente)
                except Exception as e:
                    Q.put(("log", f"  ✖  Erro: {e}", "error"))
                    erros += 1
                    continue

                dados["numero_mocao"] = _ao.normalizar_numero_mocao(dados["numero_mocao"])
                texto_autoria, sigla_autores = _ao.formatar_autores(dados["autores"])

                for dest in dados["destinatarios"]:
                    info = _ao.processar_destinatario(dest)
                    num_str = f"{numero_atual:03d}"

                    ctx: dict[str, str] = {
                        "num_oficio":           num_str,
                        "data_extenso":         inputs["data_extenso"],
                        "tipo_mocao":           str(dados["tipo_mocao"]),
                        "num_mocao":            str(dados["numero_mocao"]),
                        "vocativo":             info["vocativo"],
                        "pronome_corpo":        info["pronome_corpo"],
                        "texto_autoria":        texto_autoria,
                        "tratamento_rodape":    info["tratamento_rodape"],
                        "destinatario_nome":    info["destinatario_nome"],
                        "destinatario_endereco": info["destinatario_endereco"],
                    }

                    doc = DocxTemplate("modelo_oficio.docx")
                    doc.render(ctx)

                    nome = _ao.construir_nome_arquivo(
                        num_str, inputs["sigla"],
                        dados["tipo_mocao"], dados["numero_mocao"],
                        info["envio"], dest["nome"], sigla_autores,
                        ano=year,
                    )
                    doc.save(os.path.join(_ao.PASTA_SAIDA, nome))

                    Q.put(("log", f"  ✔  {nome}", "success"))

                    dados_planilha.append([
                        num_str,
                        inputs["data_iso"],
                        f"{info['tratamento_rodape']} {info['destinatario_nome']}".strip(),
                        f"Encaminha Moção de {dados['tipo_mocao']} nº {dados['numero_mocao']}/{year}",
                        ", ".join(dados["autores"]),
                        info["envio"],
                        inputs["sigla"],
                    ])
                    numero_atual += 1

            # Excel spreadsheet
            Q.put(("log", "\n📊  Gerando planilha Excel…", "accent"))
            if getattr(sys, "frozen", False):
                _modelo_xlsx = Path(sys.executable).parent / _ao.MODELO_PLANILHA
            else:
                _modelo_xlsx = Path(__file__).parent / _ao.MODELO_PLANILHA
            if _modelo_xlsx.exists():
                from openpyxl import load_workbook
                wb = load_workbook(str(_modelo_xlsx))
                ws = wb.active
                assert ws is not None
            else:
                wb = Workbook()
                ws = wb.active
                assert ws is not None
                ws.append(["Of. n.º", "Data", "Destinatário", "Assunto",
                            "Vereador", "Envio", "Autor"])
            ws.title = f"Controle {year}"
            for row in dados_planilha:
                ws.append(row)
            Path(_ao.PASTA_PLANILHA).mkdir(parents=True, exist_ok=True)
            wb.save(os.path.join(_ao.PASTA_PLANILHA, "CONTROLE_OFICIOS.xlsx"))

            elapsed = time.time() - inicio
            Q.put(("done", len(dados_planilha), erros, elapsed))

        except Exception as e:
            Q.put(("error", str(e)))

    # =========================================================================
    # Queue polling (runs on main thread via after())
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
            self._prog_label.configure(
                text=f"Concluído em {tempo}",
                text_color=color,
            )
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

        elif kind == "cancelled":
            done_so_far, total = msg[1], msg[2]
            self._processing = False
            self._cancel_btn.grid_remove()
            self._cancel_btn.configure(state="normal", text="⏹   CANCELAR")
            self._gen_btn.configure(state="normal", text="⚡   GERAR OFÍCIOS")
            self._progress.configure(progress_color=_C["warn"])
            self._prog_label.configure(text=f"Cancelado após {done_so_far} de {total} moções.", text_color=_C["warn"])
            self._log(f"\n⏹  Processamento cancelado após {done_so_far}/{total} moções.", "warn")

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


# =============================================================================
if __name__ == "__main__":
    app = AutoOficiosApp()
    app.mainloop()
