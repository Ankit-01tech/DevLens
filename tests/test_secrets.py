import tempfile
import unittest
from pathlib import Path

from devlens.models import Severity
from devlens.secret_scanner import SecretScanner


class TestSecretScanner(unittest.TestCase):
    def setUp(self):
        self.scanner = SecretScanner()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _scan_content(self, content: str, filename: str = "test.py"):
        path = self.root / filename
        path.write_text(content)
        return self.scanner.scan_file(path, filename)

    def test_detects_aws_key(self):
        findings = self._scan_content('key = "AKIAABCDEFGHIJKLMNOP"\n')
        ids = [f.id.rsplit("-", 1)[0] for f in findings]
        self.assertIn("SEC-AWS-KEY", ids)

    def test_detects_stripe_key(self):
        findings = self._scan_content('STRIPE_KEY = "sk_live_51H8xyzabcdefghijklmnop1234567890"\n')
        ids = [f.id.rsplit("-", 1)[0] for f in findings]
        self.assertIn("SEC-STRIPE-KEY", ids)

    def test_detects_private_key_header(self):
        findings = self._scan_content("-----BEGIN RSA PRIVATE KEY-----\nMIIB...\n")
        ids = [f.id.rsplit("-", 1)[0] for f in findings]
        self.assertIn("SEC-PRIVATE-KEY", ids)
        crit = [f for f in findings if f.id.startswith("SEC-PRIVATE-KEY")]
        self.assertEqual(crit[0].severity, Severity.CRITICAL)

    def test_ignores_placeholder_values(self):
        findings = self._scan_content('api_key = "your_api_key_here"\n')
        self.assertEqual(findings, [])

    def test_ignores_short_values(self):
        findings = self._scan_content('password = "abc"\n')
        self.assertEqual(findings, [])

    def test_never_reproduces_full_secret(self):
        secret = "sk_live_51H8xyzabcdefghijklmnop1234567890"
        findings = self._scan_content(f'STRIPE_KEY = "{secret}"\n')
        for f in findings:
            self.assertNotIn(secret, f.evidence)
            self.assertNotIn(secret, f.to_dict().values().__str__())

    def test_db_connection_string_detected(self):
        findings = self._scan_content(
            'DB = "postgresql://admin:hunter2pass@db.example.com:5432/prod"\n'
        )
        ids = [f.id.rsplit("-", 1)[0] for f in findings]
        self.assertIn("SEC-DB-CONN", ids)

    def test_env_filename_flagged(self):
        path = self.root / ".env"
        path.write_text("SECRET=abc123def456\n")
        findings = self.scanner.scan_file(path, ".env")
        titles = [f.title for f in findings]
        self.assertTrue(any("Environment" in t for t in titles))

    def test_no_false_positive_on_clean_file(self):
        findings = self._scan_content("def add(a, b):\n    return a + b\n")
        self.assertEqual(findings, [])

    def test_line_numbers_are_correct(self):
        content = "line1\nline2\nAKIAABCDEFGHIJKLMNOP\nline4\n"
        findings = self._scan_content(content)
        aws_findings = [f for f in findings if f.id.startswith("SEC-AWS-KEY")]
        self.assertEqual(aws_findings[0].line, 3)


if __name__ == "__main__":
    unittest.main()
