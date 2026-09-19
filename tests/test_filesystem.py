import os
import tempfile
import unittest
from pathlib import Path

from devlens.filesystem import FilesystemScanner, ScanConfig


class TestFilesystemScanner(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _scan(self, **kwargs):
        config = ScanConfig(root=self.root, **kwargs)
        scanner = FilesystemScanner(config)
        return scanner, scanner.discover()

    def test_discovers_plain_files(self):
        (self.root / "a.py").write_text("print(1)\n")
        (self.root / "b.txt").write_text("hello\n")
        _, records = self._scan()
        paths = {r.path for r in records}
        self.assertEqual(paths, {"a.py", "b.txt"})

    def test_ignores_default_dirs(self):
        (self.root / "node_modules").mkdir()
        (self.root / "node_modules" / "pkg.js").write_text("x")
        (self.root / "keep.py").write_text("x")
        _, records = self._scan()
        paths = {r.path for r in records}
        self.assertIn("keep.py", paths)
        self.assertFalse(any("node_modules" in p for p in paths))

    def test_custom_ignored_dirs(self):
        (self.root / "customdir").mkdir()
        (self.root / "customdir" / "file.py").write_text("x")
        _, records = self._scan(ignored_dirs={"customdir"})
        paths = {r.path for r in records}
        self.assertFalse(any("customdir" in p for p in paths))

    def test_handles_broken_symlink(self):
        target = self.root / "missing_target.txt"
        link = self.root / "broken_link.txt"
        try:
            os.symlink(str(target), str(link))
        except (OSError, NotImplementedError):
            self.skipTest("symlinks not supported in this environment")
        _, records = self._scan()
        broken = [r for r in records if r.path == "broken_link.txt"]
        self.assertEqual(len(broken), 1)
        self.assertTrue(broken[0].unreadable)

    def test_does_not_follow_symlink_loop(self):
        sub = self.root / "sub"
        sub.mkdir()
        loop_link = sub / "loop"
        try:
            os.symlink(str(self.root), str(loop_link))
        except (OSError, NotImplementedError):
            self.skipTest("symlinks not supported in this environment")
        (self.root / "real.py").write_text("x")
        # Should terminate without hanging or infinite recursion.
        _, records = self._scan()
        paths = {r.path for r in records}
        self.assertIn("real.py", paths)

    def test_binary_detection(self):
        (self.root / "bin.dat").write_bytes(b"\x00\x01\x02binarycontent")
        (self.root / "text.txt").write_text("just text")
        _, records = self._scan()
        by_path = {r.path: r for r in records}
        self.assertTrue(by_path["bin.dat"].is_binary)
        self.assertFalse(by_path["text.txt"].is_binary)

    def test_max_file_size_marks_large_files_binary_safe(self):
        big_content = "x" * 2000
        (self.root / "big.py").write_text(big_content)
        _, records = self._scan(max_file_size_mb=0.0001)
        by_path = {r.path: r for r in records}
        # Oversized files are conservatively treated as binary (skipped for deep analysis).
        self.assertTrue(by_path["big.py"].is_binary)

    def test_permission_error_does_not_crash(self):
        restricted_dir = self.root / "restricted"
        restricted_dir.mkdir()
        (restricted_dir / "secret.txt").write_text("x")
        try:
            os.chmod(restricted_dir, 0o000)
            scanner, records = self._scan()
            # Should not raise; errors may be recorded instead.
            self.assertIsInstance(records, list)
        finally:
            os.chmod(restricted_dir, 0o755)


if __name__ == "__main__":
    unittest.main()
