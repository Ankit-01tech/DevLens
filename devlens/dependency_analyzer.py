"""Static dependency-manifest analysis, without any third-party parsers.

This module intentionally implements small, targeted parsers instead of
pulling in `toml`, `PyYAML`, or XML dependency libraries. Each parser is
deliberately conservative: if a manifest cannot be safely parsed, DevLens
reports that fact rather than guessing.

DevLens performs *static, local* inspection only. It does not query any
vulnerability database and does not claim to detect CVEs.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Optional

from .models import DependencyInfo

_PY_REQ_LINE = re.compile(
    r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*(==|>=|<=|~=|!=|>|<)?\s*([^\s#;]*)"
)


def analyze(root: Path) -> List[DependencyInfo]:
    results: List[DependencyInfo] = []

    req_txt = root / "requirements.txt"
    if req_txt.exists():
        results.append(_parse_requirements_txt(req_txt))

    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        info = _parse_pyproject(pyproject)
        if info:
            results.append(info)

    pkg_json = root / "package.json"
    if pkg_json.exists():
        results.append(_parse_package_json(pkg_json, root))

    cargo = root / "Cargo.toml"
    if cargo.exists():
        results.append(_parse_cargo_toml(cargo, root))

    go_mod = root / "go.mod"
    if go_mod.exists():
        results.append(_parse_go_mod(go_mod, root))

    pom = root / "pom.xml"
    if pom.exists():
        results.append(_parse_pom_xml(pom))

    return results


def _parse_requirements_txt(path: Path) -> DependencyInfo:
    deps: List[str] = []
    pinned_count = 0
    seen = {}
    duplicates = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return DependencyInfo(ecosystem="python", manifest_file="requirements.txt")

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        match = _PY_REQ_LINE.match(line)
        if not match:
            continue
        name, _extras, operator, version = match.groups()
        name_norm = name.lower()
        if name_norm in seen:
            duplicates.append(name)
        seen[name_norm] = True
        deps.append(name)
        if operator == "==" and version:
            pinned_count += 1

    pinned = bool(deps) and pinned_count == len(deps)
    return DependencyInfo(
        ecosystem="python",
        manifest_file="requirements.txt",
        runtime_dependencies=deps,
        pinned=pinned,
        lockfile_present=False,
        duplicate_declarations=duplicates,
    )


def _parse_pyproject(path: Path) -> Optional[DependencyInfo]:
    """Extract dependency lists from pyproject.toml using targeted regex.

    A full TOML parser is unnecessary here: we only need the
    `dependencies = [...]` array under `[project]` and, optionally,
    `[project.optional-dependencies]`. This keeps the implementation
    honest about what it can and cannot parse.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    deps = _extract_toml_array(text, r"^\s*dependencies\s*=\s*\[")
    dev_deps: List[str] = []
    for section_re in (
        r"\[project\.optional-dependencies\.dev\]",
        r"\[tool\.poetry\.dev-dependencies\]",
        r"\[tool\.poetry\.group\.dev\.dependencies\]",
    ):
        m = re.search(section_re, text)
        if m:
            # Grab everything until the next section header.
            rest = text[m.end():]
            next_section = re.search(r"^\[", rest, re.MULTILINE)
            block = rest[: next_section.start()] if next_section else rest
            for line in block.splitlines():
                line = line.strip()
                dep_match = re.match(r'^"?([A-Za-z0-9._-]+)"?\s*=', line)
                if dep_match:
                    dev_deps.append(dep_match.group(1))

    names = [_strip_version_spec(d) for d in deps]
    pinned = bool(deps) and all("==" in d for d in deps)
    lockfile = (path.parent / "poetry.lock").exists() or (path.parent / "uv.lock").exists()

    return DependencyInfo(
        ecosystem="python",
        manifest_file="pyproject.toml",
        runtime_dependencies=names,
        dev_dependencies=dev_deps,
        pinned=pinned,
        lockfile_present=lockfile,
    )


def _extract_toml_array(text: str, header_pattern: str) -> List[str]:
    match = re.search(header_pattern, text, re.MULTILINE)
    if not match:
        return []
    start = match.end()
    end = text.find("]", start)
    if end == -1:
        return []
    body = text[start:end]
    items = re.findall(r'"([^"]+)"', body)
    return items


def _strip_version_spec(dep_string: str) -> str:
    return re.split(r"[<>=!~\[\s]", dep_string, maxsplit=1)[0]


def _parse_package_json(path: Path, root: Path) -> DependencyInfo:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return DependencyInfo(ecosystem="node", manifest_file="package.json")

    runtime = list((data.get("dependencies") or {}).keys())
    dev = list((data.get("devDependencies") or {}).keys())
    versions = {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})}
    pinned = bool(versions) and all(
        not str(v).startswith(("^", "~", ">", "<", "*")) for v in versions.values()
    )
    lockfile = (root / "package-lock.json").exists() or (root / "yarn.lock").exists() or (root / "pnpm-lock.yaml").exists()

    return DependencyInfo(
        ecosystem="node",
        manifest_file="package.json",
        runtime_dependencies=runtime,
        dev_dependencies=dev,
        pinned=pinned,
        lockfile_present=lockfile,
    )


def _parse_cargo_toml(path: Path, root: Path) -> DependencyInfo:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return DependencyInfo(ecosystem="rust", manifest_file="Cargo.toml")

    deps = _extract_toml_table_keys(text, r"^\[dependencies\]")
    dev_deps = _extract_toml_table_keys(text, r"^\[dev-dependencies\]")
    lockfile = (root / "Cargo.lock").exists()

    return DependencyInfo(
        ecosystem="rust",
        manifest_file="Cargo.toml",
        runtime_dependencies=deps,
        dev_dependencies=dev_deps,
        pinned=False,
        lockfile_present=lockfile,
    )


def _extract_toml_table_keys(text: str, header_pattern: str) -> List[str]:
    match = re.search(header_pattern, text, re.MULTILINE)
    if not match:
        return []
    rest = text[match.end():]
    next_section = re.search(r"^\[", rest, re.MULTILINE)
    block = rest[: next_section.start()] if next_section else rest
    keys = []
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key_match = re.match(r'^"?([A-Za-z0-9._-]+)"?\s*=', line)
        if key_match:
            keys.append(key_match.group(1))
    return keys


def _parse_go_mod(path: Path, root: Path) -> DependencyInfo:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return DependencyInfo(ecosystem="go", manifest_file="go.mod")

    deps = []
    in_require_block = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("require ("):
            in_require_block = True
            continue
        if in_require_block:
            if stripped == ")":
                in_require_block = False
                continue
            parts = stripped.split()
            if parts:
                deps.append(parts[0])
        elif stripped.startswith("require "):
            parts = stripped.split()
            if len(parts) >= 2:
                deps.append(parts[1])

    lockfile = (root / "go.sum").exists()
    return DependencyInfo(
        ecosystem="go",
        manifest_file="go.mod",
        runtime_dependencies=deps,
        pinned=True,  # go.mod always pins to a specific module version
        lockfile_present=lockfile,
    )


def _parse_pom_xml(path: Path) -> DependencyInfo:
    """Extract basic <dependency> groupId/artifactId pairs via regex.

    A full XML parser (xml.etree) is standard library and would also be
    acceptable here; regex is used for a lightweight, tolerant pass that
    won't fail on minor malformed XML.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return DependencyInfo(ecosystem="java", manifest_file="pom.xml")

    deps = []
    for dep_block in re.findall(r"<dependency>(.*?)</dependency>", text, re.DOTALL):
        group = re.search(r"<groupId>(.*?)</groupId>", dep_block)
        artifact = re.search(r"<artifactId>(.*?)</artifactId>", dep_block)
        if group and artifact:
            deps.append(f"{group.group(1).strip()}:{artifact.group(1).strip()}")

    return DependencyInfo(
        ecosystem="java",
        manifest_file="pom.xml",
        runtime_dependencies=deps,
    )
