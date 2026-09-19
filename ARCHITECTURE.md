# ARCHITECTURE.md

## Components

```
                          ┌─────────────────┐
                          │   cli.py         │  argparse, exit codes,
                          │                  │  --serve HTTP server
                          └────────┬─────────┘
                                   │
                          ┌────────▼─────────┐
                          │  scanner.py       │  orchestration pipeline
                          └────────┬─────────┘
              ┌───────────┬────────┼────────┬───────────┬────────────┐
              ▼           ▼        ▼         ▼           ▼            ▼
     filesystem.py  project_    dependency_ secret_   code_       hygiene.py /
                    detector.py analyzer.py scanner.py analyzer.py documentation.py
              │           │        │         │           │            │
              └───────────┴────────┴─────────┴───────────┴────────────┘
                                   │
                          ┌────────▼─────────┐
                          │  scoring.py       │  deterministic, weighted
                          │  recommendations  │  score + advice
                          └────────┬─────────┘
                                   │
                          ┌────────▼─────────┐
                          │  reporters.py     │  text / json / csv / html
                          └──────────────────┘
```

All modules communicate through plain dataclasses defined in `models.py` (`FileRecord`, `Finding`, `CodeStats`, `DependencyInfo`, `ScoreBreakdown`, `ScanResult`). Nothing downstream of `scanner.py` depends on filesystem paths directly — every module works off the already-collected `List[FileRecord]` and produces `Finding` objects.

## Data flow (scan pipeline)

1. **Discovery** (`filesystem.py`): recursively walk the target directory, honoring ignore rules, hidden-file settings, and symlink-loop protection. Produces `List[FileRecord]` with size, extension, binary/source classification.
2. **Project detection** (`project_detector.py`): check for marker files (`pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `pom.xml`, `CMakeLists.txt`, ...) to label detected ecosystems.
3. **Dependency analysis** (`dependency_analyzer.py`): for each detected manifest, run a small targeted parser (JSON for `package.json`, regex-based extraction for `pyproject.toml`/`Cargo.toml`, structured line parsing for `go.mod`, regex for `pom.xml`) to produce `DependencyInfo` records.
4. **Secret scanning** (`secret_scanner.py`): for every non-binary, readable file, run a set of `SecretRule`s (regex + entropy + placeholder filtering) over its contents. Findings are emitted with **redacted** evidence only. This step runs in parallel across files via a bounded `ThreadPoolExecutor`.
5. **Code analysis** (`code_analyzer.py`): compute line-based statistics (blank/comment/code lines, TODO/FIXME/XXX counts, long lines) for every source file; additionally run `ast.parse()` on Python files to count functions/classes/imports, detect syntax errors, and estimate nesting depth — all without executing any code.
6. **Hygiene checks** (`hygiene.py`): check for README/LICENSE/.gitignore/CI config/tests, flag risky file extensions (`.pem`, `.key`, database dumps, etc.), flag oversized committed files, and compute duplicate-file groups via streaming SHA-256 hashing.
7. **Git inspection** (`git_analyzer.py`): if a `.git` directory exists, safely query branch/last-commit/commit-count via a fixed, read-only subprocess allowlist.
8. **Documentation evaluation** (`documentation.py`): locate a README, measure its length, and check for the presence of common sections (installation, usage, license, etc.) to produce a documentation quality score.
9. **Scoring** (`scoring.py`): map every `Finding` to one of five dimensions (Security, Dependencies, Code Health, Documentation, Repository Hygiene) via its `category`, apply a severity-based point deduction per finding, and combine the five dimension scores into a weighted overall score. Every deduction is recorded in a human-readable `reasons` list.
10. **Recommendations** (`recommendations.py`): take the sorted, de-duplicated set of non-INFO findings and produce a short, prioritized list of recommendation strings.
11. **Reporting** (`reporters.py`): render the final `ScanResult` as terminal text (with ANSI styling via `terminal.py`), JSON, CSV, or a self-contained HTML dashboard.

## Concurrency model

Secret scanning is the only step parallelized across a thread pool (`concurrent.futures.ThreadPoolExecutor`, size controlled by `--workers`), because it is the most I/O-heavy per-file operation (reading up to 2 MB per file and running several regex passes) and each file is fully independent of every other file.

Threads (not processes) were chosen because:

- The work is dominated by file I/O and regex matching, not CPU-bound number crunching, so the GIL is released during I/O and threads provide real concurrency benefit without multiprocessing's pickling/IPC overhead.
- `ThreadPoolExecutor` requires zero extra memory-management complexity (no shared-memory setup) compared to `ProcessPoolExecutor`, keeping the implementation simple and dependency-free.

**Determinism guarantee:** results are always collected via `as_completed()` into a list and then the overall `ScanResult.findings` are sorted deterministically by `(severity.rank, category, path, line, id)` before rendering (`ScanResult.sorted_findings()`). This means scan output is identical across runs regardless of which thread happens to finish first — verified by `tools/reproducibility_check.py` and `tests/test_scoring.py::test_scores_are_deterministic`.

Exceptions raised inside a single worker (e.g. an unexpected file read failure) are caught per-future and simply skipped, so one bad file can never abort the whole scan (see `scanner.py::_scan_secrets`).

## Scoring algorithm

Each of the five dimensions starts at a perfect 100 and is reduced by a fixed penalty per finding, based on severity:

| Severity | Penalty |
|---|---|
| CRITICAL | -25 |
| HIGH | -12 |
| MEDIUM | -6 |
| LOW | -2 |
| INFO | 0 |

The Documentation dimension additionally blends in a measured README-quality heuristic score (length + section coverage) via `min(finding_penalty_score, doc_heuristic_score)`.

The overall score is a weighted sum of the five dimension scores:

| Dimension | Weight |
|---|---|
| Security | 30% |
| Code Health | 25% |
| Documentation | 15% |
| Dependencies | 15% |
| Repository Hygiene | 15% |

All weights are defined in `constants.DEFAULT_SCORE_WEIGHTS` and are passed explicitly into `scoring.compute_scores()`, so they can be overridden by any future caller without touching the scoring logic itself.

## Security boundaries

See [SECURITY.md](SECURITY.md) for the full threat model. In short: scanned code is never executed, scanned dependency manifests are never installed, `git` is invoked only via a fixed read-only argument allowlist, and detected secrets are redacted before they ever reach a `Finding` object — meaning no downstream reporter can accidentally leak a raw secret even if it wanted to.

## Error handling philosophy

Every layer that touches the filesystem (discovery, hashing, text reading, git subprocess calls) catches `OSError`/`subprocess.SubprocessError` locally and degrades gracefully (skip the file, record an error string, mark a `FileRecord` as `unreadable`) rather than propagating an exception up through the pipeline. The only place a top-level exception is caught is `cli.py::main()`, which converts any truly unexpected failure into exit code `3` with a clear message, optionally with a full traceback under `--verbose`.

## Reporting pipeline

`ScanResult.to_dict()` is the single source of truth for the JSON/CSV structure — the text renderer (`render_text_report`) and HTML renderer (`render_html_dashboard`) both read from the same `ScanResult` object (via `sorted_findings()`, `finding_counts()`, etc.), so all four output formats are guaranteed to reflect identical underlying data.
