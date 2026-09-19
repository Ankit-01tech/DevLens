#!/usr/bin/env python3
"""Reproducibility verification tool for DevLens build artifacts.

Demonstrates that building DevLens into a standalone executable archive (.pyz)
produces 100% byte-identical SHA-256 build artifacts when timestamp metadata
is normalized (standard practice in reproducible build pipelines).

Usage:
    python tools/reproducible_build.py
"""

from __future__ import annotations

import hashlib
import os
import sys
import zipfile
from pathlib import Path

# Fixed epoch timestamp for deterministic zip entry timestamps (2026-01-01 00:00:00)
FIXED_ZIP_DATE = (2026, 1, 1, 0, 0, 0)
PERM_MODE = 0o644 << 16


def collect_source_files(root: Path) -> list[tuple[Path, str]]:
    """Collect all DevLens source files with deterministic relative archive paths."""
    files: list[tuple[Path, str]] = []

    devlens_py = root / "devlens.py"
    if devlens_py.exists():
        files.append((devlens_py, "__main__.py"))

    devlens_dir = root / "devlens"
    if devlens_dir.is_dir():
        for p in sorted(devlens_dir.rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            arcname = f"devlens/{p.relative_to(devlens_dir)}"
            files.append((p, arcname))

    files.sort(key=lambda item: item[1])
    return files


SHEBANG = b"#!/usr/bin/env python3\n"


def create_reproducible_artifact(source_root: Path, output_file: Path) -> str:
    """Build a standalone executable zipapp archive with normalized timestamps and compute SHA-256."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    if output_file.exists():
        output_file.unlink()

    files = collect_source_files(source_root)

    with open(output_file, "wb") as f:
        f.write(SHEBANG)
        with zipfile.ZipFile(f, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for src_path, arcname in files:
                content = src_path.read_bytes()
                zinfo = zipfile.ZipInfo(filename=arcname, date_time=FIXED_ZIP_DATE)
                zinfo.external_attr = PERM_MODE
                zinfo.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(zinfo, content)

    os.chmod(output_file, 0o755)

    hasher = hashlib.sha256()
    hasher.update(output_file.read_bytes())
    return hasher.hexdigest()


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    dist_dir = root / "dist"
    dist_dir.mkdir(exist_ok=True)

    artifact_a = dist_dir / "devlens_a.pyz"
    artifact_b = dist_dir / "devlens_b.pyz"

    print("=" * 60)
    print("DEV LENS REPRODUCIBLE BUILD VERIFICATION")
    print("=" * 60)
    print()

    print(f"Building Artifact A ({artifact_a.relative_to(root)})...")
    hash_a = create_reproducible_artifact(root, artifact_a)
    print(f"SHA-256: {hash_a}")
    print()

    print(f"Building Artifact B ({artifact_b.relative_to(root)})...")
    hash_b = create_reproducible_artifact(root, artifact_b)
    print(f"SHA-256: {hash_b}")
    print()

    identical = hash_a == hash_b
    print(f"Byte identical: {'YES' if identical else 'NO'}")
    print()

    if identical:
        print("RESULT: PASS")
        print("Build artifact byte-level reproducibility confirmed.")
        print("=" * 60)
        return 0

    print("RESULT: FAIL")
    print("Artifact hashes differ.")
    print("=" * 60)
    return 1


if __name__ == "__main__":
    sys.exit(main())
