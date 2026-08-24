"""Streamed upload handling.

Reads UploadFile bodies in fixed-size chunks so a 50MB PDF never sits whole
in the event-loop's RAM. The bytes spill into a SpooledTemporaryFile that
stays in memory only while small, and the SHA-256 digest is computed during
the copy so dedup needs no second pass over the data.
"""
from __future__ import annotations

import hashlib
import tempfile
from typing import BinaryIO

CHUNK_SIZE = 1024 * 1024


def _absorb_chunk(spool: BinaryIO, hasher, chunk: bytes) -> None:
    hasher.update(chunk)
    spool.write(chunk)


async def stream_async_upload_to_spool(
    file,
    max_bytes: int,
    chunk_size: int = CHUNK_SIZE,
) -> tuple[BinaryIO, int, str]:
    """Copy an async ``UploadFile`` into a spooled temp file.

    Returns ``(spooled_file, byte_count, sha256_hex)`` positioned at offset 0.
    Raises ``ValueError`` when the payload exceeds ``max_bytes`` (checked per
    chunk, so oversized uploads are rejected early instead of buffered first).
    """
    import anyio

    spool: tempfile.SpooledTemporaryFile = tempfile.SpooledTemporaryFile(max_size=CHUNK_SIZE)
    hasher = hashlib.sha256()
    total = 0
    try:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                spool.close()
                raise ValueError(f"payload exceeds {max_bytes} bytes")
            # write/hash are CPU+disk bound; run off the event loop so big
            # copies don't stall other requests.
            await anyio.to_thread.run_sync(_absorb_chunk, spool, hasher, chunk)
        spool.seek(0)
        return spool, total, hasher.hexdigest()
    except Exception:
        if not spool.closed:
            spool.close()
        raise


def read_spool(spool: BinaryIO) -> bytes:
    """Return the spool's full contents (caller caps size beforehand)."""
    position = spool.tell()
    spool.seek(0)
    data = spool.read()
    spool.seek(position)
    return data


def replace_spooled_contents(spool: BinaryIO, data: bytes) -> None:
    """Atomically swap the spool's contents (e.g. post-compression)."""
    spool.seek(0)
    spool.truncate()
    spool.write(data)
    spool.seek(0)

