"""CLI test script to run the processing pipeline without the GUI.

Usage:
    python scripts/run_cli.py

This script runs the same processing pipeline as the GUI but outputs
results to the console, useful for testing and iteration.
"""

from __future__ import annotations

import io
import queue
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

# Fix encoding for Windows console
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add src to path
_root = Path(__file__).parent.parent
_src = _root / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from z7_officeletters.constants import (
    BASE_DIR,
    PASTA_SAIDA,
    PASTA_PLANILHA,
    PASTA_ENVELOPES,
    PASTA_PROPOSITURAS_FONTE,
)
from z7_officeletters.core.api_key import carregar_api_key, carregar_modelo_ia, carregar_modelo_fallback
from z7_officeletters.core.logging_setup import configurar_logging


def run_cli() -> None:
    """Run the processing pipeline from the command line."""
    # Configure logging
    configurar_logging()

    # Load API key
    api_key = carregar_api_key()
    if not api_key:
        print("ERROR: No API key found. Please set one via the GUI first.")
        sys.exit(1)

    modelo = carregar_modelo_ia()
    modelo_fallback = carregar_modelo_fallback()

    print(f"Model: {modelo}")
    print(f"Fallback: {modelo_fallback}")

    # Clean previous output
    for folder in [PASTA_SAIDA, PASTA_PLANILHA, PASTA_ENVELOPES, PASTA_PROPOSITURAS_FONTE]:
        p = Path(folder)
        if p.exists():
            import shutil
            shutil.rmtree(p)
            print(f"Cleaned: {folder}")

    # Find propositura files
    proposituras_dir = BASE_DIR / "proposituras"
    arquivos = sorted(proposituras_dir.glob("*"))
    arquivos = [str(f) for f in arquivos if f.suffix.lower() in {".txt", ".docx", ".pdf", ".odt"}]

    if not arquivos:
        print(f"ERROR: No propositura files found in {proposituras_dir}")
        sys.exit(1)

    print(f"Found {len(arquivos)} propositura file(s)")

    # Build inputs
    data = datetime(2026, 8, 19)
    inputs = {
        "num_inicial": 471,
        "sigla": "cms",
        "data_extenso": "19 de agosto de 2026",
        "data_iso": "2026-08-19",
        "arquivos": arquivos,
        "api_key": api_key,
        "modelo": modelo,
        "modelo_fallback": modelo_fallback,
    }

    # Create queue and cancel event
    q: queue.Queue = queue.Queue()
    cancel_event = threading.Event()

    # Import and run the worker
    from z7_officeletters.gui.workers.processor import run_processing_worker

    print("\nStarting processing...")
    start_time = time.time()

    # Run in background thread
    thread = run_processing_worker(inputs, q, cancel_event)

    # Monitor queue
    while thread.is_alive() or not q.empty():
        try:
            msg = q.get(timeout=0.5)
            tag = msg[0]
            if tag == "log":
                text = msg[1]
                print(text)
            elif tag == "progress":
                current, total = msg[1], msg[2]
                if total > 0:
                    print(f"  Progress: {current}/{total}", end="\r")
            elif tag == "done":
                generated, errors, elapsed_s, tokens = msg[1], msg[2], msg[3], msg[4]
                print(f"\n\n{'='*60}")
                print(f"Results: {generated} ofícios generated, {errors} errors")
                print(f"Time: {elapsed_s:.1f}s")
                if tokens:
                    print(f"Tokens: {tokens:,}")
                print(f"{'='*60}")
            elif tag == "error":
                print(f"\nFATAL ERROR: {msg[1]}")
            elif tag == "cancelled":
                print(f"\nCancelled after {msg[1]}/{msg[2]} {msg[3]}")
        except queue.Empty:
            continue

    elapsed = time.time() - start_time
    print(f"\nTotal time: {elapsed:.1f}s")


if __name__ == "__main__":
    run_cli()