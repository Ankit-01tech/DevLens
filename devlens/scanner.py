"""Top-level scan orchestration.

Coordinates filesystem discovery, project detection, dependency
analysis, secret scanning, code analysis, hygiene checks, scoring, and
recommendation generation into a single ScanResult.

Concurrency: file-level hashing and per-file analysis (secret scanning,
code stats) are CPU/IO bound but embarrassingly parallel across files,
so we use a bounded ThreadPoolExecutor. Threads (not processes) are
appropriate here because the work is dominated by I/O (reading files
from disk) rather than pure CPU, and threads avoid the pickling
overhead and complexity of multiprocessing for this workload. Output
order is always made deterministic by sorting after collection, never
by relying on completion order.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, List, Optional

from . import dependency_analyzer, documentation, git_analyzer, hygiene, project_detector, recommendations, scoring
from .code_analyzer import CodeAnalyzer
from .filesystem import FilesystemScanner, ScanConfig
from .models import Finding, ScanResult
from .secret_scanner import SecretScanner

ProgressCallback = Optional[Callable[[int, int, str], None]]


class ScanOptions:
    def __init__(
        self,
        path: str,
        max_file_size_mb: float = 10,
        workers: int = 4,
        enable_secrets: bool = True,
        enable_dependencies: bool = True,
    ):
        self.path = path
        self.max_file_size_mb = max_file_size_mb
        self.workers = max(1, workers)
        self.enable_secrets = enable_secrets
        self.enable_dependencies = enable_dependencies


def run_scan(options: ScanOptions, progress: ProgressCallback = None) -> ScanResult:
    start = time.time()
    root = Path(options.path).resolve()

    def report(step: int, total: int, message: str) -> None:
        if progress:
            progress(step, total, message)

    total_steps = 8
    report(1, total_steps, "Discovering files...")
    fs_config = ScanConfig(root=root, max_file_size_mb=options.max_file_size_mb)
    fs_scanner = FilesystemScanner(fs_config)
    files = fs_scanner.discover()

    result = ScanResult(project_path=str(root), project_name=root.name or str(root))
    result.files = files
    result.errors.extend(fs_scanner.errors)

    report(2, total_steps, "Detecting project type...")
    result.detected_technologies = project_detector.detect_technologies(root, files)

    all_findings: List[Finding] = []

    report(3, total_steps, "Analyzing dependencies...")
    if options.enable_dependencies:
        result.dependencies = dependency_analyzer.analyze(root)
        all_findings.extend(_dependency_findings(result.dependencies))

    report(4, total_steps, "Scanning for exposed secrets...")
    if options.enable_secrets:
        all_findings.extend(_scan_secrets(root, files, options.workers))

    report(5, total_steps, "Calculating code statistics...")
    code_analyzer = _analyze_code(root, files)
    result.code_stats = code_analyzer.stats
    all_findings.extend(code_analyzer.findings)

    report(6, total_steps, "Checking repository hygiene...")
    all_findings.extend(hygiene.evaluate_hygiene(root, files))
    result.duplicate_groups = hygiene.find_duplicates(root, files)
    all_findings.extend(hygiene.duplicate_findings(result.duplicate_groups, files))
    git_info = git_analyzer.analyze_git(root)
    if git_info is None:
        from .models import Severity as _Severity

        all_findings.append(
            Finding(
                id="HYG-GIT-000",
                severity=_Severity.LOW,
                category="Hygiene",
                title="No Git repository detected",
                explanation="No .git directory was found at the project root.",
                recommendation="Initialize version control with `git init` if this project doesn't already use it.",
            )
        )

    report(7, total_steps, "Evaluating documentation...")
    doc_result, doc_findings = documentation.evaluate_documentation(root)
    all_findings.extend(doc_findings)

    report(8, total_steps, "Calculating health score...")
    # Sort now so every downstream consumer (scoring reasons, recommendations,
    # JSON/CSV/text rendering) sees a deterministic order regardless of which
    # thread pool worker happened to finish first during secret scanning.
    all_findings.sort(key=lambda f: f.sort_key())
    result.findings = all_findings
    result.scores = scoring.compute_scores(all_findings, documentation_score=doc_result["score"])
    result.recommendations = recommendations.build_recommendations(all_findings)

    result.scan_duration_seconds = time.time() - start
    return result


def _dependency_findings(dep_infos) -> List[Finding]:
    from .models import Finding, Severity

    findings = []
    for dep in dep_infos:
        total = len(dep.runtime_dependencies)
        if total > 80:
            findings.append(
                Finding(
                    id=f"DEP-LARGE-{dep.ecosystem}", severity=Severity.LOW, category="Dependencies",
                    title="Unusually large dependency list",
                    path=dep.manifest_file,
                    explanation=f"{total} runtime dependencies declared for {dep.ecosystem}.",
                    recommendation="Review whether all dependencies are still needed; large dependency trees increase attack surface.",
                )
            )
        if dep.duplicate_declarations:
            findings.append(
                Finding(
                    id=f"DEP-DUP-{dep.ecosystem}", severity=Severity.LOW, category="Dependencies",
                    title="Duplicate dependency declarations",
                    path=dep.manifest_file,
                    explanation=f"Duplicated entries: {', '.join(dep.duplicate_declarations)}.",
                    recommendation="Remove duplicate dependency declarations from the manifest.",
                )
            )
        if not dep.lockfile_present and dep.ecosystem in ("node", "python", "rust"):
            findings.append(
                Finding(
                    id=f"DEP-NOLOCK-{dep.ecosystem}", severity=Severity.INFO, category="Dependencies",
                    title="No lockfile detected",
                    path=dep.manifest_file,
                    explanation="No lockfile was found, so exact resolved dependency versions are not pinned.",
                    recommendation="Commit a lockfile to ensure reproducible installs.",
                )
            )
    return findings


def _scan_secrets(root: Path, files, workers: int) -> List[Finding]:
    scanner = SecretScanner()
    candidates = [f for f in files if not f.is_binary and not f.unreadable]
    findings: List[Finding] = []

    def worker(rel_path: str):
        return scanner.scan_file(root / rel_path, rel_path)

    if workers <= 1 or len(candidates) < 20:
        for f in candidates:
            findings.extend(worker(f.path))
        return findings

    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {pool.submit(worker, f.path): f.path for f in candidates}
        for future in as_completed(future_map):
            try:
                findings.extend(future.result())
            except Exception:
                # A single file's failure must never abort the whole scan.
                continue
    return findings


def _analyze_code(root: Path, files) -> CodeAnalyzer:
    analyzer = CodeAnalyzer()
    for f in files:
        if f.is_binary or f.unreadable:
            continue
        if not f.is_source and f.extension not in (".md", ".txt", ".rst"):
            continue
        analyzer.analyze_file(root / f.path, f.path, f.extension, f.size)
    analyzer.finalize()
    return analyzer
