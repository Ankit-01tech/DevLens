import csv
import io
import json
import unittest

from devlens.models import Finding, ScanResult, Severity
from devlens.reporters import render_csv_report, render_html_dashboard, render_json_report, render_text_report
from devlens.terminal import Palette


def _sample_result() -> ScanResult:
    result = ScanResult(project_path="/tmp/proj", project_name="proj")
    result.findings = [
        Finding(
            id="SEC-001", severity=Severity.HIGH, category="Security",
            title="Possible secret", path="a.py", line=3,
            evidence="key = ****", explanation="explanation", recommendation="rotate it",
        ),
        Finding(
            id="HYG-001", severity=Severity.LOW, category="Hygiene",
            title="Missing license", explanation="no license", recommendation="add one",
        ),
    ]
    result.recommendations = ["rotate it", "add one"]
    return result


class TestReporters(unittest.TestCase):
    def test_json_report_is_valid_and_complete(self):
        result = _sample_result()
        rendered = render_json_report(result)
        data = json.loads(rendered)
        self.assertEqual(data["project"]["name"], "proj")
        self.assertEqual(len(data["findings"]), 2)
        self.assertEqual(data["summary"]["finding_counts"]["HIGH"], 1)

    def test_json_report_never_contains_raw_secret_marker(self):
        result = _sample_result()
        rendered = render_json_report(result)
        self.assertNotIn("key = plaintext_secret_value", rendered)

    def test_csv_report_has_header_and_rows(self):
        result = _sample_result()
        rendered = render_csv_report(result)
        rows = list(csv.reader(io.StringIO(rendered)))
        self.assertEqual(rows[0][:4], ["id", "severity", "category", "title"])
        finding_ids = [r[0] for r in rows if r and r[0].startswith(("SEC", "HYG"))]
        self.assertIn("SEC-001", finding_ids)
        self.assertIn("HYG-001", finding_ids)

    def test_text_report_contains_key_sections(self):
        result = _sample_result()
        palette = Palette(enabled=False)
        rendered = render_text_report(result, palette)
        self.assertIn("DEV LENS REPORT", rendered)
        self.assertIn("FINDINGS", rendered)
        self.assertIn("RECOMMENDATIONS", rendered)
        self.assertIn("SEC-001", rendered)

    def test_text_report_plain_when_colors_disabled(self):
        result = _sample_result()
        palette = Palette(enabled=False)
        rendered = render_text_report(result, palette)
        self.assertNotIn("\033[", rendered)

    def test_findings_sorted_by_severity_in_text_report(self):
        result = _sample_result()
        palette = Palette(enabled=False)
        rendered = render_text_report(result, palette)
        self.assertLess(rendered.index("SEC-001"), rendered.index("HYG-001"))

    def test_html_dashboard_is_self_contained(self):
        result = _sample_result()
        rendered = render_html_dashboard(result)
        self.assertIn("<html", rendered)
        self.assertNotIn("cdn.", rendered)
        self.assertNotIn("<script src=", rendered)

    def test_html_dashboard_escapes_content(self):
        result = _sample_result()
        result.findings[0].title = "<script>alert(1)</script>"
        rendered = render_html_dashboard(result)
        self.assertNotIn("<script>alert(1)</script>", rendered)


if __name__ == "__main__":
    unittest.main()
