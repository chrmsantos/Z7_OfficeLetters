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


def _criar_splash() -> Any:
    """Create a borderless splash window using stdlib tkinter only.

    Only ``tkinter`` (stdlib) is imported here so the window appears
    almost instantly, before any heavy dependency is loaded.

    Returns:
        The ``tk.Tk`` root window (already visible and animating).
    """
    import tkinter as tk  # noqa: PLC0415 — stdlib, intentionally late

    root = tk.Tk()
    root.overrideredirect(True)
    root.configure(bg="#0f111a")
    root.attributes("-topmost", True)
    root.resizable(False, False)

    w, h = 380, 168
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    tk.Label(
        root, text="Z7 OfficeLetters",
        bg="#0f111a", fg="#cdd6f4",
        font=("Segoe UI", 20, "bold"),
    ).pack(pady=(30, 6))

    tk.Label(
        root, text="Aguarde \u2014 o aplicativo est\u00e1 carregando\u2026",
        bg="#0f111a", fg="#6c7086",
        font=("Segoe UI", 10),
    ).pack()

    # Indeterminate bouncing progress bar (pure tkinter, no canvas needed).
    bar_outer = tk.Frame(root, bg="#1a1d2e", height=4, width=w - 60)
    bar_outer.pack(pady=(22, 0))
    bar_outer.pack_propagate(False)
    segment_w = 90
    bar_inner = tk.Frame(bar_outer, bg="#8b5cf6", height=4, width=segment_w)
    bar_inner.place(x=0, y=0, relheight=1, width=segment_w)

    root.update()

    # Animate the segment bouncing left \u2194 right while the event loop runs.
    track_w = (w - 60) - segment_w
    _state: dict[str, int] = {"pos": 0, "dir": 1}

    def _tick() -> None:
        _state["pos"] += _state["dir"] * 5
        if _state["pos"] >= track_w:
            _state["pos"] = track_w
            _state["dir"] = -1
        elif _state["pos"] <= 0:
            _state["pos"] = 0
            _state["dir"] = 1
        bar_inner.place(x=_state["pos"], y=0, relheight=1, width=segment_w)
        root.after(16, _tick)

    root.after(16, _tick)
    return root


def main() -> None:
    """Start the GUI application."""
    # Start loading the heavy application class immediately, in parallel with
    # the splash-window setup that follows (~120 ms overlap).
    _result: dict[str, Any] = {}

    def _load() -> None:
        try:
            from z7_officeletters.gui.app import AutoOficiosApp  # noqa: PLC0415
            _result["cls"] = AutoOficiosApp
        except Exception as exc:  # noqa: BLE001
            _result["error"] = exc

    t = threading.Thread(target=_load, daemon=True)
    t.start()

    # Show the splash — only stdlib tkinter is imported here.
    splash = _criar_splash()

    def _check() -> None:
        if t.is_alive():
            splash.after(50, _check)
            return
        # Loading finished \u2014 close the splash and hand control to the app.
        splash.destroy()

    splash.after(50, _check)
    splash.mainloop()  # blocks until splash.destroy() is called

    if "error" in _result:
        raise _result["error"]

    app = _result["cls"]()
    app.mainloop()


if __name__ == "__main__":
    main()
