import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestDependencyCheckTool(unittest.TestCase):
    def test_passes_against_devlens_itself(self):
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "tools" / "dependency_check.py"), str(REPO_ROOT)],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Result: PASS", result.stdout)
        self.assertIn("Zero runtime dependencies confirmed.", result.stdout)

    def test_flags_third_party_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bad.py").write_text("import requests\n")
            result = subprocess.run(
                [sys.executable, str(REPO_ROOT / "tools" / "dependency_check.py"), str(root)],
                capture_output=True, text=True, timeout=30,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("requests", result.stdout)

    def test_flags_adversarial_third_party_imports(self):
        adversarial_code = (
            "import requests\n"
            "import flask\n"
            "import numpy\n"
            "import pandas\n"
            "from rich import print\n"
            "import sqlalchemy\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "adversarial.py").write_text(adversarial_code)
            result = subprocess.run(
                [sys.executable, str(REPO_ROOT / "tools" / "dependency_check.py"), str(root)],
                capture_output=True, text=True, timeout=30,
            )
            self.assertNotEqual(result.returncode, 0)
            for pkg in ("requests", "flask", "numpy", "pandas", "rich", "sqlalchemy"):
                self.assertIn(pkg, result.stdout)


if __name__ == "__main__":
    unittest.main()
