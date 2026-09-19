#!/usr/bin/env python3
"""DevLens Single — a condensed, single-file variant of DevLens.

This is an OPTIONAL bonus artifact. The primary, fully-featured DevLens
implementation is the modular package (`devlens.py` + `devlens/`); this
file exists to demonstrate that the essential scanning functionality
can also run as a single, dependency-free, copy-anywhere script.

Scope note: to stay genuinely maintainable as a single file, this
variant implements a focused subset of the full tool: file discovery,
secret scanning, Python code statistics, core hygiene checks (README/
LICENSE/.gitignore/tests), and a deterministic health score. It does
NOT include: multi-ecosystem dependency parsing, the HTML dashboard,
CSV export, or git metadata inspection. For the complete feature set,
use `devlens.py`.

Usage:
    python devlens_single.py /path/to/project
    python devlens_single.py /path/to/project --format json
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

VERSION = "2.0.0-single"

IGNORED_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist",
    "build", "target", "coverage", ".next", ".pytest_cache", "vendor",
}
SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".go", ".rs", ".java", ".c", ".cpp", ".rb", ".sh"}
BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".tar", ".gz",
    ".exe", ".dll", ".so", ".pyc", ".db", ".sqlite", ".sqlite3",
}
PLACEHOLDER_TOKENS = {"changeme", "your_api_key", "example", "placeholder", "dummy", "fake", "test", "password"}

SEVERITY_PENALTY = {"CRITICAL": 25, "HIGH": 12, "MEDIUM": 6, "LOW": 2, "INFO": 0}


@dataclass
class Finding:
    id: str
    severity: str
    category: str
    title: str
    path: str = ""
    line: Optional[int] = None
    evidence: str = ""
    explanation: str = ""
    recommendation: str = ""


SECRET_RULES = [
    ("SEC-AWS-KEY", "CRITICAL", re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
     "Possible AWS access key ID", "Rotate this credential immediately."),
    ("SEC-STRIPE-KEY", "HIGH", re.compile(r"\b(sk|pk|rk)_(live|test)_[A-Za-z0-9]{16,}\b"),
     "Possible Stripe API key", "Rotate the key from the Stripe dashboard if live."),
    ("SEC-PRIVATE-KEY", "CRITICAL", re.compile(r"-----BEGIN (RSA|EC|DSA|OPENSSH|PGP) PRIVATE KEY-----"),
     "Private key material detected", "Remove and rotate this private key."),
    ("SEC-DB-CONN", "HIGH",
     re.compile(r"\b(postgres|postgresql|mysql|mongodb(?:\+srv)?)://[^\s\"']+:[^\s\"'@]+@[^\s\"']+"),
     "Database connection string with embedded credentials", "Move credentials out of the connection string."),
    ("SEC-GENERIC-ASSIGN", "MEDIUM",
     re.compile(r"(?i)\b(api[_-]?key|secret[_-]?key|access[_-]?token|password)\b\s*[:=]\s*['\"]([^'\"\s]{8,})['\"]"),
     "Possible hardcoded credential assignment", "Move this value into an environment variable."),
]


def redact(value: str) -> str:
    if len(value) <= 4:
        return "*" * len(value)
    return value[:4] + "*" * min(16, len(value) - 4)


def is_placeholder(value: str) -> bool:
    stripped = value.strip().strip("'\"").lower()
    if stripped in PLACEHOLDER_TOKENS or len(stripped) < 8:
        return True
    if re.fullmatch(r"x{4,}|\*{4,}|0{4,}", stripped):
        return True
    return False


def is_binary(path: Path) -> bool:
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return True
    try:
        with open(path, "rb") as fh:
            chunk = fh.read(8192)
        return b"\x00" in chunk
    except OSError:
        return True


def discover_files(root: Path, max_size_bytes: int) -> List[Path]:
    results = []
    visited_real_dirs = set()
    for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: None):
        current = Path(dirpath)
        try:
            real = os.path.realpath(dirpath)
        except OSError:
            real = dirpath
        if real in visited_real_dirs:
            dirnames[:] = []
            continue
        visited_real_dirs.add(real)

        dirnames[:] = [
            d for d in dirnames
            if d not in IGNORED_DIRS and not (current / d).is_symlink()
        ]
        for name in filenames:
            p = current / name
            try:
                if p.is_symlink() and not p.exists():
                    continue
                if p.stat().st_size > max_size_bytes:
                    continue
            except OSError:
                continue
            results.append(p)
    results.sort()
    return results


def stable_hash_int(value: str, modulo: int = 1000) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % modulo


def scan_secrets(path: Path, rel_path: str) -> List[Finding]:
    findings = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return findings

    for line_no, line in enumerate(text.splitlines(), start=1):
        for rule_id, severity, pattern, title, rec in SECRET_RULES:
            for match in pattern.finditer(line):
                value = match.group(2) if rule_id == "SEC-GENERIC-ASSIGN" else match.group(0)
                if is_placeholder(value):
                    continue
                safe_line = line.replace(value, redact(value)).strip()[:160]
                findings.append(Finding(
                    id=f"{rule_id}-{len(findings) + 1:03d}", severity=severity, category="Security",
                    title=title, path=rel_path, line=line_no, evidence=safe_line,
                    explanation=f"Pattern-matched secret-like value found on line {line_no}.",
                    recommendation=rec,
                ))
    if path.name.lower().startswith(".env"):
        findings.append(Finding(
            id=f"SEC-ENV-{stable_hash_int(rel_path):03d}", severity="MEDIUM", category="Security",
            title="Environment file present in repository", path=rel_path,
            explanation="Files like .env commonly store secrets.",
            recommendation="Add to .gitignore; commit a .env.example instead.",
        ))
    return findings


def analyze_python(path: Path, rel_path: str) -> (dict, List[Finding]):
    """Never executes the file -- uses ast.parse only."""
    stats = {"functions": 0, "classes": 0, "imports": 0}
    findings = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(text, filename=rel_path)
    except (OSError, SyntaxError) as exc:
        if isinstance(exc, SyntaxError):
            findings.append(Finding(
                id=f"CODE-SYNTAX-{stable_hash_int(rel_path):03d}", severity="MEDIUM", category="Code Health",
                title="Python syntax error", path=rel_path, line=getattr(exc, "lineno", None),
                explanation=f"File failed to parse: {exc.msg}",
                recommendation="Fix the syntax error.",
            ))
        return stats, findings

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            stats["functions"] += 1
        elif isinstance(node, ast.ClassDef):
            stats["classes"] += 1
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            stats["imports"] += 1
    return stats, findings


def hash_file(path: Path, chunk_size: int = 65536) -> Optional[str]:
    hasher = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            while True:
                chunk = fh.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)
    except OSError:
        return None
    return hasher.hexdigest()


def check_hygiene(root: Path, has_tests: bool) -> List[Finding]:
    findings = []
    readme_candidates = ["README.md", "README.rst", "README.txt", "README"]
    has_readme = any((root / c).exists() for c in readme_candidates)
    if not has_readme:
        findings.append(Finding(id="HYG-001", severity="MEDIUM", category="Hygiene",
                                 title="README missing",
                                 explanation="No README file found.",
                                 recommendation="Add a README.md."))
    if not (root / "LICENSE").exists() and not (root / "LICENSE.md").exists():
        findings.append(Finding(id="HYG-002", severity="LOW", category="Hygiene",
                                 title="LICENSE missing",
                                 explanation="No LICENSE file found.",
                                 recommendation="Add a LICENSE file."))
    if not (root / ".gitignore").exists():
        findings.append(Finding(id="HYG-003", severity="LOW", category="Hygiene",
                                 title=".gitignore missing",
                                 explanation="No .gitignore found.",
                                 recommendation="Add a .gitignore."))
    if not has_tests:
        findings.append(Finding(id="HYG-005", severity="MEDIUM", category="Hygiene",
                                 title="No test suite detected",
                                 explanation="No tests/ directory or test-named files found.",
                                 recommendation="Add automated tests."))
    return findings


def compute_score(findings: List[Finding]) -> Dict[str, int]:
    by_category = {"Security": 100, "Hygiene": 100, "Code Health": 100}
    for f in findings:
        cat = f.category if f.category in by_category else None
        if cat:
            by_category[cat] = max(0, by_category[cat] - SEVERITY_PENALTY.get(f.severity, 0))
    overall = round(
        by_category["Security"] * 0.4 + by_category["Code Health"] * 0.3 + by_category["Hygiene"] * 0.3
    )
    return {"overall": overall, **{k.lower().replace(" ", "_"): v for k, v in by_category.items()}}


def run_scan(root: Path, max_size_mb: float = 10) -> dict:
    max_bytes = int(max_size_mb * 1024 * 1024)
    files = discover_files(root, max_bytes)

    findings: List[Finding] = []
    total_lines = 0
    python_stats = {"functions": 0, "classes": 0, "imports": 0}
    hashes: Dict[str, List[str]] = {}
    has_tests = (root / "tests").is_dir() or (root / "test").is_dir()

    for path in files:
        rel = str(path.relative_to(root))
        if "test" in rel.lower():
            has_tests = True
        if is_binary(path):
            continue

        findings.extend(scan_secrets(path, rel))

        if path.suffix == ".py":
            stats, py_findings = analyze_python(path, rel)
            for k in python_stats:
                python_stats[k] += stats[k]
            findings.extend(py_findings)

        if path.suffix in SOURCE_EXTENSIONS or path.suffix in (".md", ".txt"):
            try:
                total_lines += len(path.read_text(encoding="utf-8", errors="replace").splitlines())
            except OSError:
                pass

        if path.stat().st_size > 0:
            digest = hash_file(path)
            if digest:
                hashes.setdefault(digest, []).append(rel)

    findings.extend(check_hygiene(root, has_tests))

    duplicate_groups = [paths for paths in hashes.values() if len(paths) > 1]

    scores = compute_score(findings)

    findings_sorted = sorted(
        findings,
        key=lambda f: ({"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}[f.severity], f.category, f.path, f.line or 0),
    )

    return {
        "project": {"path": str(root), "name": root.name},
        "summary": {"files_scanned": len(files), "total_lines": total_lines},
        "scores": scores,
        "code": python_stats,
        "duplicate_groups": duplicate_groups,
        "findings": [asdict(f) for f in findings_sorted],
    }


def render_text(result: dict) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("DEV LENS (single-file) REPORT")
    lines.append("=" * 60)
    lines.append(f"\nProject: {result['project']['name']}")
    lines.append(f"Files scanned: {result['summary']['files_scanned']}")
    lines.append(f"Total lines: {result['summary']['total_lines']}")
    lines.append(f"\nOverall score: {result['scores']['overall']}/100")
    for k, v in result["scores"].items():
        if k != "overall":
            lines.append(f"  {k}: {v}/100")
    lines.append(f"\nFindings ({len(result['findings'])}):")
    for f in result["findings"]:
        loc = f"{f['path']}:{f['line']}" if f.get("line") else f.get("path", "")
        lines.append(f"[{f['severity']}] [{f['id']}] {f['title']}" + (f" ({loc})" if loc else ""))
        if f.get("evidence"):
            lines.append(f"    Evidence: {f['evidence']}")
    if result["duplicate_groups"]:
        lines.append(f"\nDuplicate file groups: {result['duplicate_groups']}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="devlens_single", description="DevLens Single - condensed single-file scanner.")
    parser.add_argument("path", nargs="?", default=".")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--max-file-size", type=float, default=10)
    parser.add_argument("--version", action="store_true")
    args = parser.parse_args(argv)

    if args.version:
        print(f"DevLens Single {VERSION}")
        return 0

    root = Path(args.path)
    if not root.exists() or not root.is_dir():
        print(f"Error: not a valid directory: {args.path}", file=sys.stderr)
        return 2

    result = run_scan(root.resolve(), max_size_mb=args.max_file_size)

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(render_text(result))

    return 1 if result["findings"] else 0


if __name__ == "__main__":
    sys.exit(main())
