"""Small, dependency-free helper utilities shared across DevLens modules."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Iterable, Optional

from .constants import HASH_CHUNK_SIZE, KNOWN_BINARY_EXTENSIONS


def is_probably_binary(path: Path, sniff_bytes: int = 8192) -> bool:
    """Heuristically decide whether a file is binary.

    Uses extension short-circuits first (cheap), then falls back to
    sniffing the first few KB for NUL bytes, which is a standard and
    reliable binary-detection heuristic (the same one Git itself uses).
    """
    if path.suffix.lower() in KNOWN_BINARY_EXTENSIONS:
        return True
    try:
        with open(path, "rb") as fh:
            chunk = fh.read(sniff_bytes)
    except OSError:
        return True
    if b"\x00" in chunk:
        return True
    return False


def safe_read_text(path: Path, max_bytes: Optional[int] = None) -> Optional[str]:
    """Read a file as text, tolerating encoding issues and I/O errors.

    Returns None if the file cannot be read at all. Malformed UTF-8 is
    handled with 'replace' so a single bad byte never crashes a scan.
    """
    try:
        with open(path, "rb") as fh:
            data = fh.read(max_bytes) if max_bytes else fh.read()
        return data.decode("utf-8", errors="replace")
    except OSError:
        return None


def hash_file(path: Path, max_bytes: Optional[int] = None) -> Optional[str]:
    """Compute a streaming SHA-256 hash of a file without loading it fully."""
    hasher = hashlib.sha256()
    read_total = 0
    try:
        with open(path, "rb") as fh:
            while True:
                remaining = None
                if max_bytes is not None:
                    remaining = max_bytes - read_total
                    if remaining <= 0:
                        break
                to_read = HASH_CHUNK_SIZE if remaining is None else min(HASH_CHUNK_SIZE, remaining)
                chunk = fh.read(to_read)
                if not chunk:
                    break
                hasher.update(chunk)
                read_total += len(chunk)
    except OSError:
        return None
    return hasher.hexdigest()


def iter_lines(text: str) -> Iterable[str]:
    """Split text into lines without keeping line-ending characters."""
    return text.splitlines()


def human_size(num_bytes: int) -> str:
    """Format a byte count as a short human-readable string."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f}{unit}" if unit != "B" else f"{int(size)}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def shannon_entropy(s: str) -> float:
    """Compute the Shannon entropy (bits/char) of a string.

    Used by the secret scanner to flag high-entropy tokens that look
    like generated keys/secrets rather than ordinary words.
    """
    if not s:
        return 0.0
    from collections import Counter
    from math import log2

    counts = Counter(s)
    length = len(s)
    return -sum((c / length) * log2(c / length) for c in counts.values())


def redact(value: str, keep_prefix: int = 4) -> str:
    """Redact a secret-like value, keeping only a short, safe prefix."""
    if len(value) <= keep_prefix:
        return "*" * len(value)
    return value[:keep_prefix] + "*" * min(16, max(4, len(value) - keep_prefix))


def stable_hash_int(value: str, modulo: int = 1000) -> int:
    """Compute a process-deterministic integer hash modulo `modulo`.

    Uses SHA-256 instead of Python's built-in `hash()`, avoiding
    `PYTHONHASHSEED` process randomization and ensuring finding IDs
    remain identical across separate process runs.
    """
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % modulo

