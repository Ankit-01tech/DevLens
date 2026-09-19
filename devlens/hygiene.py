"""Repository / project hygiene checks.

Covers presence of README, LICENSE, .gitignore, tests, CI configuration,
plus lower-level anomalies like risky files, duplicate files, and large
binaries -- all using only filesystem inspection and hashing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from .constants import CI_CONFIG_PATHS, DUPLICATE_HASH_MAX_BYTES, HYGIENE_EXPECTED_FILES
from .models import FileRecord, Finding, Severity
from .utils import hash_file, human_size, stable_hash_int

RISKY_EXTENSIONS = {
    ".pem": ("Private key or certificate file", Severity.HIGH),
    ".key": ("Private key file", Severity.HIGH),
    ".pfx": ("Certificate/key bundle", Severity.HIGH),
    ".sqlite": ("SQLite database detected", Severity.INFO),
    ".sqlite3": ("SQLite database detected", Severity.INFO),
    ".db": ("Database file detected", Severity.INFO),
    ".bak": ("Backup file detected", Severity.LOW),
    ".old": ("Old/backup file detected", Severity.LOW),
    ".tmp": ("Temporary file detected", Severity.INFO),
    ".log": ("Log file detected", Severity.INFO),
    ".dump": ("Database dump detected", Severity.MEDIUM),
    ".sql": ("SQL file detected (verify no production data)", Severity.INFO),
}

LARGE_BINARY_THRESHOLD_BYTES = 5 * 1024 * 1024


def check_expected_files(root: Path) -> Dict[str, bool]:
    presence = {}
    for label, candidates in HYGIENE_EXPECTED_FILES.items():
        presence[label] = any((root / c).exists() for c in candidates)
    return presence


def check_ci_config(root: Path) -> bool:
    return any((root / p).exists() for p in CI_CONFIG_PATHS)


def check_tests_present(root: Path, files: List[FileRecord]) -> bool:
    if (root / "tests").is_dir() or (root / "test").is_dir():
        return True
    return any("test" in f.path.lower() for f in files if f.is_source)


def evaluate_hygiene(root: Path, files: List[FileRecord]) -> List[Finding]:
    findings: List[Finding] = []
    presence = check_expected_files(root)

    if not presence["README"]:
        findings.append(
            Finding(
                id="HYG-001", severity=Severity.MEDIUM, category="Hygiene",
                title="README missing",
                explanation="No README file was found at the project root.",
                recommendation="Add a README.md with installation, usage, and license information.",
            )
        )
    if not presence["LICENSE"]:
        findings.append(
            Finding(
                id="HYG-002", severity=Severity.LOW, category="Hygiene",
                title="LICENSE missing",
                explanation="No LICENSE file was found; the project's usage terms are unclear.",
                recommendation="Add a LICENSE file (e.g. MIT, Apache-2.0) appropriate for the project.",
            )
        )
    if not presence["gitignore"]:
        findings.append(
            Finding(
                id="HYG-003", severity=Severity.LOW, category="Hygiene",
                title=".gitignore missing",
                explanation="No .gitignore file was found; build artifacts or secrets may be committed accidentally.",
                recommendation="Add a .gitignore appropriate for the detected ecosystem(s).",
            )
        )

    if not check_ci_config(root):
        findings.append(
            Finding(
                id="HYG-004", severity=Severity.LOW, category="Hygiene",
                title="No CI configuration detected",
                explanation="No continuous integration configuration (GitHub Actions, GitLab CI, etc.) was found.",
                recommendation="Add a CI workflow to run tests automatically on each change.",
            )
        )

    if not check_tests_present(root, files):
        findings.append(
            Finding(
                id="HYG-005", severity=Severity.MEDIUM, category="Hygiene",
                title="No test suite detected",
                explanation="No tests/ directory or test-named source files were found.",
                recommendation="Add automated tests to guard against regressions.",
            )
        )

    for f in files:
        if f.extension in RISKY_EXTENSIONS:
            title, severity = RISKY_EXTENSIONS[f.extension]
            findings.append(
                Finding(
                    id=f"HYG-RISK-{stable_hash_int(f.path):03d}",
                    severity=severity, category="Hygiene",
                    title=title, path=f.path,
                    explanation=f"File extension '{f.extension}' commonly indicates: {title.lower()}.",
                    recommendation="Confirm this file should be committed and does not contain sensitive data.",
                )
            )
        if not f.is_binary and False:
            pass
        if f.size > LARGE_BINARY_THRESHOLD_BYTES:
            findings.append(
                Finding(
                    id=f"HYG-LARGE-{stable_hash_int(f.path):03d}",
                    severity=Severity.LOW, category="Hygiene",
                    title="Large file committed to repository",
                    path=f.path,
                    explanation=f"File is {human_size(f.size)}, which is unusually large for version control.",
                    recommendation="Consider Git LFS or excluding large binaries from the repository.",
                )
            )
        if f.unreadable and f.error and "broken symlink" in f.error:
            findings.append(
                Finding(
                    id=f"HYG-SYMLINK-{stable_hash_int(f.path):03d}",
                    severity=Severity.INFO, category="Hygiene",
                    title="Broken symlink",
                    path=f.path,
                    explanation="This symlink points to a target that does not exist.",
                    recommendation="Remove or fix the broken symlink.",
                )
            )

    return findings


def find_duplicates(root: Path, files: List[FileRecord]) -> List[List[str]]:
    """Group files by content hash to find duplicates (chunked hashing)."""
    by_hash: Dict[str, List[str]] = {}
    size_by_path: Dict[str, int] = {f.path: f.size for f in files}
    for f in files:
        if f.is_binary or f.size == 0 or f.size > DUPLICATE_HASH_MAX_BYTES or f.unreadable:
            continue
        digest = hash_file(root / f.path)
        if digest is None:
            continue
        by_hash.setdefault(digest, []).append(f.path)

    groups = [paths for paths in by_hash.values() if len(paths) > 1]
    groups.sort(key=lambda g: g[0])
    return groups


def duplicate_findings(groups: List[List[str]], files: List[FileRecord]) -> List[Finding]:
    """Turn duplicate-file groups into findings, including wasted-space estimate."""
    size_by_path: Dict[str, int] = {f.path: f.size for f in files}
    findings: List[Finding] = []
    for group in groups:
        per_file_size = size_by_path.get(group[0], 0)
        wasted = per_file_size * (len(group) - 1)
        group_key = ":".join(sorted(group))
        findings.append(
            Finding(
                id=f"HYG-DUP-{stable_hash_int(group_key):03d}",
                severity=Severity.LOW, category="Hygiene",
                title="Duplicate files detected",
                path=group[0],
                explanation=(
                    f"{len(group)} files share identical content: {', '.join(group)}. "
                    f"Approximately {human_size(wasted)} could be reclaimed by de-duplicating."
                ),
                recommendation="Remove or symlink duplicate files to avoid drift between copies.",
            )
        )
    return findings
