# JUDGE_QA.md — Hackathon Judge Q&A & Technical Defense

This document provides technically honest, precise answers to common questions judges may ask during evaluation of **DevLens v2.0**.

---

### 1. What problem are you solving?
Developers regularly inspect unfamiliar repositories (open-source projects, contractor deliverables, student submissions, internal audits) without a fast, safe way to audit project health, secret exposures, dependency hygiene, and documentation quality in a single step.

### 2. Why is it useful?
It provides instant supply-chain intelligence, secret exposure detection, and project hygiene analysis before running `npm install`, `pip install`, or executing third-party code, avoiding accidental credential leaks or compromised build steps.

### 3. Why not use existing tools?
Existing scanners (like Snyk, Trivy, or Semgrep) typically require installing multi-megabyte package dependencies, node/python runtime environments, external cloud services, or running heavy binary toolchains. DevLens runs instantly out of the box with zero installation overhead on any machine with Python 3.11+.

### 4. What makes DevLens different?
- **Zero third-party runtime dependencies**: Pure standard library.
- **Local-first & offline**: Zero network calls, zero telemetry, no code leaves the disk.
- **Non-execution guarantee**: Static AST parsing and file inspection only; never imports or executes scanned code.
- **Explainable health scoring**: Transparent deductions with explicit reason tracing.
- **Remediation plan & CI gate**: Built-in `--fix-plan` and `--ci --fail-on <severity>` quality gates.

### 5. Why zero dependencies?
Zero dependencies mean zero attack surface, zero installation time, zero supply-chain risk from third-party packages, zero version conflicts, and immediate portability across any system with standard Python 3.11+.

### 6. How do you detect secrets?
Using high-precision regular expressions for structured keys (AWS, Stripe, GitHub, Google, JWT, database URIs, private keys) combined with Shannon entropy scoring and contextual variable assignment analysis.

### 7. How do you prevent secret leakage?
DevLens NEVER prints or logs raw secrets. Secrets are sanitized using a strict redaction function (`redact()`) that preserves only a short, safe prefix (e.g. `sk_l****************`) in terminal reports, JSON, CSV, and HTML outputs.

### 8. Do you execute scanned code?
**NO.** DevLens uses Python's standard `ast.parse()` to analyze code structure statically. It never imports Python modules, never executes `setup.py`, and never executes build scripts or shell commands from the scanned project.

### 9. How do you handle malicious repositories?
- No code execution or dynamic imports.
- Safe path resolution and symlink loop detection (`os.path.realpath` visited set).
- File size caps (`--max-file-size`) and chunked streaming reads prevent memory exhaustion.
- Subprocess execution is strictly limited to fixed, read-only Git commands (`git log -1`, `git branch`, `git rev-list`).

### 10. How does concurrency work?
DevLens uses `concurrent.futures.ThreadPoolExecutor` for parallel file secret scanning and stats analysis. Findings from worker threads are collected and deterministically sorted by severity, category, path, and line, ensuring byte-identical report output regardless of thread completion order.

### 11. How is scoring calculated?
Scores start at 100 per dimension (Security 30%, Code Health 25%, Documentation 15%, Dependencies 15%, Hygiene 15%). Finding severities subtract fixed points (Critical -25, High -12, Medium -6, Low -2). The overall score is the weighted sum rounded to an integer.

### 12. Is the score scientifically validated?
No. It is an explainable heuristic health metric designed to prioritize remediation, not a formal academic security proof. Every point deducted maps to a documented finding in `result.scores.reasons`.

### 13. What ecosystems are supported?
Static manifest parsing is supported for:
- Python (`requirements.txt`, `pyproject.toml`)
- Node.js (`package.json`)
- Rust (`Cargo.toml`)
- Go (`go.mod`)
- Java (`pom.xml`)

### 14. What happens with malformed files?
- Malformed UTF-8/binary data: decodes safely with `errors='replace'` or is flagged as binary.
- Syntax errors in Python: caught as AST parse exceptions, recorded as a Medium finding, and scan proceeds cleanly.
- Malformed JSON/TOML manifests: safely caught; returns partial info or reports unreadable manifest rather than crashing.

### 15. What are your limitations?
- Does NOT perform CVE vulnerability lookups (no online database connection).
- Non-Python languages (JS, Go, Rust, Java) use line-based heuristics rather than full AST parsing.
- Git analysis requires `git` binary on PATH (falls back gracefully to directory detection if missing).

### 16. What packages did you replace?
13 standard-library substitutions documented in `STDLIB.md`:
- Click / Typer → `argparse`
- Rich → ANSI escape sequences
- Colorama → `NO_COLOR` / `TERM` detection
- Requests → local-first filesystem scanner / `urllib.request`
- Flask / FastAPI → `http.server` & `socketserver`
- Jinja2 → f-strings with `html.escape()`
- PyYAML → `pathlib` file presence checks
- toml / tomllib → targeted regex parsing
- GitPython → safe `subprocess` allowlist
- Pandas → `csv` module & `collections`
- SQLAlchemy → `dataclasses` & `sqlite3`
- pytest → `unittest`
- zipapp / wheel builders → `zipfile` with timestamp normalization

### 17. How is the single-file version implemented?
`devlens_single.py` is a standalone, copy-anywhere Python script implementing file discovery, secret scanning, Python AST code stats, hygiene checks, and health scoring in ~350 lines of zero-dependency Python.

### 18. How did you verify reproducibility?
- **Scan Report Determinism**: `tools/reproducibility_check.py` runs scans twice and verifies identical JSON payload hashes (excluding timing).
- **Build Artifact Reproducibility**: `tools/reproducible_build.py` packs DevLens into executable zipapp archives (`dist/devlens_a.pyz` and `dist/devlens_b.pyz`) with an explicit shebang (`#!/usr/bin/env python3`), normalized ZIP entry timestamps (`FIXED_ZIP_DATE`), and `0o755` permissions, asserting byte-identical SHA-256 hashes (`RESULT: PASS`) and direct executable execution (`./dist/devlens_a.pyz`).

### 19. How is this useful in CI?
With `--ci` and `--fail-on <severity>` (e.g. `--fail-on high`), DevLens acts as a lightweight quality gate in GitHub Actions or GitLab CI. It prints a machine-friendly summary and exits with code `1` if findings exceed the specified threshold level, or `0` if clean.

### 20. What did AI assist with?
AI pair programming (Google Antigravity) assisted with test expansion, documentation synthesis, refactoring, and edge-case hardening. All architectural decisions, security boundaries, and code implementations were audited, executed, and verified by unit tests and CLI runs.

### 21. Can your team explain the implementation?
Yes. Every module (`scanner.py`, `secret_scanner.py`, `dependency_analyzer.py`, `scoring.py`, `reporters.py`, `cli.py`, `filesystem.py`) is written in simple, readable Python standard library code without external framework magic.
