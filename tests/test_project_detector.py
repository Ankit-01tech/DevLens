import tempfile
import unittest
from pathlib import Path

from devlens.models import FileRecord
from devlens.project_detector import detect_technologies


class TestProjectDetector(unittest.TestCase):
    def test_root_level_python_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "requirements.txt").write_text("flask==3.0.0\n")
            techs = detect_technologies(root)
            self.assertIn("Python", techs)

    def test_root_level_node_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text('{"name": "test"}\n')
            techs = detect_technologies(root)
            self.assertIn("Node.js", techs)

    def test_nested_package_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frontend = root / "frontend"
            frontend.mkdir()
            (frontend / "package.json").write_text('{"name": "frontend"}\n')

            files = [
                FileRecord(path="frontend/package.json", size=30, extension=".json", is_binary=False, is_source=False)
            ]
            techs = detect_technologies(root, files)
            self.assertIn("Node.js", techs)

    def test_nested_python_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            backend = root / "backend"
            backend.mkdir()
            (backend / "requirements.txt").write_text("requests\n")

            files = [
                FileRecord(path="backend/requirements.txt", size=10, extension=".txt", is_binary=False, is_source=False)
            ]
            techs = detect_technologies(root, files)
            self.assertIn("Python", techs)

    def test_typescript_project_detected_through_tsconfig(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tsconfig.json").write_text('{}\n')

            files = [
                FileRecord(path="tsconfig.json", size=2, extension=".json", is_binary=False, is_source=False)
            ]
            techs = detect_technologies(root, files)
            self.assertIn("TypeScript", techs)

    def test_extension_based_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = [
                FileRecord(path="src/index.ts", size=100, extension=".ts", is_binary=False, is_source=True),
                FileRecord(path="src/App.tsx", size=200, extension=".tsx", is_binary=False, is_source=True),
            ]
            techs = detect_technologies(root, files)
            self.assertIn("TypeScript", techs)

    def test_mixed_python_and_typescript_node_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = [
                FileRecord(path="backend/app.py", size=100, extension=".py", is_binary=False, is_source=True),
                FileRecord(path="backend/main.py", size=150, extension=".py", is_binary=False, is_source=True),
                FileRecord(path="frontend/tsconfig.json", size=50, extension=".json", is_binary=False, is_source=False),
                FileRecord(path="frontend/package.json", size=80, extension=".json", is_binary=False, is_source=False),
            ]
            techs = detect_technologies(root, files)
            self.assertIn("Python", techs)
            self.assertIn("TypeScript", techs)
            self.assertIn("Node.js", techs)

    def test_empty_generic_repository_remains_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            techs = detect_technologies(root, [])
            self.assertEqual(techs, ["Unknown / Generic"])


if __name__ == "__main__":
    unittest.main()
