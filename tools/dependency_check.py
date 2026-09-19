#!/usr/bin/env python3
"""Dependency audit tool for DevLens.

Scans every Python source file inside the project (excluding this tool
itself and any virtual environments) and reports which top-level
modules are imported. Cross-references those against Python's known
standard-library module set to prove that DevLens has zero third-party
runtime dependencies.

This tool is deliberately CONSERVATIVE: any import it cannot confidently
classify as standard library is reported under "needs manual review"
rather than silently passed. A conservative false positive (flagging a
stdlib module we don't recognize) is preferable to a false negative
(missing a real third-party dependency).

Usage:
    python tools/dependency_check.py [project_root]
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Set

# Directories that should never be scanned when auditing DevLens itself.
EXCLUDED_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", "examples"}

# Local package/module names that are part of DevLens itself, not
# third-party dependencies. Anything importing "devlens" or a sibling
# module within the package is first-party code, not a dependency.
FIRST_PARTY_PREFIXES = {"devlens", "tests", "tools"}

# A short list of stdlib modules that, on some Python builds, are not
# present in sys.stdlib_module_names (e.g. very old/new interpreters)
# but are unambiguously part of the standard library.
KNOWN_STDLIB_EXTRA = {
    "distutils", "typing_extensions",  # typing_extensions is intentionally
    # NOT treated as stdlib below -- see note in main().
}


def get_stdlib_modules() -> Set[str]:
    """Return the set of standard-library top-level module names.

    Uses sys.stdlib_module_names (Python 3.10+), which is the most
    authoritative, dependency-free source of truth available. Falls
    back to sys.builtin_module_names on older interpreters.
    """
    modules = set()
    if hasattr(sys, "stdlib_module_names"):
        modules |= set(sys.stdlib_module_names)
    modules |= set(sys.builtin_module_names)
    return modules


def find_python_files(root: Path) -> list[Path]:
    files = []
    for path in root.rglob("*.py"):
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        files.append(path)
    return files


def extract_top_level_imports(path: Path) -> Set[str]:
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError):
        return set()

    imports: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                # Relative import (e.g. "from . import x") -- always first-party.
                continue
            if node.module:
                imports.add(node.module.split(".")[0])
    return imports


def main() -> int:
    project_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
    project_root = project_root.resolve()

    stdlib_modules = get_stdlib_modules()
    py_files = find_python_files(project_root)

    all_imports: Set[str] = set()
    for f in py_files:
        all_imports |= extract_top_level_imports(f)

    first_party = {m for m in all_imports if m in FIRST_PARTY_PREFIXES}
    stdlib_used = {m for m in all_imports if m in stdlib_modules}
    unknown = all_imports - first_party - stdlib_used

    # "typing_extensions" is a real PyPI backport package, not stdlib,
    # even though its name suggests otherwise -- flag it explicitly if seen.
    third_party_confirmed = set()
    needs_review = set()
    for mod in sorted(unknown):
        if mod in ("typing_extensions",):
            third_party_confirmed.add(mod)
        else:
            needs_review.add(mod)

    print("=" * 60)
    print("DEV LENS DEPENDENCY AUDIT")
    print("=" * 60)
    print()
    print(f"Project root: {project_root}")
    print(f"Python files scanned: {len(py_files)}")
    print()
    print(f"Standard-library imports found: {len(stdlib_used)}")
    for mod in sorted(stdlib_used):
        print(f"  - {mod}")
    print()
    print(f"First-party (DevLens) imports found: {len(first_party)}")
    for mod in sorted(first_party):
        print(f"  - {mod}")
    print()

    result = "PASS"
    if third_party_confirmed:
        result = "FAIL"
        print(f"Confirmed third-party runtime dependencies: {len(third_party_confirmed)}")
        for mod in sorted(third_party_confirmed):
            print(f"  - {mod}")
        print()

    if needs_review:
        # Conservative: don't declare PASS if anything is unclassified.
        result = "NEEDS REVIEW"
        print(f"Imports needing manual review (not recognized as stdlib): {len(needs_review)}")
        for mod in sorted(needs_review):
            print(f"  - {mod}")
        print()

    print("-" * 60)
    print(f"Third-party runtime dependencies: {len(third_party_confirmed)}")
    print(f"Standard-library imports: {len(stdlib_used)}")
    print()
    print(f"Result: {result}")
    if result == "PASS":
        print("Zero runtime dependencies confirmed.")
    print("=" * 60)

    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
