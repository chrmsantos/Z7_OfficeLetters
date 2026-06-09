"""Entry point for ``python -m z7_officeletters``.

Launches the graphical interface.  The module is also used as the
PyInstaller analysis script so that the exe bundle starts the GUI.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Any

# When executed directly (python __main__.py) the src/ directory is not on
# sys.path; add it so that the z7_officeletters package can be found.
_src = Path(__file__).parent.parent
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))


def main() -> None:
    """Start the GUI application."""
    try:
        from z7_officeletters.gui.app import AutoOficiosApp  # noqa: PLC0415
    except Exception as exc:
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Erro de Inicialização",
                f"Ocorreu um erro crítico ao carregar o aplicativo:\n\n{exc}\n\n"
                "Verifique os logs ou a integridade dos arquivos do sistema.",
            )
            root.destroy()
        except Exception:
            pass
        raise exc

    app = AutoOficiosApp()
    app.mainloop()


if __name__ == "__main__":
    main()
