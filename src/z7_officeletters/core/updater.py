"""Self-updater logic for Z7 OfficeLetters.

Handles checking the GitHub Releases API for new updates, comparing version
strings using SemVer, downloading updates with visual progress, and replacing the
running executable in-place.

Public exports:
    obter_ultima_versao: Query GitHub for the latest release details.
    comparar_versoes: Compare two version strings.
    run_update_check: Check for updates and initiate the update process.
"""

from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
import tkinter as tk
import urllib.error
import urllib.request
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable

from z7_officeletters.core.logging_setup import logger

__all__ = ["obter_ultima_versao", "comparar_versoes", "run_update_check"]


def parse_version(v_str: str) -> tuple[tuple[int, ...], tuple[int, tuple[str | int, ...]]]:
    """Parse a version string into a structure suitable for SemVer comparison.

    Handles major, minor, patch and optional pre-release tag (e.g., v3.2.0-rc1).
    """
    clean_v = v_str.strip().lstrip("vV").split("+")[0]
    parts = clean_v.split("-", 1)
    version_part = parts[0]
    prerelease_part = parts[1] if len(parts) > 1 else ""

    version_nums = tuple(int(x) for x in re.findall(r"\d+", version_part))
    if len(version_nums) < 3:
        version_nums = version_nums + (0,) * (3 - len(version_nums))

    if not prerelease_part:
        # Stable release compares greater than pre-release.
        # We return a tuple starting with 1 to indicate stable.
        return (version_nums, (1, ()))

    # Pre-release compares lower than stable release.
    # We return a tuple starting with 0 to indicate pre-release.
    pre_elements: list[str | int] = []
    for item in prerelease_part.split("."):
        for subitem in re.findall(r"[a-zA-Z]+|\d+", item):
            if subitem.isdigit():
                pre_elements.append(int(subitem))
            else:
                pre_elements.append(subitem.lower())

    return (version_nums, (0, tuple(pre_elements)))


def comparar_versoes(v1: str, v2: str) -> bool:
    """Compare two version strings (SemVer style).

    Returns:
        True if v1 is strictly greater than v2, False otherwise.
    """
    try:
        p1 = parse_version(v1)
        p2 = parse_version(v2)

        # Compare main version numbers (major, minor, patch)
        if p1[0] != p2[0]:
            return p1[0] > p2[0]

        # Compare stable vs pre-release
        if p1[1][0] != p2[1][0]:
            return p1[1][0] > p2[1][0]

        # If both are stable and their main version is equal, they are equal
        if p1[1][0] == 1:
            return False

        # Both are pre-releases, compare their elements
        pre1 = p1[1][1]
        pre2 = p2[1][1]

        for e1, e2 in zip(pre1, pre2):
            if type(e1) is type(e2):
                if e1 != e2:
                    return e1 > e2  # type: ignore[operator]
            else:
                # Numeric identifiers always have lower precedence than non-numeric
                return isinstance(e1, str)

        # If all compared elements are equal, the one with more elements is greater
        return len(pre1) > len(pre2)
    except Exception as exc:
        logger.warning("Falha ao comparar versões %r e %r: %s", v1, v2, exc)
        return False


def obter_ultima_versao() -> tuple[str, str]:
    """Query the GitHub Releases API for the latest stable release of the project.

    Returns:
        A tuple (tag_name, browser_download_url) for the Z7_OfficeLetters.exe asset.

    Raises:
        RuntimeError: If the request fails, returns invalid JSON, or if the
            required executable asset is missing from the release.
    """
    url = "https://api.github.com/repos/chrmsantos/Z7_OfficeLetters/releases/latest"
    req = urllib.request.Request(url, headers={"User-Agent": "Z7_OfficeLetters-Updater"})

    try:
        logger.info("Verificando atualizações no GitHub: %s", url)
        with urllib.request.urlopen(req, timeout=10) as response:
            status = response.status
            if status != 200:
                raise RuntimeError(f"Servidor respondeu com código HTTP {status}")
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as http_exc:
        if http_exc.code == 403:
            logger.error("Limite de requisições da API do GitHub excedido.")
            raise RuntimeError(
                "Limite de requisições da API do GitHub excedido para o seu IP. "
                "Por favor, aguarde alguns minutos e tente novamente."
            ) from http_exc
        raise RuntimeError(f"Servidor respondeu com código HTTP {http_exc.code}") from http_exc
    except Exception as exc:
        logger.error("Falha ao consultar a API do GitHub: %s", exc)
        raise RuntimeError(f"Erro ao conectar com o servidor de atualizações: {exc}") from exc

    tag_name = data.get("tag_name")
    if not tag_name:
        raise RuntimeError("A resposta do servidor de atualizações não continha informações de versão (tag_name).")

    assets = data.get("assets", [])
    download_url = ""
    for asset in assets:
        if asset.get("name") == "Z7_OfficeLetters.exe":
            download_url = asset.get("browser_download_url", "")
            break

    if not download_url:
        raise RuntimeError(
            f"A nova versão ({tag_name}) está disponível, mas o arquivo executável "
            "'Z7_OfficeLetters.exe' não foi publicado nos anexos da release ainda."
        )

    logger.info("Última versão disponível encontrada: %s", tag_name)
    return tag_name, download_url


def check_write_permission(dest_path: Path) -> bool:
    """Check if the directory containing the destination path is writable.

    Args:
        dest_path: The file path to verify write access for.

    Returns:
        True if the parent directory is writable, False otherwise.
    """
    try:
        parent = dest_path.parent
        parent.mkdir(parents=True, exist_ok=True)
        # Try creating a dummy file in the directory
        temp_file = parent / f".write_test_{os.getpid()}"
        temp_file.touch()
        temp_file.unlink()
        return True
    except Exception:
        return False


def _get_project_root() -> Path:
    """Return the project root path."""
    return Path(__file__).parent.parent.parent.parent


def _get_target_path() -> Path:
    """Return the final target executable path based on whether the app is frozen or not."""
    is_frozen = getattr(sys, "frozen", False)
    if not is_frozen:
        return _get_project_root() / "dist" / "Z7_OfficeLetters.exe"
    return Path(sys.executable)


class UpdateProgressWindow:
    """Toplevel Tkinter window showing the download progress of the update."""

    def __init__(
        self,
        parent: tk.Tk | tk.Toplevel,
        download_url: str,
        dest_path: Path,
        new_version: str = "",
    ) -> None:
        """Initialize the download progress window and start download thread.

        Args:
            parent: The parent Tkinter window.
            download_url: The URL to download the update from.
            dest_path: The local destination path for the executable.
            new_version: The version string being installed (e.g. "4.7.1").
        """
        self.parent = parent
        self.download_url = download_url
        self.dest_path = dest_path
        self.new_version = new_version

        self.win = tk.Toplevel(parent)
        self.win.title("Baixando Atualização")
        self.win.resizable(False, False)
        self.win.transient(parent)
        self.win.grab_set()

        # UI variables
        self.progress_var = tk.DoubleVar(value=0.0)
        self.status_var = tk.StringVar(value="Iniciando download...")

        # Color palette from z7_officeletters
        from z7_officeletters.gui.constants import _C
        self.palette = _C
        self.win.configure(bg=self.palette["bg"])

        logger.info(
            "Initializing UpdateProgressWindow (download_url=%s, dest_path=%s)...",
            self.download_url,
            self.dest_path,
        )
        self._build_ui()

        self.cancel_event = threading.Event()
        self.download_thread = threading.Thread(target=self._run_download, daemon=True)
        self.download_thread.start()

        self.win.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.win.bind("<Escape>", lambda _e: self.on_cancel())

    def _build_ui(self) -> None:
        p = self.palette

        # Top banner frame
        header_frame = tk.Frame(self.win, bg=p["panel"], pady=12)
        header_frame.pack(fill=tk.X)

        tk.Label(
            header_frame,
            text="🚀  Atualização do Sistema",
            font=("Segoe UI", 11, "bold"),
            fg=p["accent"],
            bg=p["panel"],
        ).pack(anchor="w", padx=16)

        tk.Frame(self.win, bg=p["border"], height=1).pack(fill=tk.X)

        # Body frame
        body = tk.Frame(self.win, bg=p["bg"], padx=20, pady=16)
        body.pack(fill=tk.BOTH, expand=True)

        self.status_lbl = tk.Label(
            body,
            textvariable=self.status_var,
            font=("Segoe UI", 9),
            fg=p["text"],
            bg=p["bg"],
            anchor="w",
            justify="left",
            wraplength=360,
        )
        self.status_lbl.pack(fill=tk.X, pady=(0, 12))

        # Progressbar
        self.progress = ttk.Progressbar(
            body,
            orient="horizontal",
            length=360,
            mode="determinate",
            variable=self.progress_var,
        )
        self.progress.pack(fill=tk.X, pady=(0, 16))

        # Separator and Footer with Cancel button
        tk.Frame(self.win, bg=p["border"], height=1).pack(fill=tk.X)
        footer = tk.Frame(self.win, bg=p["panel"], pady=8)
        footer.pack(fill=tk.X)

        cancel_btn = tk.Button(
            footer,
            text="Cancelar",
            command=self.on_cancel,
            font=("Segoe UI", 9, "bold"),
            fg="#ffffff",
            bg="#5a1a1a",
            activeforeground="#ffffff",
            activebackground="#5a1a1a",
            relief=tk.FLAT,
            cursor="hand2",
            padx=14,
            pady=5,
            bd=0,
        )
        cancel_btn.pack(side=tk.RIGHT, padx=16)

        def on_enter(_e: tk.Event) -> None:
            cancel_btn.configure(bg="#802020", activebackground="#802020")

        def on_leave(_e: tk.Event) -> None:
            cancel_btn.configure(bg="#5a1a1a", activebackground="#5a1a1a")

        cancel_btn.bind("<Enter>", on_enter)
        cancel_btn.bind("<Leave>", on_leave)

        # Center the window relative to parent
        self.win.update_idletasks()
        w, h = 400, 190
        px = self.parent.winfo_x() + (self.parent.winfo_width() - w) // 2
        py = self.parent.winfo_y() + (self.parent.winfo_height() - h) // 2
        self.win.geometry(f"{w}x{h}+{px}+{py}")

    def on_cancel(self) -> None:
        """Prompt user for confirmation when canceling the download."""
        if self.cancel_event.is_set():
            return
        logger.info("User requested cancellation of the download.")
        if messagebox.askyesno(
            "Cancelar Download",
            "Deseja realmente cancelar o download da atualização?",
            parent=self.win,
        ):
            logger.info("User confirmed download cancellation.")
            self.cancel_event.set()
            self.status_var.set("Cancelando...")
            self.win.after(200, self.win.destroy)

    def _run_download(self) -> None:
        temp_dest = self.dest_path.with_suffix(".tmp_download")
        try:
            logger.info(
                "Starting download from %s to %s",
                self.download_url,
                temp_dest,
            )
            req = urllib.request.Request(
                self.download_url, headers={"User-Agent": "Z7_OfficeLetters-Updater"}
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                total_size = int(response.info().get("Content-Length", 0))
                logger.info(
                    "Connected to download server. Expected total size: %s bytes",
                    total_size,
                )
                bytes_downloaded = 0
                block_size = 16384
                last_logged_quarter = 0
                last_ui_update_time = 0.0
                last_percent = -1

                with open(temp_dest, "wb") as f:
                    while not self.cancel_event.is_set():
                        block = response.read(block_size)
                        if not block:
                            break
                        f.write(block)
                        bytes_downloaded += len(block)

                        percent = (bytes_downloaded / total_size) * 100 if total_size else 0
                        current_percent_int = int(percent)
                        now = time.time()

                        current_quarter = int(percent // 25) * 25
                        if current_quarter > last_logged_quarter and current_quarter <= 100:
                            logger.info(
                                "Download progress: %d%% (%d/%d bytes)",
                                current_quarter,
                                bytes_downloaded,
                                total_size,
                            )
                            last_logged_quarter = current_quarter

                        if current_percent_int != last_percent or (now - last_ui_update_time) >= 0.1:
                            speed_msg = (
                                f"Baixando: {percent:.1f}% "
                                f"({bytes_downloaded // 1024} KB / {total_size // 1024} KB)"
                            )
                            self.win.after(
                                0, lambda p=percent, m=speed_msg: self._update_ui_state(p, m)
                            )
                            last_percent = current_percent_int
                            last_ui_update_time = now

            if self.cancel_event.is_set():
                logger.info(
                    "Download loop terminated due to cancellation. Cleaning up temporary file..."
                )
                if temp_dest.exists():
                    temp_dest.unlink(missing_ok=True)
                return

            logger.info(
                "Download completed successfully. Total size: %s bytes. Requesting finalization...",
                bytes_downloaded,
            )

            # Request finalization in main GUI thread
            self.win.after(0, lambda: self.status_var.set("Instalando atualização..."))
            self.win.after(0, lambda: self._finalize_update(temp_dest))

        except Exception as exc:
            logger.exception("Failed to download update")
            if temp_dest.exists():
                temp_dest.unlink(missing_ok=True)
            self.win.after(0, lambda e=exc: self._handle_error(e))

    def _update_ui_state(self, percent: float, msg: str) -> None:
        if self.win.winfo_exists():
            self.progress_var.set(percent)
            self.status_var.set(msg)

    def _finalize_update(self, temp_dest: Path) -> None:
        try:
            is_frozen = getattr(sys, "frozen", False)
            if not is_frozen:
                logger.info(
                    "Finalizing update in DEVELOPMENT mode. Simulating update process...",
                )
                # Dev mode target path simulation
                dev_dest = self.dest_path
                dev_dest.parent.mkdir(parents=True, exist_ok=True)
                if dev_dest.exists():
                    logger.info(
                        "Deleting existing simulated dev executable: %s",
                        dev_dest,
                    )
                    dev_dest.unlink()
                os.rename(temp_dest, dev_dest)
                logger.info(
                    "Development update simulation complete. Saved to %s",
                    dev_dest,
                )
                messagebox.showinfo(
                    "Atualização (Desenvolvimento)",
                    f"Modo de desenvolvimento detectado!\n\n"
                    f"O download foi realizado com sucesso.\n"
                    f"O executável simulado foi salvo em:\n{dev_dest}\n\n"
                    f"A atualização real de sys.executable não foi realizada "
                    f"para evitar danificar o interpretador python.",
                    parent=self.parent,
                )
                self.win.destroy()
                return

            current_exe = self.dest_path
            old_exe = current_exe.with_suffix(".exe.old")

            logger.info(
                "Finalizing update in FROZEN mode. Target current executable: %s",
                current_exe,
            )

            # Rename current running executable first
            if old_exe.exists():
                try:
                    logger.info(
                        "Removing existing old backup file: %s",
                        old_exe,
                    )
                    old_exe.unlink()
                except Exception as unlink_err:
                    import time

                    old_exe = current_exe.with_name(f"Z7_OfficeLetters.exe.old.{int(time.time())}")
                    logger.warning(
                        "Failed to remove %s: %s. Using alternate old backup path: %s",
                        current_exe.with_suffix(".exe.old"),
                        unlink_err,
                        old_exe,
                    )

            logger.info(
                "Backing up current running executable: %s -> %s",
                current_exe,
                old_exe,
            )
            os.rename(current_exe, old_exe)
            logger.info(
                "Installing newly downloaded executable: %s -> %s",
                temp_dest,
                current_exe,
            )
            try:
                os.rename(temp_dest, current_exe)
            except Exception as rename_exc:
                logger.error(
                    "Failed to rename temp download to current exe. Restoring backup...",
                    exc_info=True,
                )
                try:
                    os.rename(old_exe, current_exe)
                    logger.info("Backup restored successfully.")
                except Exception as restore_exc:
                    logger.critical(
                        "CRITICAL: Failed to restore backup executable: %s",
                        restore_exc,
                        exc_info=True,
                    )
                raise rename_exc

            # Persist the new version in a file next to the executable so that
            # _read_version() picks it up immediately on the next launch, even
            # if the bundled PKG-INFO or hardcoded fallback is stale.
            if self.new_version:
                try:
                    version_file = current_exe.parent / "version.txt"
                    version_file.write_text(self.new_version, encoding="utf-8")
                    logger.info(
                        "Version file written: %s -> %s",
                        version_file,
                        self.new_version,
                    )
                except Exception:
                    logger.warning("Failed to write version.txt after update", exc_info=True)

            messagebox.showinfo(
                "Atualização Concluída",
                "A atualização foi baixada e instalada com sucesso!\n\n"
                "A nova versão estará ativa na próxima inicialização do aplicativo.",
                parent=self.parent,
            )
            self.win.destroy()
        except Exception as exc:
            logger.exception("Failed to install update")
            if temp_dest.exists():
                temp_dest.unlink(missing_ok=True)
            messagebox.showerror(
                "Erro na Instalação",
                f"Erro ao instalar a atualização:\n{exc}",
                parent=self.parent,
            )
            self.win.destroy()

    def _handle_error(self, exc: Exception) -> None:
        messagebox.showerror(
            "Erro no Download",
            f"Não foi possível baixar a atualização:\n{exc}",
            parent=self.parent,
        )
        self.win.destroy()


def run_update_check(
    parent: tk.Tk | tk.Toplevel,
    current_version: str,
    on_startup: bool = False,
    status_callback: Callable[[str], None] | None = None,
) -> None:
    """Check for updates on GitHub and launch download if accepted by the user.

    Args:
        parent: The parent Tkinter/CustomTkinter window.
        current_version: The current version of the application.
        on_startup: If True, do not show messages for "up to date" or network errors.
        status_callback: A callback to report status updates to.
    """

    def do_check() -> None:
        if status_callback:
            status_callback("checking")
        logger.info(
            "Starting update check (on_startup=%s, current_version=%s)...",
            on_startup,
            current_version,
        )
        try:
            tag_name, download_url = obter_ultima_versao()

            if not tag_name or not download_url:
                logger.warning("Latest release tag or download URL is missing. Skipping update.")
                if status_callback:
                    status_callback("up_to_date")
                if not on_startup:
                    parent.after(
                        0,
                        lambda: messagebox.showinfo(
                            "Atualização", "Você já está na versão mais recente.", parent=parent
                        ),
                    )
                return

            versao_limpa = tag_name.lstrip("vV")

            if not comparar_versoes(versao_limpa, current_version):
                logger.info(
                    "Current version %s is up-to-date or newer than latest version %s. Skipping update.",
                    current_version,
                    tag_name,
                )
                if status_callback:
                    status_callback("up_to_date")
                if not on_startup:
                    parent.after(
                        0,
                        lambda: messagebox.showinfo(
                            "Atualização",
                            "Você já está na versão estável mais recente do aplicativo.",
                            parent=parent,
                        ),
                    )
                return

            # New version found!
            logger.info(
                "New update found! Version: %s (current: %s).",
                tag_name,
                current_version,
            )

            dest_path = _get_target_path()
            if not check_write_permission(dest_path):
                logger.warning(
                    "Write permission denied in installation directory: %s. Cannot install update.",
                    dest_path.parent,
                )
                if status_callback:
                    status_callback("error")
                if not on_startup:
                    parent.after(
                        0,
                        lambda: messagebox.showwarning(
                            "Permissão Negada",
                            f"Uma nova versão ({tag_name}) está disponível, mas o aplicativo não possui "
                            f"permissão de gravação no diretório de instalação:\n{dest_path.parent}\n\n"
                            f"Por favor, execute o aplicativo como administrador para atualizar.",
                            parent=parent,
                        ),
                    )
                return

            if status_callback:
                status_callback("update_available")

            def ask_user() -> None:
                msg = (
                    f"Uma nova atualização estável está disponível!\n\n"
                    f"Versão: {tag_name}\n\n"
                    f"Deseja realizar o download e atualizar agora?"
                )
                logger.info(
                    "Prompting user for update acceptance: version=%s",
                    tag_name,
                )
                if messagebox.askyesno("Atualização Disponível", msg, parent=parent):
                    logger.info("User accepted the update. Spawning UpdateProgressWindow...")
                    UpdateProgressWindow(parent, download_url, dest_path, new_version=versao_limpa)
                else:
                    logger.info("User declined the update prompt.")

            if not on_startup:
                parent.after(0, ask_user)

        except Exception as exc:
            # Check if this is a common network error to avoid tracebacks in logs when offline.
            is_network_err = False
            if isinstance(exc, urllib.error.URLError):
                is_network_err = True
            elif isinstance(exc, (TimeoutError, ConnectionError)):
                is_network_err = True
            elif hasattr(exc, "reason") and ("getaddrinfo failed" in str(exc) or "timed out" in str(exc)):
                is_network_err = True

            if is_network_err:
                logger.warning(
                    "Failed to check for updates (network offline/timeout): %s",
                    exc,
                )
            else:
                logger.exception("Failed to check for updates due to unexpected error")

            if status_callback:
                status_callback("error")
            if not on_startup:
                parent.after(
                    0,
                    lambda e=exc: messagebox.showerror(
                        "Erro de Verificação",
                        f"Erro ao verificar atualizações:\n{e}",
                        parent=parent,
                    ),
                )

    threading.Thread(target=do_check, daemon=True).start()
