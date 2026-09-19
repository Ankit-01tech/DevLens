"""Detects which software ecosystems a project appears to use.

Detection uses root-level manifest markers, nested project configuration files,
and source file extension statistics to identify project technologies.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Set

from .constants import PROJECT_TYPE_MARKERS
from .models import FileRecord

NESTED_MARKER_MAP = {
    "tsconfig.json": "TypeScript",
    "package.json": "Node.js",
    "requirements.txt": "Python",
    "pyproject.toml": "Python",
    "setup.py": "Python",
    "setup.cfg": "Python",
    "Pipfile": "Python",
    "Cargo.toml": "Rust",
    "go.mod": "Go",
    "pom.xml": "Java (Maven)",
    "build.gradle": "Java (Gradle)",
    "build.gradle.kts": "Java (Gradle)",
    "CMakeLists.txt": "C/C++",
    "Makefile": "C/C++",
}


def detect_technologies(root: Path, files: Optional[List[FileRecord]] = None) -> List[str]:
    found: List[str] = []
    seen: Set[str] = set()

    def add_tech(tech: str):
        if tech not in seen:
            seen.add(tech)
            found.append(tech)

    # Priority A: Check root-level manifest markers directly
    for tech, markers in PROJECT_TYPE_MARKERS.items():
        for marker in markers:
            if (root / marker).exists():
                add_tech(tech)
                break

    # Priority B & C: Check nested manifest markers and extension distribution
    if files:
        ext_counts: dict[str, int] = {}
        for f in files:
            path_obj = Path(f.path)
            file_name = path_obj.name.lower()
            ext = f.extension.lower()

            if not f.is_binary:
                ext_counts[ext] = ext_counts.get(ext, 0) + 1

            for marker_file, tech in NESTED_MARKER_MAP.items():
                if file_name == marker_file.lower():
                    add_tech(tech)

        if ext_counts.get(".ts", 0) + ext_counts.get(".tsx", 0) >= 2:
            add_tech("TypeScript")
        if ext_counts.get(".py", 0) >= 2:
            add_tech("Python")
        if ext_counts.get(".js", 0) + ext_counts.get(".jsx", 0) >= 2:
            if "TypeScript" not in seen and "Node.js" not in seen:
                add_tech("JavaScript")
        if ext_counts.get(".go", 0) >= 2:
            add_tech("Go")
        if ext_counts.get(".rs", 0) >= 2:
            add_tech("Rust")
        if ext_counts.get(".java", 0) >= 2:
            add_tech("Java")
        if ext_counts.get(".c", 0) + ext_counts.get(".cpp", 0) + ext_counts.get(".h", 0) >= 2:
            add_tech("C/C++")
    else:
        try:
            for item in root.rglob("*"):
                if any(part.startswith(".") or part in ("node_modules", "__pycache__", "venv") for part in item.parts):
                    continue
                name_lower = item.name.lower()
                for marker_file, tech in NESTED_MARKER_MAP.items():
                    if name_lower == marker_file.lower():
                        add_tech(tech)
        except OSError:
            pass

    if not found:
        found.append("Unknown / Generic")
    return found
