import tempfile
import unittest
from pathlib import Path

from devlens.code_analyzer import CodeAnalyzer


class TestCodeAnalyzer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.analyzer = CodeAnalyzer()

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, name: str, content: str) -> Path:
        p = self.root / name
        p.write_text(content)
        return p

    def test_counts_lines_blank_and_comments(self):
        p = self._write("a.py", "x = 1\n\n# comment\ny = 2\n")
        self.analyzer.analyze_file(p, "a.py", ".py", p.stat().st_size)
        self.assertEqual(self.analyzer.stats.total_lines, 4)
        self.assertEqual(self.analyzer.stats.blank_lines, 1)
        self.assertEqual(self.analyzer.stats.comment_lines, 1)
        self.assertEqual(self.analyzer.stats.code_lines, 2)

    def test_todo_fixme_xxx_markers(self):
        p = self._write("b.py", "# TODO: fix\n# FIXME: broken\n# XXX weird\n")
        self.analyzer.analyze_file(p, "b.py", ".py", p.stat().st_size)
        self.assertEqual(self.analyzer.stats.todo_count, 1)
        self.assertEqual(self.analyzer.stats.fixme_count, 1)
        self.assertEqual(self.analyzer.stats.xxx_count, 1)

    def test_python_ast_counts_functions_and_classes(self):
        code = "class Foo:\n    def bar(self):\n        pass\n\ndef baz():\n    pass\n"
        p = self._write("c.py", code)
        self.analyzer.analyze_file(p, "c.py", ".py", p.stat().st_size)
        self.assertEqual(self.analyzer.stats.python_classes, 1)
        self.assertEqual(self.analyzer.stats.python_functions, 2)

    def test_python_syntax_error_recorded_not_crashed(self):
        p = self._write("broken.py", "def f(:\n    pass\n")
        self.analyzer.analyze_file(p, "broken.py", ".py", p.stat().st_size)
        self.assertEqual(self.analyzer.stats.python_syntax_errors, 1)
        self.assertTrue(any(f.category == "Code Health" for f in self.analyzer.findings))

    def test_does_not_execute_python_code(self):
        # If this file were executed, it would create a marker file. It must not be.
        marker = self.root / "SHOULD_NOT_EXIST"
        code = f"open(r'{marker}', 'w').write('bad')\n"
        p = self._write("dangerous.py", code)
        self.analyzer.analyze_file(p, "dangerous.py", ".py", p.stat().st_size)
        self.assertFalse(marker.exists())

    def test_long_lines_counted(self):
        p = self._write("long.py", "x = '" + "a" * 300 + "'\n")
        self.analyzer.analyze_file(p, "long.py", ".py", p.stat().st_size)
        self.assertEqual(self.analyzer.stats.long_line_count, 1)

    def test_largest_files_sorted_after_finalize(self):
        p1 = self._write("small.py", "x = 1\n")
        p2 = self._write("large.py", "x = 1\n" * 1000)
        self.analyzer.analyze_file(p1, "small.py", ".py", p1.stat().st_size)
        self.analyzer.analyze_file(p2, "large.py", ".py", p2.stat().st_size)
        self.analyzer.finalize()
        self.assertEqual(self.analyzer.stats.largest_files[0]["path"], "large.py")


if __name__ == "__main__":
    unittest.main()
