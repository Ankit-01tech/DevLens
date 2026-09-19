import io
import subprocess
import sys
import unittest
from pathlib import Path

from devlens.cli import EXIT_FINDINGS, EXIT_SUCCESS, main
from devlens.models import Finding, ScanResult, Severity
from devlens.reporters import render_ci_report, render_fix_plan
from devlens.terminal import Palette

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMO_PATH = REPO_ROOT / "examples" / "demo_project"


class TestFixPlanAndCI(unittest.TestCase):
    def test_fix_plan_cli_runs_successfully(self):
        result = main([str(DEMO_PATH), "--fix-plan"])
        self.assertEqual(result, EXIT_FINDINGS)

    def test_ci_mode_fail_on_high(self):
        result = main([str(DEMO_PATH), "--ci", "--fail-on", "high"])
        self.assertEqual(result, EXIT_FINDINGS)

    def test_ci_mode_fail_on_critical_passes_when_no_critical(self):
        result = main([str(DEMO_PATH), "--ci", "--fail-on", "critical"])
        self.assertEqual(result, EXIT_SUCCESS)

    def test_render_fix_plan_output_structure(self):
        res = ScanResult(project_path="/tmp/foo", project_name="foo")
        res.findings.append(
            Finding(
                id="SEC-001",
                severity=Severity.HIGH,
                category="Security",
                title="Test finding",
                path="src/main.py",
                line=10,
                explanation="Test explanation",
                recommendation="Fix the test issue",
            )
        )
        palette = Palette(enabled=False)
        rendered = render_fix_plan(res, palette)
        self.assertIn("DEV LENS REMEDIATION PLAN", rendered)
        self.assertIn("[SEC-001] Test finding", rendered)
        self.assertIn("src/main.py:10", rendered)
        self.assertIn("Action:    Fix the test issue", rendered)

    def test_render_ci_report_output_structure(self):
        res = ScanResult(project_path="/tmp/foo", project_name="foo")
        palette = Palette(enabled=False)
        rendered = render_ci_report(res, palette, fail_on_sev="HIGH")
        self.assertIn("DEV LENS CI QUALITY GATE REPORT", rendered)
        self.assertIn("Gate Status: PASS", rendered)


if __name__ == "__main__":
    unittest.main()
