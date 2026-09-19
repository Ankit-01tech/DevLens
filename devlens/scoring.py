"""Deterministic, explainable health scoring.

Every dimension score starts at 100 and is reduced by documented,
finding-driven penalties. Nothing here is a black-box AI guess -- each
point deducted maps to a specific reason recorded in ``reasons``.
"""

from __future__ import annotations

from typing import Dict, List

from .constants import DEFAULT_SCORE_WEIGHTS
from .models import Finding, ScoreBreakdown, Severity

SEVERITY_PENALTY = {
    Severity.CRITICAL: 25,
    Severity.HIGH: 12,
    Severity.MEDIUM: 6,
    Severity.LOW: 2,
    Severity.INFO: 0,
}

CATEGORY_TO_DIMENSION = {
    "Security": "security",
    "Dependencies": "dependencies",
    "Code Health": "code_health",
    "Documentation": "documentation",
    "Hygiene": "hygiene",
}


def _dimension_score(findings: List[Finding], doc_score: int = None) -> (int, List[str]):
    score = 100
    reasons: List[str] = []
    for f in findings:
        penalty = SEVERITY_PENALTY[f.severity]
        if penalty:
            score -= penalty
            reasons.append(f"-{penalty} for {f.severity.value} finding [{f.id}] {f.title}")
    if doc_score is not None:
        # Blend measured documentation-quality score with finding penalties.
        score = min(score, doc_score)
        reasons.append(f"Documentation quality heuristic score: {doc_score}/100")
    return max(0, min(100, score)), reasons


def compute_scores(
    findings: List[Finding],
    documentation_score: int,
    weights: Dict[str, float] = None,
) -> ScoreBreakdown:
    weights = weights or DEFAULT_SCORE_WEIGHTS
    by_dimension: Dict[str, List[Finding]] = {d: [] for d in weights}

    for f in findings:
        dim = CATEGORY_TO_DIMENSION.get(f.category)
        if dim:
            by_dimension.setdefault(dim, []).append(f)

    reasons: Dict[str, List[str]] = {}

    security_score, reasons["security"] = _dimension_score(by_dimension.get("security", []))
    deps_score, reasons["dependencies"] = _dimension_score(by_dimension.get("dependencies", []))
    code_score, reasons["code_health"] = _dimension_score(by_dimension.get("code_health", []))
    hygiene_score, reasons["hygiene"] = _dimension_score(by_dimension.get("hygiene", []))
    doc_score, reasons["documentation"] = _dimension_score(
        by_dimension.get("documentation", []), doc_score=documentation_score
    )

    dims = {
        "security": security_score,
        "dependencies": deps_score,
        "code_health": code_score,
        "documentation": doc_score,
        "hygiene": hygiene_score,
    }

    overall = sum(dims[k] * weights[k] for k in weights)
    overall = round(overall)

    return ScoreBreakdown(
        overall=overall,
        security=security_score,
        dependencies=deps_score,
        code_health=code_score,
        documentation=doc_score,
        hygiene=hygiene_score,
        weights=weights,
        reasons=reasons,
    )
