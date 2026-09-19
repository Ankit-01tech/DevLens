# STDLIB.md — Standard-Library Substitution Log

DevLens is built with **zero third-party runtime dependencies**. This document lists every meaningful place where DevLens implements functionality that would normally come from a third-party package, and explains what standard-library module was used instead and what the trade-offs are.

Only substitutions that are actually exercised by implemented DevLens code are listed here — nothing below is aspirational.

| # | Normally used | Why developers reach for it | DevLens replacement | Where in DevLens | Trade-off |
|---|---|---|---|---|---|
| 1 | **Click / Typer** | Ergonomic CLI argument parsing, subcommands, auto-generated help | `argparse` | `devlens/cli.py` | `argparse` is more verbose for subcommands, but DevLens has a single flat command surface, so this is a non-issue in practice. |
| 2 | **Rich** | Colored terminal output, progress bars, tables | Raw ANSI escape codes + `sys.stdout.isatty()` detection | `devlens/terminal.py` | We lose Rich's automatic terminal-width-aware tables and live progress bars; DevLens uses simple numbered `[n/8]` step lines instead, which degrades gracefully on any terminal. |
| 3 | **Colorama** | Cross-platform ANSI color support on Windows | Standard ANSI codes with a `--no-color` flag and `NO_COLOR`/`TERM=dumb` env detection | `devlens/terminal.py` | Modern Windows Terminal/PowerShell support ANSI natively; older `cmd.exe` may render escape codes literally. The `--no-color` flag exists specifically to work around this. |
| 4 | **Requests** | Making HTTP calls | Not needed — DevLens performs zero network requests by design (`urllib` would be the stdlib substitute if any were ever added) | N/A | DevLens's local-first design means there is no HTTP client requirement at all; this is a design choice, not a workaround. |
| 5 | **Flask / FastAPI** | Serving a small local web dashboard | `http.server.BaseHTTPRequestHandler` + `socketserver.TCPServer` | `devlens/cli.py` (`_serve_dashboard`) | No routing, templating engine, or middleware — but DevLens's dashboard is a single static page, so a full web framework would be pure overhead. |
| 6 | **Jinja2 / other templating** | Generating HTML | Python f-strings with `html.escape()` for safe interpolation | `devlens/reporters.py` (`render_html_dashboard`) | No template inheritance or macros, but the dashboard is one self-contained page, so plain string building is simpler and has zero XSS risk once escaping is applied consistently. |
| 7 | **PyYAML** | Parsing YAML config/CI files | Not required for DevLens's own operation; where YAML-adjacent files are merely *detected* (e.g. `.github/workflows`), only file *presence* is checked via `pathlib`, not full parsing | `devlens/hygiene.py` | If DevLens ever needed to parse YAML content (not just detect file presence), a hand-rolled parser would be needed since PyYAML is off-limits — this is flagged as a known limitation rather than attempted partially. |
| 8 | **toml / tomllib usage beyond stdlib** | Parsing `pyproject.toml` / `Cargo.toml` | Targeted `re`-based extraction of just the `dependencies = [...]` arrays and `[dependencies]` tables actually needed | `devlens/dependency_analyzer.py` | This is not a general-purpose TOML parser — it only extracts dependency arrays/tables, and is explicit about that limitation rather than silently mis-parsing edge cases. (Python 3.11+ ships `tomllib` in the stdlib for *reading* full TOML, but a full parse isn't needed for the narrow extraction DevLens performs.) |
| 9 | **GitPython** | Reading git history/branch/commit metadata | `subprocess` with a fixed, read-only allowlist of `git` arguments (`git log -1`, `git branch --show-current`, `git rev-list --count HEAD`) | `devlens/git_analyzer.py` | No object-model API for walking commits/trees — DevLens only needs a few summary facts, so three tightly-scoped subprocess calls are simpler and avoid pulling in a full git object database reader. |
| 10 | **Pandas** | Tabular data manipulation, CSV export | `csv` module + built-in `dict`/`list` aggregation | `devlens/reporters.py` (`render_csv_report`) | No DataFrame joins/pivoting, but DevLens's tabular output (a findings table and a summary block) doesn't need them. |
| 11 | **SQLAlchemy** | Database abstraction | Not used — DevLens is a stateless CLI scanner with no persistent database. If DevLens ever added a local result cache, `sqlite3` (stdlib) would be the substitute. | N/A | No ORM convenience, but there's no database requirement in the current feature set. |
| 12 | **pytest** | Test running, fixtures, parametrization | `unittest` (including `unittest.mock`-style patterns where needed) | `tests/*.py` | No `@pytest.fixture` / `@pytest.mark.parametrize` sugar — tests use plain `setUp`/`tearDown` and explicit loops, which is slightly more verbose but requires zero installation to run: `python -m unittest discover`. |
| 13 | **zipapp / wheel build tools** | Building reproducible executable Python bundles | `zipfile` with explicit timestamp and permission normalization (`FIXED_ZIP_DATE = (2026, 1, 1, 0, 0, 0)`) | `tools/reproducible_build.py` | No reliance on complex third-party build hooks; produces 100% byte-identical executable `.pyz` packages deterministically. |

## Package Killer — focused replacement

Rather than making generic claims, DevLens implements focused replacements for key third-party packages that CLI security tools typically rely upon:

### 1. Primary Target: `Rich` (Terminal Formatting & Styling)
- **Package Replaced**: `rich` (`rich.console.Console`, `rich.style.Style`, `rich.text.Text`)
- **Specific Capability Replaced**: ANSI terminal color palettes, severity level color coding, automatic `NO_COLOR` / `TERM=dumb` environment fallback, plain-text auto-detection via `sys.stdout.isatty()`, and formatted text report layouts.
- **Why Sufficient**: DevLens requires consistent, color-coded terminal reports with zero external dependencies. Standard ANSI sequence handling in `devlens/terminal.py` fulfills all terminal formatting needs cleanly.
- **Standard-Library Implementation**: `devlens/terminal.py` (`Palette`, `make_palette()`, `color_enabled()`) + `devlens/reporters.py` (`render_text_report()`, `render_fix_plan()`, `render_ci_report()`).
- **Relevant Source Files**: `devlens/terminal.py`, `devlens/reporters.py`.
- **Trade-offs**: Text width wrapping and full table layouts are formatted manually rather than dynamically calculated by Rich's render engine.
- **What is NOT Implemented**: Live animated progress bars, markdown terminal rendering, rich tree views, HTML export from rich renderables.

### 2. Secondary Target: `GitPython` (Read-only Repository Inspection)
- **Package Replaced**: `gitpython` (`git.Repo`)
- **Specific Capability Replaced**: Extracting current branch name, last commit hash/author/date, and total commit count.
- **Why Sufficient**: DevLens only needs top-level repository inspection metadata for hygiene reports; it does not perform Git object tree traversals or branch management.
- **Standard-Library Implementation**: `subprocess.run()` invoking a fixed, read-only allowlist of `git` CLI subcommands (`git branch --show-current`, `git log -1`, `git rev-list --count HEAD`).
- **Relevant Source Files**: `devlens/git_analyzer.py`.
- **Trade-offs**: Requires `git` executable on `PATH`; falls back gracefully to `.git` directory presence check if binary is missing.
- **What is NOT Implemented**: Commit tree walking, git object parsing, diff generation, push/pull operations.

### 3. Secondary Target: `Click` / `Typer` (CLI Parsing & Quality Gates)
- **Package Replaced**: `click` / `typer`
- **Specific Capability Replaced**: Command-line option parsing, type conversion, help formatting, `--version`, `--format`, `--fix-plan`, `--ci`, and `--fail-on` flag handling with explicit exit codes.
- **Why Sufficient**: DevLens has a clean, focused single-command CLI interface. Standard library `argparse` is completely sufficient.
- **Standard-Library Implementation**: `argparse.ArgumentParser` in `devlens/cli.py`.
- **Relevant Source Files**: `devlens/cli.py`.
- **Trade-offs**: Slightly more verbose parser setup code.
- **What is NOT Implemented**: Nestable subcommand hierarchies, decorator-based command routing, shell completion generation.

---

## Development & Build Tooling Disclosure

As required by hackathon rules, all development-only and build-time tooling is disclosed below:

- **`setuptools` (`pyproject.toml`)**: Declared under `[build-system]` (`requires = ["setuptools>=68"]`) solely for standard Python package packaging (`pip install -e .` or wheel building).
  - **Development / Build-only**: Yes.
  - **Not a Runtime Dependency**: DevLens has **zero runtime dependencies**.
  - **Not Imported at Runtime**: `setuptools` is never imported by `devlens` or `devlens_single.py`.
  - **Execution**: Running `python3 devlens.py <path>` or `python3 devlens_single.py <path>` does **not** require `setuptools`.

---

## What is genuinely *not* replaced

To be honest about scope: DevLens does not attempt to reimplement a full YAML parser (it checks CI file presence via `pathlib`), a full TOML parser (uses targeted regex for dependency arrays in `pyproject.toml`), a real online vulnerability/CVE database client, or per-language AST parsers for JavaScript/Go/Rust/Java (uses line-based heuristics). These are documented as explicit limitations in `README.md`.
