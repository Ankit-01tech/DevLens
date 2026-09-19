import tempfile
import unittest
from pathlib import Path

from devlens.hygiene import duplicate_findings, evaluate_hygiene, find_duplicates
from devlens.models import FileRecord


class TestHygiene(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _record(self, path, size=10, is_binary=False, unreadable=False, ext=""):
        return FileRecord(path=path, size=size, extension=ext, is_binary=is_binary, is_source=False, unreadable=unreadable)

    def test_missing_readme_license_gitignore_flagged(self):
        files = []
        findings = evaluate_hygiene(self.root, files)
        ids = {f.id for f in findings}
        self.assertIn("HYG-001", ids)  # README missing
        self.assertIn("HYG-002", ids)  # LICENSE missing
        self.assertIn("HYG-003", ids)  # gitignore missing

    def test_present_files_not_flagged(self):
        (self.root / "README.md").write_text("docs")
        (self.root / "LICENSE").write_text("MIT")
        (self.root / ".gitignore").write_text("*.pyc")
        findings = evaluate_hygiene(self.root, [])
        ids = {f.id for f in findings}
        self.assertNotIn("HYG-001", ids)
        self.assertNotIn("HYG-002", ids)
        self.assertNotIn("HYG-003", ids)

    def test_risky_extension_flagged(self):
        (self.root / "id_rsa.key").write_text("fake key content")
        files = [self._record("id_rsa.key", ext=".key")]
        findings = evaluate_hygiene(self.root, files)
        self.assertTrue(any("key" in f.title.lower() for f in findings))

    def test_large_file_flagged(self):
        files = [self._record("big.bin", size=10 * 1024 * 1024)]
        findings = evaluate_hygiene(self.root, files)
        self.assertTrue(any("large" in f.title.lower() for f in findings))

    def test_duplicate_detection_finds_identical_files(self):
        (self.root / "a.py").write_text("print('hello')\n")
        (self.root / "b.py").write_text("print('hello')\n")
        files = [
            FileRecord(path="a.py", size=16, extension=".py", is_binary=False, is_source=True),
            FileRecord(path="b.py", size=16, extension=".py", is_binary=False, is_source=True),
        ]
        groups = find_duplicates(self.root, files)
        self.assertEqual(len(groups), 1)
        self.assertEqual(set(groups[0]), {"a.py", "b.py"})

    def test_duplicate_findings_report_wasted_space(self):
        groups = [["a.py", "b.py"]]
        files = [
            FileRecord(path="a.py", size=100, extension=".py", is_binary=False, is_source=True),
            FileRecord(path="b.py", size=100, extension=".py", is_binary=False, is_source=True),
        ]
        findings = duplicate_findings(groups, files)
        self.assertEqual(len(findings), 1)
        self.assertTrue("100" in findings[0].explanation or "B" in findings[0].explanation)

    def test_no_duplicates_for_unique_files(self):
        (self.root / "a.py").write_text("print(1)\n")
        (self.root / "b.py").write_text("print(2)\n")
        files = [
            FileRecord(path="a.py", size=10, extension=".py", is_binary=False, is_source=True),
            FileRecord(path="b.py", size=10, extension=".py", is_binary=False, is_source=True),
        ]
        groups = find_duplicates(self.root, files)
        self.assertEqual(groups, [])


if __name__ == "__main__":
    unittest.main()
