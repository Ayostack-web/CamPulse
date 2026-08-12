from __future__ import annotations

import shutil
import subprocess
from contextlib import suppress
from pathlib import Path
from tempfile import NamedTemporaryFile


def is_ghostscript_available() -> bool:
    """Return True if the Ghostscript `gs` binary is installed and callable."""
    return shutil.which("gs") is not None


def compress_pdf_ghostscript(
    input_path: str | Path,
    output_path: str | Path,
    preset: str = "/ebook",
    timeout: int = 120,
) -> Path | None:
    """
    Compress a PDF using Ghostscript.

    Uses the ``/ebook`` preset (150 dpi) for a good balance of size and
    readability. Returns the compressed output path on success, or ``None``
    when the input is not a PDF, Ghostscript is unavailable, or compression
    fails (so callers can fall back to the original file).
    """
    source = Path(input_path)
    if source.suffix.lower() != ".pdf" or not is_ghostscript_available():
        return None

    target = Path(output_path)
    command = [
        "gs",
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS={preset}",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        "-dDetectDuplicateImages=true",
        f"-sOutputFile={target}",
        str(source),
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (subprocess.SubprocessError, OSError):
        return None

    if result.returncode != 0 or not target.exists() or target.stat().st_size == 0:
        return None

    return target


def compress_pdf_bytes(
    data: bytes,
    filename: str,
    max_bytes: int = 4 * 1024 * 1024,
    timeout: int = 20,
) -> bytes:
    """Best-effort in-memory PDF compression via Ghostscript.

    Strictly optional: it must never block or fail a caller. Files that are
    not PDFs, larger than ``max_bytes``, or that fail to compress are returned
    unchanged so callers always get back storable bytes.
    """
    if not str(filename).lower().endswith(".pdf") or len(data) == 0:
        return data
    if len(data) > max_bytes:
        return data

    source_path: Path | None = None
    target_path: Path | None = None
    try:
        with NamedTemporaryFile(delete=False, suffix=".pdf") as source_file:
            source_file.write(data)
            source_path = Path(source_file.name)

        target_path = source_path.with_name(f"{source_path.stem}_compressed.pdf")
        compressed = compress_pdf_ghostscript(source_path, target_path, timeout=timeout)
        if compressed is not None and compressed.stat().st_size < len(data):
            return compressed.read_bytes()
        return data
    except Exception:
        return data
    finally:
        with suppress(OSError):
            if source_path is not None:
                source_path.unlink(missing_ok=True)
            if target_path is not None:
                target_path.unlink(missing_ok=True)
