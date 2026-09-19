# DevLens v2.0

**"See what's really inside your software."**

DevLens is a local-first developer security and project-quality analyzer. Point it at any project directory and it produces an actionable report covering project structure, dependencies, exposed secrets, code health, documentation, repository hygiene, and an overall, explainable health score.

Built for the **Zero Dependency 2026 — 72-Hour Hackathon by Hackathon Raptors**, Track A (Developer Tools & CLI).

---

## Table of contents

1. [Problem](#problem)
2. [Why this matters](#why-this-matters)
3. [Solution](#solution)
4. [Key features](#key-features)
5. [Architecture](#architecture)
6. [Zero-dependency philosophy](#zero-dependency-philosophy)
7. [Installation](#installation)
8. [Usage](#usage)
9. [CLI reference](#cli-reference)
10. [Example output](#example-output)
11. [JSON output](#json-output)
12. [Security model](#security-model)
13. [Performance](#performance)
14. [Testing](#testing)
15. [Demo project](#demo-project)
16. [Standard-library substitutions](#standard-library-substitutions)
17. [Limitations](#limitations)
18. [Future improvements](#future-improvements)
19. [License](#license)

---

## Problem

Developers regularly pull down unfamiliar repositories — a coursework submission, an open-source project, a contractor's handoff — and have no fast way to answer basic questions: Does it declare its dependencies cleanly? Is there a stray API key sitting in a config file? Is there a test suite at all? Answering these by hand means opening dozens of files one at a time.

## Why this matters

Supply-chain and credential-exposure incidents are frequently caused by things that are simple to check for but easy to overlook: a `.env` file committed by accident, a hardcoded database password, a dependency manifest nobody has looked at in months. A quick, local, zero-setup scan that surfaces these issues up front — before code review, before a demo, before a deploy — closes an entire class of "nobody looked" mistakes.

## Solution

Run one command:

```
python devlens.py /path/to/project
```

DevLens scans the project directory and reports:

1. Project structure and detected technologies
2. Code statistics (lines, comments, functions, classes, TODOs)
3. Dependency intelligence (declared deps, pinning, lockfiles)
4. Secret exposure (heuristic detection, always redacted)
5. Security hygiene (risky files, large binaries)
6. File anomalies (duplicates, broken symlinks, oversized files)
7. Documentation quality (README section coverage)
8. Test presence
9. Git/project hygiene (README, LICENSE, .gitignore, CI config)
10. An overall, weighted, explainable health score (0–100)
11. Machine-readable JSON/CSV reports for CI integration

## Key features

- **One command, zero setup.** `python devlens.py .` — no `pip install`, no virtualenv, no lockfile to resolve.
- **Heuristic secret scanner** with entropy scoring, placeholder filtering, and mandatory redaction — full secret values are never printed, logged, or written to any report.
- **Static dependency analysis** for Python, Node.js, Rust, Go, and Java manifests, without invoking any of those toolchains.
- **Python AST analysis** (functions, classes, imports, syntax errors, nesting depth) without ever executing the scanned code.
- **Transparent, deterministic scoring** — every point deducted from every score maps to a specific finding, documented in the JSON report's `reasons`.
- **Duplicate file detection** via streaming SHA-256 hashing.
- **Concurrent analysis** via a bounded thread pool, with fully deterministic (sorted) output regardless of completion order.
- **Three report formats**: human-readable terminal text, machine-readable JSON, and CSV for spreadsheets.
- **Optional local HTML dashboard** (`--serve`) — a single self-contained page with no CDN, no JavaScript framework, no external assets.
- **Fully offline.** No network calls, no telemetry, no uploaded source code, ever.

## Architecture

```
devlens.py                  # entry point: python devlens.py <path>
devlens/
├── cli.py                  # argparse-based CLI, exit codes, dashboard server
├── scanner.py               # orchestrates the full scan pipeline
├── models.py                 # dataclasses: Finding, FileRecord, ScanResult, etc.
├── filesystem.py             # safe recursive directory walking
├── project_detector.py        # ecosystem detection via marker files
├── dependency_analyzer.py     # requirements.txt / package.json / Cargo.toml / go.mod / pom.xml
├── secret_scanner.py          # heuristic secret detection + redaction
├── code_analyzer.py           # line stats + Python AST analysis
├── git_analyzer.py            # safe, read-only git metadata inspection
├── hygiene.py                 # README/LICENSE/.gitignore/CI/tests + risky files + duplicates
├── documentation.py           # README quality heuristics
├── scoring.py                 # deterministic, weighted, explainable scoring
├── recommendations.py         # prioritized, human-readable recommendations
├── reporters.py               # text / JSON / CSV / HTML rendering
├── terminal.py                # ANSI colors with automatic plain-text fallback
└── constants.py               # shared configuration defaults
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full data-flow and scoring model documentation.

## Zero-dependency philosophy

DevLens uses **only the Python 3.11+ standard library**. There is no `requirements.txt` (or `pyproject.toml` dependency list) to install for DevLens itself — it runs on a clean Python installation. See [STDLIB.md](STDLIB.md) for a full table of what would normally be a third-party package, and what standard-library module replaces it in DevLens.

## Installation

Requires **Python 3.11 or later**. No installation step is needed:

```bash
git clone <this-repo>
cd devlens
python3 devlens.py --version
```

That's it. No `pip install`, no virtual environment required to run DevLens.

## Usage

```bash
# Scan a project (text report to terminal + devlens-report.json alongside it)
python devlens.py /path/to/project

# Scan the current directory
python devlens.py .

# JSON output
python devlens.py /path/to/project --format json

# CSV output
python devlens.py /path/to/project --format csv

# Write the report to a specific file
python devlens.py /path/to/project --output report.json --format json

# Skip the secret scanner or dependency analysis
python devlens.py /path/to/project --no-secrets
python devlens.py /path/to/project --no-dependencies

# Tune performance
python devlens.py /path/to/project --max-file-size 5 --workers 8

# Launch the local HTML dashboard
python devlens.py /path/to/project --serve

# Version / help
python devlens.py --version
python devlens.py --help
```

## CLI reference

| Flag | Description |
|---|---|
| `path` | Directory to scan (default: `.`) |
| `--format {text,json,csv}` | Report format (default: `text`) |
| `--output FILE` | Write report to a file instead of stdout |
| `--fix-plan` | Generate a non-modifying prioritized remediation plan |
| `--ci` | Run in Continuous Integration mode with quality gate summary |
| `--fail-on {critical,high,medium,low,info}` | Fail (exit code 1) if findings match or exceed specified severity |
| `--verbose` | Print full tracebacks on fatal errors |
| `--no-secrets` | Disable the secret scanner |
| `--no-dependencies` | Disable dependency manifest analysis |
| `--max-file-size MB` | Max file size analyzed in depth (default: 10) |
| `--workers N` | Worker threads for parallel analysis (default: 4) |
| `--no-color` | Disable ANSI color output |
| `--serve` | Serve an interactive local HTML dashboard |
| `--port PORT` | Port for `--serve` (default: 8787) |
| `--version` | Print version and exit |

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Scan completed, no findings at all |
| `1` | Scan completed successfully, findings were reported |
| `2` | Invalid usage (bad path, bad arguments) |
| `3` | Fatal/internal error during the scan |

## Example output

Running DevLens against the intentionally-flawed `examples/demo_project/`:

```
$ python devlens.py examples/demo_project --no-color

DevLens
Zero-Dependency Software Health Scanner
------------------------------------------------------------

Scanning: examples/demo_project

[1/8] Discovering files...
[2/8] Detecting project type...
[3/8] Analyzing dependencies...
[4/8] Scanning for exposed secrets...
[5/8] Calculating code statistics...
[6/8] Checking repository hygiene...
[7/8] Evaluating documentation...
[8/8] Calculating health score...

Scan complete.

============================================================
                 DEV LENS REPORT
============================================================

Project: demo_project
Path: /path/to/examples/demo_project
Detected technologies: Python
Files scanned: 7
Source files: 6
Total lines: 545

HEALTH SCORE
------------------------------------------------------------
Overall                     62/100

Security                    34/100
Dependencies                98/100
Code Health                 94/100
Documentation                6/100
Repository Hygiene          86/100

FINDINGS
------------------------------------------------------------

CRITICAL                    0
HIGH                        4
MEDIUM                      6
LOW                         6
INFO                        1

HIGH
[SEC-STRIPE-KEY-001] Possible Stripe API key
  File: src/app.py:6
  Evidence: API_KEY = "sk_l****************"
  This string matches the format of a Stripe secret/publishable key.
...

RECOMMENDATIONS
------------------------------------------------------------
1. Rotate the key from the Stripe dashboard immediately if this is a live key.
2. Move credentials to environment variables or a secrets manager instead of a connection string literal.
...

Full report: devlens-report.json
```

All sample credentials in `examples/demo_project/` are fake and non-functional; see [SECURITY.md](SECURITY.md).

## JSON output

The JSON report (`--format json`) has this shape:

```json
{
  "project": { "path": "...", "name": "...", "detected_technologies": ["Python"] },
  "summary": { "files_scanned": 7, "source_files": 6, "total_lines": 545, "finding_counts": {"CRITICAL": 0, "HIGH": 4, "...": "..."} },
  "scores": { "overall": 62, "security": 34, "dependencies": 98, "code_health": 94, "documentation": 6, "hygiene": 86, "weights": {"...": 0.0}, "reasons": {"...": ["..."]} },
  "dependencies": [ { "ecosystem": "python", "manifest_file": "requirements.txt", "runtime_dependencies": ["flask", "requests", "numpy"], "...": "..." } ],
  "code": { "total_lines": 545, "python_functions": 4, "...": "..." },
  "duplicate_groups": [["src/app.py", "src/app_copy.py"]],
  "findings": [ { "id": "SEC-STRIPE-KEY-001", "severity": "HIGH", "category": "Security", "title": "...", "path": "src/app.py", "line": 6, "evidence": "API_KEY = \"sk_l****************\"", "explanation": "...", "recommendation": "..." } ],
  "recommendations": ["..."],
  "errors": []
}
```

Findings are always sorted deterministically: severity, then category, then path, then line.

## Security model

DevLens treats every scanned project as **untrusted input**. It never executes scanned source code, never imports scanned Python modules, never runs a package manager against the scanned project, never runs Git hooks, and never deserializes untrusted pickle data. See [SECURITY.md](SECURITY.md) for the full threat model.

Secret detection is heuristic: **this is not a guarantee that all secrets are found, nor that every finding is a real credential.** Findings are meant to prompt human review.

## Performance

- Files are streamed (chunked reads) for hashing and secret scanning — large files are never loaded fully into memory beyond the configured size limit.
- Common generated/vendor directories (`node_modules`, `.venv`, `__pycache__`, `dist`, `build`, etc.) are ignored by default.
- Per-file secret scanning and code analysis run on a bounded thread pool (`--workers`, default 4); output is always deterministically sorted regardless of thread completion order.
- On a mid-size repository (a few thousand files), a full scan typically completes in well under a second to a few seconds, depending on disk speed and file sizes.

## Testing

```bash
python3 -m unittest discover -v
```

73+ tests across filesystem discovery, dependency parsing, secret detection, code/AST analysis, scoring, report rendering, `--fix-plan`, `--ci` exit codes, reproducible builds, and the CLI. See [TESTING.md](TESTING.md).

## Demo project

`examples/demo_project/` is a small, intentionally flawed project containing safe, non-functional fake credentials, a duplicate file, a Python syntax error, a tiny README, and no LICENSE/.gitignore/tests — designed to make DevLens's detections obvious in a live demo.

## Standard-library substitutions

See [STDLIB.md](STDLIB.md) for the full table (12 substitutions) of what DevLens replaces from the typical third-party toolchain.

## Limitations

- Secret detection is heuristic (regex + entropy + context), not a certified secret scanner; it will have both false positives and false negatives.
- Dependency analysis is **static manifest inspection only** — it does not check dependencies against any vulnerability database (no CVE lookups) and does not claim to.
- Non-Python source analysis (JS, Go, Rust, etc.) uses line-based heuristics, not a real parser/AST for those languages.
- Git metadata inspection requires a `git` executable on `PATH`; if absent, DevLens falls back to reporting only that a `.git` directory exists.
- Very large repositories (hundreds of thousands of files) will take proportionally longer; there is no incremental/cached scanning yet.

## Future improvements

- Per-language AST-level analysis for JavaScript/TypeScript and Go.
- Configurable scoring weights via a config file.
- Incremental scanning with a local cache keyed by file mtime/hash.
- Optional SARIF output for direct GitHub code-scanning integration.

## License

MIT. See [LICENSE](LICENSE).
