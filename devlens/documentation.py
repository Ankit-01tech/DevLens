"""README / documentation quality heuristics."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .constants import HYGIENE_EXPECTED_FILES
from .models import Finding, Severity

SECTION_KEYWORDS = {
    "installation": ["install", "installation", "setup", "getting started"],
    "usage": ["usage", "how to use", "quick start", "example"],
    "features": ["features", "what it does"],
    "configuration": ["configuration", "config", "options", "environment variables"],
    "testing": ["testing", "tests", "how to test"],
    "license": ["license", "licence"],
    "contribution": ["contributing", "contribution"],
    "examples": ["example", "examples", "demo"],
}

MIN_SUBSTANTIAL_LENGTH = 500


def find_readme(root: Path) -> Optional[Path]:
    for candidate in HYGIENE_EXPECTED_FILES["README"]:
        p = root / candidate
        if p.exists():
            return p
    return None


def evaluate_documentation(root: Path) -> Dict:
    readme = find_readme(root)
    result = {
        "present": readme is not None,
        "length_chars": 0,
        "sections_found": [],
        "score": 0,
    }
    findings: List[Finding] = []

    if readme is None:
        findings.append(
            Finding(
                id="DOC-000", severity=Severity.MEDIUM, category="Documentation",
                title="README missing",
                explanation="No README file exists to document the project.",
                recommendation="Add a README.md covering installation, usage, and license.",
            )
        )
        return result, findings
    # (readme exists past this point)

    try:
        text = readme.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""

    lowered = text.lower()
    result["length_chars"] = len(text)

    found_sections = []
    for section, keywords in SECTION_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            found_sections.append(section)
    result["sections_found"] = found_sections

    if len(text) < MIN_SUBSTANTIAL_LENGTH:
        findings.append(
            Finding(
                id="DOC-001", severity=Severity.MEDIUM, category="Documentation",
                title="README exists but is very small",
                path=str(readme.name),
                explanation=f"README is only {len(text)} characters, suggesting minimal documentation.",
                recommendation="Expand the README with installation, usage, and configuration details.",
            )
        )

    missing = [s for s in ("installation", "usage", "license") if s not in found_sections]
    if missing:
        findings.append(
            Finding(
                id="DOC-002", severity=Severity.LOW, category="Documentation",
                title="README missing common sections",
                path=str(readme.name),
                explanation=f"Could not find guidance for: {', '.join(missing)}.",
                recommendation=f"Add sections covering: {', '.join(missing)}.",
            )
        )

    # Score: base on length + section coverage, deterministic and explainable.
    length_score = min(50, int(len(text) / 40))
    section_score = int(50 * (len(found_sections) / len(SECTION_KEYWORDS)))
    result["score"] = min(100, length_score + section_score)

    return result, findings
