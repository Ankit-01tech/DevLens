import tempfile
import unittest
from pathlib import Path

from devlens import dependency_analyzer


class TestDependencyAnalyzer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_requirements_txt_basic(self):
        (self.root / "requirements.txt").write_text(
            "flask==2.0.1\nrequests\n# a comment\nnumpy==1.21.0\nrequests\n"
        )
        results = dependency_analyzer.analyze(self.root)
        self.assertEqual(len(results), 1)
        info = results[0]
        self.assertEqual(info.ecosystem, "python")
        self.assertIn("flask", info.runtime_dependencies)
        self.assertIn("requests", info.duplicate_declarations)

    def test_requirements_txt_pinned_detection(self):
        (self.root / "requirements.txt").write_text("flask==2.0.1\nnumpy==1.21.0\n")
        results = dependency_analyzer.analyze(self.root)
        self.assertTrue(results[0].pinned)

    def test_package_json_parses_dependencies(self):
        (self.root / "package.json").write_text(
            '{"dependencies": {"react": "^18.0.0"}, "devDependencies": {"jest": "29.0.0"}}'
        )
        results = dependency_analyzer.analyze(self.root)
        info = results[0]
        self.assertEqual(info.ecosystem, "node")
        self.assertIn("react", info.runtime_dependencies)
        self.assertIn("jest", info.dev_dependencies)
        self.assertFalse(info.pinned)  # react uses ^

    def test_malformed_package_json_does_not_crash(self):
        (self.root / "package.json").write_text("{not valid json,,,")
        results = dependency_analyzer.analyze(self.root)
        self.assertEqual(results[0].runtime_dependencies, [])

    def test_pyproject_toml_dependencies(self):
        (self.root / "pyproject.toml").write_text(
            '[project]\nname = "demo"\ndependencies = [\n  "requests>=2.0",\n  "click==8.1.0",\n]\n'
        )
        results = dependency_analyzer.analyze(self.root)
        info = results[0]
        self.assertIn("requests", info.runtime_dependencies)
        self.assertIn("click", info.runtime_dependencies)

    def test_go_mod_parsing(self):
        (self.root / "go.mod").write_text(
            "module example.com/app\n\ngo 1.21\n\nrequire (\n\tgithub.com/foo/bar v1.2.3\n\tgithub.com/baz/qux v0.1.0\n)\n"
        )
        results = dependency_analyzer.analyze(self.root)
        info = results[0]
        self.assertEqual(info.ecosystem, "go")
        self.assertIn("github.com/foo/bar", info.runtime_dependencies)

    def test_cargo_toml_parsing(self):
        (self.root / "Cargo.toml").write_text(
            '[package]\nname = "demo"\n\n[dependencies]\nserde = "1.0"\ntokio = "1.0"\n'
        )
        results = dependency_analyzer.analyze(self.root)
        info = results[0]
        self.assertEqual(info.ecosystem, "rust")
        self.assertIn("serde", info.runtime_dependencies)

    def test_pom_xml_parsing(self):
        (self.root / "pom.xml").write_text(
            "<project><dependencies>"
            "<dependency><groupId>org.junit</groupId><artifactId>junit</artifactId></dependency>"
            "</dependencies></project>"
        )
        results = dependency_analyzer.analyze(self.root)
        info = results[0]
        self.assertEqual(info.ecosystem, "java")
        self.assertIn("org.junit:junit", info.runtime_dependencies)

    def test_no_manifests_returns_empty(self):
        results = dependency_analyzer.analyze(self.root)
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
