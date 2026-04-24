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
    ["ui.py"],
    pathex=["."],
    binaries=[],
    datas=[
        # customtkinter: temas, fontes e imagens internas
        (ctk_dir, "customtkinter"),
        # Babel locale data (necessário para tkcalendar com locale="pt_BR")
        (str(Path(babel_dir) / "locale-data"), "babel/locale-data"),
        (str(Path(babel_dir) / "global.dat"),  "babel"),
        # Arquivos de dados da aplicação (copiados para o mesmo diretório do exe)
        ("config.json",                   "."),
        ("templates/modelo_oficio.docx",  "templates"),
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
        # Core app
        "auto_oficios",
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
