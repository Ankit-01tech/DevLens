"""Generates a short, prioritized, actionable recommendation list."""

from __future__ import annotations

from typing import List

from .models import Finding, Severity


def build_recommendations(findings: List[Finding], max_items: int = 8) -> List[str]:
    ordered = sorted(findings, key=lambda f: f.sort_key())
    seen_titles = set()
    recs: List[str] = []

    for f in ordered:
        if f.severity == Severity.INFO:
            continue
        if f.title in seen_titles:
            continue
        seen_titles.add(f.title)
        if f.recommendation:
            recs.append(f.recommendation)
        if len(recs) >= max_items:
            break

    if not recs:
        recs.append("No significant issues found. Keep up the good practices!")

    return recs
