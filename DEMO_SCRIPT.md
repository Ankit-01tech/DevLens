# DEMO_SCRIPT.md — 5-Minute Demo

## 0:00–0:30 — Problem

"When you pull down an unfamiliar repository — a coursework submission, an open-source project, a contractor's handoff — there's no fast way to know what's actually inside it. Is there a stray API key sitting in a config file? Are dependencies pinned? Is there a test suite at all? Today that means opening dozens of files by hand."

## 0:30–1:00 — Solution

"DevLens is a local-first, zero-dependency project health scanner. One command, no installation:"

```bash
python devlens.py /path/to/project
```

"It reports project structure, dependencies, exposed secrets, code health, documentation quality, and an overall explainable score — and it runs entirely offline. Nothing about your source code ever leaves your machine."

## 1:00–1:45 — Architecture

"DevLens is pure Python 3.11+ standard library — no pip install, ever. The pipeline runs eight stages: file discovery, project-type detection, dependency analysis, secret scanning, code analysis, hygiene checks, documentation evaluation, and finally a deterministic, weighted health score. Every score is explainable — every point deducted maps to a specific finding you can inspect."

(Show `ARCHITECTURE.md` diagram briefly.)

## 1:45–3:30 — Live scan of examples/demo_project

```bash
python devlens.py examples/demo_project --no-color
```

Narrate as it runs:

- "It found a hardcoded Stripe-style API key in `src/app.py` — and note the value is redacted, never printed in full."
- "A database connection string with an embedded password."
- "A duplicate file — `app.py` and `app_copy.py` have identical content, detected via SHA-256 hashing."
- "A Python syntax error in `broken.py`, caught safely by `ast.parse` without ever executing the file."
- "Missing LICENSE, missing tests, and a README that's too short — all rolled into an overall health score of about 62/100, broken down by category."

Optionally show the JSON report:

```bash
python devlens.py examples/demo_project --format json
```

"This is fully machine-readable — you could wire this into CI."

## 3:30–4:00 — Fix plan & CI Quality Gate

"DevLens v2.0 introduces an automated remediation plan and CI Quality Gate mode:"

```bash
python devlens.py examples/demo_project --fix-plan
```

"Without modifying any source files, `--fix-plan` outputs a prioritized list of remediation actions mapped directly to locations and reasons."

```bash
python devlens.py examples/demo_project --ci --fail-on high
```

"In CI mode, DevLens acts as a quality/security gate. Exit code 1 is returned when findings exceed the threshold level (`high`), allowing CI pipelines to fail builds deterministically."

## 4:00–4:25 — Self-scan & Reproducible Build

```bash
python devlens.py .
```

"DevLens scanning its own repository. Same codebase scanning itself cleanly."

```bash
python tools/reproducible_build.py
```

"This tool bundles DevLens into executable archives (`dist/devlens_a.pyz` and `dist/devlens_b.pyz`), normalizing entry timestamps. Both build artifacts produce byte-identical SHA-256 hashes, proving complete build reproducibility."

## 4:25–4:50 — Zero-dependency proof & Test Suite

```bash
python tools/dependency_check.py .
```

"This audit tool walks every Python file in the project via AST, extracts every import, and cross-references it against Python's own `sys.stdlib_module_names`. Zero third-party runtime dependencies, confirmed programmatically."

```bash
python -m unittest discover -v
```

"73+ unit tests, all passing in under a quarter-second, using standard-library `unittest`."

## 4:50–5:00 — Why DevLens matters

"DevLens proves that a genuinely useful developer security tool doesn't need a six-package dependency tree. It's local-first, so your code never leaves your machine. It's explainable, so every finding and every score has a documented reason. And it's zero-setup — clone it, and it just runs."
