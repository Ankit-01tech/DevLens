import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMO_PATH = REPO_ROOT / "examples" / "demo_project"


class TestCrossProcessDeterminism(unittest.TestCase):
    def test_finding_ids_are_deterministic_across_separate_processes(self):
        cmd = [sys.executable, str(REPO_ROOT / "devlens.py"), str(DEMO_PATH), "--format", "json"]

        run1 = subprocess.run(cmd, capture_output=True, text=True)
        run2 = subprocess.run(cmd, capture_output=True, text=True)

        self.assertIn(run1.returncode, (0, 1))
        self.assertIn(run2.returncode, (0, 1))

        json_str1 = run1.stdout[run1.stdout.find("{"):run1.stdout.rfind("}") + 1]
        json_str2 = run2.stdout[run2.stdout.find("{"):run2.stdout.rfind("}") + 1]

        data1 = json.loads(json_str1)
        data2 = json.loads(json_str2)

        ids1 = [f["id"] for f in data1.get("findings", [])]
        ids2 = [f["id"] for f in data2.get("findings", [])]

        self.assertTrue(len(ids1) > 0, "Expected demo_project to produce findings")
        self.assertEqual(ids1, ids2, "Finding IDs must be byte-for-byte identical across separate Python processes")
        self.assertEqual(data1.get("scores"), data2.get("scores"), "Scores must be identical across separate processes")

    def test_single_file_finding_ids_are_deterministic_across_separate_processes(self):
        cmd = [sys.executable, str(REPO_ROOT / "devlens_single.py"), str(DEMO_PATH), "--format", "json"]

        run1 = subprocess.run(cmd, capture_output=True, text=True)
        run2 = subprocess.run(cmd, capture_output=True, text=True)

        self.assertIn(run1.returncode, (0, 1))
        self.assertIn(run2.returncode, (0, 1))

        data1 = json.loads(run1.stdout)
        data2 = json.loads(run2.stdout)

        ids1 = [f["id"] for f in data1.get("findings", [])]
        ids2 = [f["id"] for f in data2.get("findings", [])]

        self.assertTrue(len(ids1) > 0, "Expected demo_project single-file scan to produce findings")
        self.assertEqual(ids1, ids2, "Single-file finding IDs must be identical across separate Python processes")


if __name__ == "__main__":
    unittest.main()
