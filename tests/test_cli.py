import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from devlens.cli import EXIT_FATAL_ERROR, EXIT_FINDINGS, EXIT_USAGE_ERROR, main


class TestCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, args):
        out = io.StringIO()
        err = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(args)
        return code, out.getvalue(), err.getvalue()

    def test_version_flag(self):
        code, out, _ = self._run(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("DevLens", out)

    def test_nonexistent_path_returns_usage_error(self):
        code, _, err = self._run([str(self.root / "does_not_exist")])
        self.assertEqual(code, EXIT_USAGE_ERROR)
        self.assertIn("does not exist", err)

    def test_file_instead_of_directory_returns_usage_error(self):
        f = self.root / "file.txt"
        f.write_text("x")
        code, _, err = self._run([str(f)])
        self.assertEqual(code, EXIT_USAGE_ERROR)

    def test_invalid_workers_returns_usage_error(self):
        code, _, err = self._run([str(self.root), "--workers", "0"])
        self.assertEqual(code, EXIT_USAGE_ERROR)

    def test_clean_project_scans_successfully(self):
        (self.root / "README.md").write_text("# Clean\n\nInstallation, usage, license included here in detail. " * 20)
        (self.root / "LICENSE").write_text("MIT")
        (self.root / ".gitignore").write_text("*.pyc")
        (self.root / "tests").mkdir()
        (self.root / "tests" / "test_x.py").write_text("def test_ok():\n    assert True\n")
        (self.root / "main.py").write_text("def main():\n    return 1\n")
        code, out, _ = self._run([str(self.root), "--no-color"])
        report = Path.cwd() / "devlens-report.json"
        self.assertIn("DEV LENS REPORT", out)
        if report.exists():
            report.unlink()

    def test_json_format_output_to_file(self):
        (self.root / "a.py").write_text("x = 1\n")
        out_file = self.root / "report.json"
        code, out, _ = self._run([str(self.root), "--format", "json", "--output", str(out_file)])
        self.assertTrue(out_file.exists())
        data = json.loads(out_file.read_text())
        self.assertIn("summary", data)

    def test_no_secrets_flag_suppresses_secret_findings(self):
        (self.root / "secret.py").write_text('API_KEY = "AKIAABCDEFGHIJKLMNOP"\n')
        out_file = self.root / "report.json"
        self._run([str(self.root), "--format", "json", "--output", str(out_file), "--no-secrets"])
        data = json.loads(out_file.read_text())
        sec_findings = [f for f in data["findings"] if f["category"] == "Security"]
        self.assertEqual(len(sec_findings), 0)

    def test_exit_code_reflects_findings(self):
        # Empty dir triggers several hygiene findings (no README etc.)
        code, _, _ = self._run([str(self.root), "--format", "json", "--output", str(self.root / "r.json")])
        self.assertEqual(code, EXIT_FINDINGS)


if __name__ == "__main__":
    unittest.main()
