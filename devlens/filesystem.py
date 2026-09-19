"""Recursive, safe filesystem discovery for DevLens.

Design goals:
* Never crash on permission errors, broken symlinks, or unreadable files.
* Never follow symlinks that could create infinite loops.
* Be configurable (ignored directories, max file size).
* Stream large files rather than loading them fully into memory.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set

from .constants import DEFAULT_IGNORED_DIRS, DEFAULT_MAX_FILE_SIZE_MB, SOURCE_EXTENSIONS
from .models import FileRecord
from .utils import is_probably_binary


@dataclass
class ScanConfig:
    root: Path
    ignored_dirs: Set[str] = field(default_factory=lambda: set(DEFAULT_IGNORED_DIRS))
    max_file_size_mb: float = DEFAULT_MAX_FILE_SIZE_MB
    include_hidden: bool = True

    @property
    def max_file_size_bytes(self) -> int:
        return int(self.max_file_size_mb * 1024 * 1024)


class FilesystemScanner:
    """Walks a project directory and produces FileRecord entries."""

    def __init__(self, config: ScanConfig):
        self.config = config
        self.errors: List[str] = []
        self._visited_real_dirs: Set[str] = set()

    def discover(self) -> List[FileRecord]:
        records: List[FileRecord] = []
        root = self.config.root.resolve()
        for file_path in self._walk(root):
            records.append(self._build_record(file_path, root))
        # Deterministic ordering makes reports reproducible.
        records.sort(key=lambda r: r.path)
        return records

    def _walk(self, root: Path):
        for dirpath, dirnames, filenames in os.walk(root, topdown=True, onerror=self._on_walk_error):
            current = Path(dirpath)

            # Guard against symlink loops: track resolved directory identity.
            try:
                real = os.path.realpath(dirpath)
            except OSError:
                real = dirpath
            if real in self._visited_real_dirs:
                dirnames[:] = []
                continue
            self._visited_real_dirs.add(real)

            # Filter ignored / hidden directories in-place (affects os.walk traversal).
            filtered = []
            for d in dirnames:
                if d in self.config.ignored_dirs:
                    continue
                if not self.config.include_hidden and d.startswith("."):
                    continue
                if d == ".git":
                    continue
                # Don't descend into symlinked directories to avoid loops.
                full = current / d
                if full.is_symlink():
                    continue
                filtered.append(d)
            dirnames[:] = filtered

            for name in filenames:
                if not self.config.include_hidden and name.startswith("."):
                    continue
                yield current / name

    def _on_walk_error(self, err: OSError) -> None:
        self.errors.append(f"Permission or I/O error: {err.filename or err}")

    def _build_record(self, path: Path, root: Path) -> FileRecord:
        rel = self._relative(path, root)
        try:
            if path.is_symlink() and not path.exists():
                return FileRecord(
                    path=rel, size=0, extension=path.suffix.lower(),
                    is_binary=False, is_source=False, unreadable=True,
                    error="broken symlink",
                )
            stat = path.stat()
        except OSError as exc:
            return FileRecord(
                path=rel, size=0, extension=path.suffix.lower(),
                is_binary=False, is_source=False, unreadable=True, error=str(exc),
            )

        size = stat.st_size
        ext = path.suffix.lower()
        binary = True
        if size <= self.config.max_file_size_bytes:
            try:
                binary = is_probably_binary(path)
            except OSError:
                binary = True
        is_source = (not binary) and ext in SOURCE_EXTENSIONS

        return FileRecord(
            path=rel,
            size=size,
            extension=ext,
            is_binary=binary,
            is_source=is_source,
        )

    @staticmethod
    def _relative(path: Path, root: Path) -> str:
        try:
            return str(path.relative_to(root))
        except ValueError:
            return str(path)
