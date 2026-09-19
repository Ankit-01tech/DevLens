import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestReproducibleBuild(unittest.TestCase):
    def test_reproducible_build_script_passes(self):
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "tools" / "reproducible_build.py")],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Byte identical: YES", result.stdout)
        self.assertIn("RESULT: PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
