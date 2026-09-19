"""Core data models used throughout DevLens.

All models are plain dataclasses so they serialize cleanly to JSON/CSV
without pulling in any third-party serialization library.
"""

from __future__ import annotations

import dataclasses
from enum import Enum
from typing import Any, Dict, List, Optional


class Severity(str, Enum):
    """Finding severity levels, ordered from most to least urgent."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

    @property
    def rank(self) -> int:
        """Lower rank = more urgent. Used for deterministic sorting."""
        order = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3,
            Severity.INFO: 4,
        }
        return order[self]


@dataclasses.dataclass
class Finding:
    """A single, structured issue discovered during a scan.

    ``id`` follows a ``CATEGORY-NNN`` convention, e.g. ``SEC-001``.
    ``evidence`` must never contain a raw, unredacted secret.
    """

    id: str
    severity: Severity
    category: str
    title: str
    path: str = ""
    line: Optional[int] = None
    evidence: str = ""
    explanation: str = ""
    recommendation: str = ""

    def sort_key(self):
        return (self.severity.rank, self.category, self.path, self.line or 0, self.id)

    def to_dict(self) -> Dict[str, Any]:
        d = dataclasses.asdict(self)
        d["severity"] = self.severity.value
        return d


@dataclasses.dataclass
class FileRecord:
    """Metadata about a single discovered file."""

    path: str
    size: int
    extension: str
    is_binary: bool
    is_source: bool
    sha256: Optional[str] = None
    unreadable: bool = False
    error: Optional[str] = None


@dataclasses.dataclass
class CodeStats:
    total_files: int = 0
    source_files: int = 0
    total_lines: int = 0
    blank_lines: int = 0
    comment_lines: int = 0
    code_lines: int = 0
    todo_count: int = 0
    fixme_count: int = 0
    xxx_count: int = 0
    long_line_count: int = 0
    largest_files: List[Dict[str, Any]] = dataclasses.field(default_factory=list)
    extension_distribution: Dict[str, int] = dataclasses.field(default_factory=dict)
    python_functions: int = 0
    python_classes: int = 0
    python_imports: int = 0
    python_syntax_errors: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class DependencyInfo:
    ecosystem: str
    manifest_file: str
    runtime_dependencies: List[str] = dataclasses.field(default_factory=list)
    dev_dependencies: List[str] = dataclasses.field(default_factory=list)
    pinned: bool = False
    lockfile_present: bool = False
    duplicate_declarations: List[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class ScoreBreakdown:
    overall: int
    security: int
    dependencies: int
    code_health: int
    documentation: int
    hygiene: int
    weights: Dict[str, float]
    reasons: Dict[str, List[str]] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class ScanResult:
    """The complete, aggregated result of a DevLens scan."""

    project_path: str
    project_name: str
    detected_technologies: List[str] = dataclasses.field(default_factory=list)
    files: List[FileRecord] = dataclasses.field(default_factory=list)
    code_stats: CodeStats = dataclasses.field(default_factory=CodeStats)
    dependencies: List[DependencyInfo] = dataclasses.field(default_factory=list)
    findings: List[Finding] = dataclasses.field(default_factory=list)
    scores: Optional[ScoreBreakdown] = None
    recommendations: List[str] = dataclasses.field(default_factory=list)
    duplicate_groups: List[List[str]] = dataclasses.field(default_factory=list)
    scan_duration_seconds: float = 0.0
    errors: List[str] = dataclasses.field(default_factory=list)

    def sorted_findings(self) -> List[Finding]:
        return sorted(self.findings, key=lambda f: f.sort_key())

    def finding_counts(self) -> Dict[str, int]:
        counts = {s.value: 0 for s in Severity}
        for f in self.findings:
            counts[f.severity.value] += 1
        return counts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project": {
                "path": self.project_path,
                "name": self.project_name,
                "detected_technologies": self.detected_technologies,
            },
            "summary": {
                "files_scanned": len(self.files),
                "source_files": self.code_stats.source_files,
                "total_lines": self.code_stats.total_lines,
                "scan_duration_seconds": round(self.scan_duration_seconds, 3),
                "finding_counts": self.finding_counts(),
            },
            "scores": self.scores.to_dict() if self.scores else None,
            "dependencies": [d.to_dict() for d in self.dependencies],
            "code": self.code_stats.to_dict(),
            "duplicate_groups": self.duplicate_groups,
            "findings": [f.to_dict() for f in self.sorted_findings()],
            "recommendations": self.recommendations,
            "errors": self.errors,
        }
