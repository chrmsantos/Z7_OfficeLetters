# auto_oficios.spec
# PyInstaller spec para empacotar Z7_OfficeLetters como executável Windows (.exe)
# Uso:  pyinstaller auto_oficios.spec

import sys
from pathlib import Path

block_cipher = None

# ── Localizar assets de pacotes ──────────────────────────────────────────────
import customtkinter
import tkcalendar
import babel

ctk_dir   = str(Path(customtkinter.__file__).parent)
babel_dir = str(Path(babel.__file__).parent)

a = Analysis(
    ["src/z7_officeletters/__main__.py"],
    pathex=["src", "."],
    binaries=[],
    datas=[
        # customtkinter: temas, fontes e imagens internas
        (ctk_dir, "customtkinter"),
        # Babel locale data (necessário para tkcalendar com locale="pt_BR")
        (str(Path(babel_dir) / "locale-data"), "babel/locale-data"),
        (str(Path(babel_dir) / "global.dat"),  "babel"),
        # Arquivos de dados da aplicação (copiados para o mesmo diretório do exe)
        ("config.json",                            "."),
        ("templates/modelo_mocao.docx",            "templates"),
        ("templates/modelo_requer_pesar.docx",     "templates"),
        ("templates/modelo_planilha.xlsx",         "templates"),
    ],
    hiddenimports=[
        # GUI
        "customtkinter",
        "tkcalendar",
        "babel",
        "babel.numbers",
        "babel.dates",
        "babel.core",
        # Docx / Excel
        "docxtpl",
        "docx",
        "docx.oxml",
        "docx.oxml.ns",
        "docx.oxml.parser",
        "docx.parts",
        "docx.parts.document",
        "docx.shared",
        "openpyxl",
        "openpyxl.cell._writer",
        # PDF
        "pypdf",
        "pypdf._reader",
        # Google GenAI
        "google.genai",
        "google.auth",
        "google.auth.transport",
        "google.auth.transport.requests",
        # Windows
        "winreg",
        # Credential Manager (API key encryption)
        "keyring",
        "keyring.backends",
        "keyring.backends.Windows",
        # Recycle Bin
        "send2trash",
        "send2trash.plat_win",
        # Core app
        "z7_officeletters",
        "z7_officeletters.core",
        "z7_officeletters.core.ai",
        "z7_officeletters.core.api_key",
        "z7_officeletters.core.authors",
        "z7_officeletters.core.config",
        "z7_officeletters.core.documents",
        "z7_officeletters.core.files",
        "z7_officeletters.core.logging_setup",
        "z7_officeletters.core.recipients",
        "z7_officeletters.gui",
        "z7_officeletters.gui.app",
        "z7_officeletters.gui.constants",
        "z7_officeletters.gui.dialogs",
        "z7_officeletters.gui.dialogs.api_key",
        "z7_officeletters.gui.dialogs.config_editor",
        "z7_officeletters.gui.dialogs.confirmation",
        "z7_officeletters.gui.dialogs.date_picker",
        "z7_officeletters.gui.dialogs.prompt_editor",
        "z7_officeletters.gui.workers",
        "z7_officeletters.gui.workers.processor",
        # Misc
        "PIL",
        "PIL._tkinter_finder",
        "pkg_resources",
        "packaging",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "_pytest", "unittest", "test", "tests"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Z7_OfficeLetters",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # sem janela de console (app gráfico)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="icon.ico",
)
