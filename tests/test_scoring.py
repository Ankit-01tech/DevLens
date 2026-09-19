import unittest

from devlens.models import Finding, Severity
from devlens.scoring import compute_scores


class TestScoring(unittest.TestCase):
    def test_no_findings_gives_perfect_scores(self):
        scores = compute_scores([], documentation_score=100)
        self.assertEqual(scores.security, 100)
        self.assertEqual(scores.dependencies, 100)
        self.assertEqual(scores.code_health, 100)
        self.assertEqual(scores.hygiene, 100)
        self.assertEqual(scores.documentation, 100)
        self.assertEqual(scores.overall, 100)

    def test_critical_security_finding_lowers_security_score(self):
        findings = [
            Finding(id="SEC-001", severity=Severity.CRITICAL, category="Security", title="Bad")
        ]
        scores = compute_scores(findings, documentation_score=100)
        self.assertEqual(scores.security, 75)  # 100 - 25
        self.assertEqual(scores.code_health, 100)

    def test_score_never_goes_below_zero(self):
        findings = [
            Finding(id=f"SEC-{i}", severity=Severity.CRITICAL, category="Security", title="Bad")
            for i in range(10)
        ]
        scores = compute_scores(findings, documentation_score=100)
        self.assertEqual(scores.security, 0)

    def test_overall_is_weighted_sum(self):
        scores = compute_scores([], documentation_score=100)
        weights = scores.weights
        expected = round(sum(100 * w for w in weights.values()))
        self.assertEqual(scores.overall, expected)

    def test_documentation_score_uses_heuristic_input(self):
        scores = compute_scores([], documentation_score=40)
        self.assertEqual(scores.documentation, 40)

    def test_reasons_are_recorded(self):
        findings = [
            Finding(id="SEC-001", severity=Severity.HIGH, category="Security", title="Bad thing")
        ]
        scores = compute_scores(findings, documentation_score=100)
        self.assertTrue(any("SEC-001" in r for r in scores.reasons["security"]))

    def test_scores_are_deterministic(self):
        findings = [
            Finding(id="SEC-001", severity=Severity.MEDIUM, category="Security", title="X"),
            Finding(id="HYG-001", severity=Severity.LOW, category="Hygiene", title="Y"),
        ]
        s1 = compute_scores(findings, documentation_score=80)
        s2 = compute_scores(findings, documentation_score=80)
        self.assertEqual(s1.to_dict(), s2.to_dict())


if __name__ == "__main__":
    unittest.main()
