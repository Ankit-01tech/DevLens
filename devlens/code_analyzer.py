"""Source code statistics and Python AST analysis.

DevLens never executes scanned source code. Python files are parsed
with `ast.parse`, which builds a syntax tree without running any code
in the target project -- this is a hard security requirement.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Tuple

from .constants import COMMENT_PREFIXES_BY_EXT, LONG_LINE_THRESHOLD, MARKER_PATTERNS
from .models import CodeStats, Finding, Severity
from .utils import safe_read_text, stable_hash_int

MAX_ANALYSIS_BYTES = 5 * 1024 * 1024


class CodeAnalyzer:
    def __init__(self):
        self.stats = CodeStats()
        self.findings: List[Finding] = []
        self._largest: List[Tuple[int, str]] = []

    def analyze_file(self, path: Path, rel_path: str, ext: str, size: int) -> None:
        self.stats.total_files += 1
        self.stats.extension_distribution[ext] = self.stats.extension_distribution.get(ext, 0) + 1

        text = safe_read_text(path, max_bytes=MAX_ANALYSIS_BYTES)
        if text is None:
            return

        self.stats.source_files += 1
        self._largest.append((size, rel_path))

        comment_prefixes = COMMENT_PREFIXES_BY_EXT.get(ext, ())
        lines = text.splitlines()
        blank = 0
        comment = 0
        long_lines = 0

        for line in lines:
            stripped = line.strip()
            if not stripped:
                blank += 1
            elif comment_prefixes and stripped.startswith(comment_prefixes):
                comment += 1
            if len(line) > LONG_LINE_THRESHOLD:
                long_lines += 1
            upper = stripped.upper()
            for stat_key, markers in MARKER_PATTERNS.items():
                for marker in markers:
                    if marker in upper:
                        setattr(self.stats, stat_key, getattr(self.stats, stat_key) + 1)

        total = len(lines)
        code_lines = total - blank - comment

        self.stats.total_lines += total
        self.stats.blank_lines += blank
        self.stats.comment_lines += comment
        self.stats.code_lines += max(0, code_lines)
        self.stats.long_line_count += long_lines

        if long_lines > 20:
            self.findings.append(
                Finding(
                    id=f"CODE-LONGLINES-{stable_hash_int(rel_path):03d}",
                    severity=Severity.LOW,
                    category="Code Health",
                    title="File contains many very long lines",
                    path=rel_path,
                    explanation=f"{long_lines} lines exceed {LONG_LINE_THRESHOLD} characters, which can hurt readability.",
                    recommendation="Consider reformatting long lines for readability.",
                )
            )

        if ext == ".py":
            self._analyze_python_ast(text, rel_path)

    def _analyze_python_ast(self, text: str, rel_path: str) -> None:
        try:
            tree = ast.parse(text, filename=rel_path)
        except SyntaxError as exc:
            self.stats.python_syntax_errors += 1
            self.findings.append(
                Finding(
                    id=f"CODE-SYNTAX-{stable_hash_int(rel_path):03d}",
                    severity=Severity.MEDIUM,
                    category="Code Health",
                    title="Python syntax error",
                    path=rel_path,
                    line=getattr(exc, "lineno", None),
                    explanation=f"File failed to parse: {exc.msg}",
                    recommendation="Fix the syntax error; DevLens cannot analyze this file further.",
                )
            )
            return

        functions = 0
        classes = 0
        imports = 0
        max_depth = 0

        def visit(node: ast.AST, depth: int = 0) -> None:
            nonlocal functions, classes, imports, max_depth
            max_depth = max(max_depth, depth)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions += 1
            elif isinstance(node, ast.ClassDef):
                classes += 1
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                imports += 1
            for child in ast.iter_child_nodes(node):
                visit(child, depth + 1)

        visit(tree)

        self.stats.python_functions += functions
        self.stats.python_classes += classes
        self.stats.python_imports += imports

        if max_depth > 14:
            self.findings.append(
                Finding(
                    id=f"CODE-NESTING-{stable_hash_int(rel_path):03d}",
                    severity=Severity.LOW,
                    category="Code Health",
                    title="Deeply nested code structure",
                    path=rel_path,
                    explanation=f"AST nesting depth of {max_depth} suggests complex, hard-to-follow control flow.",
                    recommendation="Consider extracting nested logic into smaller functions.",
                )
            )

    def finalize(self) -> None:
        self._largest.sort(key=lambda t: t[0], reverse=True)
        self.stats.largest_files = [
            {"path": p, "size": s} for s, p in self._largest[:10]
        ]
