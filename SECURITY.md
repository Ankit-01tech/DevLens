# SECURITY.md — Threat Model and Mitigations

## Scope

DevLens is a static analysis tool that scans a project directory supplied by the user. This document describes the threat model DevLens is designed against and the mitigations implemented for each threat.

## Core assumption: the scanned repository is untrusted

DevLens may be pointed at a repository downloaded from the internet, a student submission, or an unfamiliar third-party codebase. **DevLens treats every file inside the scanned directory as potentially hostile input.** The following hard rules follow from that assumption and are enforced throughout the codebase:

### 1. Scanned source code is never executed

- Python files are analyzed exclusively with `ast.parse()`, which builds a syntax tree without executing any code (`devlens/code_analyzer.py`).
- DevLens never calls `exec()`, `eval()`, `compile()` with execution, `importlib` to import a scanned module, or `subprocess` to run a scanned script.
- Test: `tests/test_code_analyzer.py::test_does_not_execute_python_code` writes a Python file that would create a marker file on disk if executed, then asserts the marker was never created.

### 2. No package installation is ever triggered

- DevLens never invokes `pip`, `npm`, `cargo`, `go`, `mvn`, `gradle`, or any other package manager against the scanned project. Dependency manifests (`requirements.txt`, `package.json`, `Cargo.toml`, `go.mod`, `pom.xml`) are read and parsed as **plain text/JSON**, never executed or installed from.

### 3. Git hooks are never triggered

- `devlens/git_analyzer.py` invokes `git` only via a **fixed allowlist** of three read-only subcommands (`git log -1 ...`, `git branch --show-current`, `git rev-list --count HEAD`). No user-controlled input is ever interpolated into these argument lists. None of these commands trigger Git hooks (which only fire on commit/merge/push-related operations, not on log/branch/rev-list).
- If `git` is not on `PATH`, DevLens falls back to only reporting that a `.git` directory exists, without attempting any command execution.

### 4. Configuration is never evaluated as code

- JSON manifests are parsed with `json.loads` (data-only, no code execution semantics).
- TOML-like manifests are parsed with targeted `re` extraction (see `STDLIB.md`), never with `exec`.

### 5. No untrusted deserialization

- DevLens never calls `pickle.load`/`pickle.loads` on any file, scanned or otherwise. `.pkl`/`.pickle` files, if present, are treated only as opaque binary files for size/duplicate-detection purposes and are never deserialized.

### 6. No remote URLs are followed

- DevLens makes zero network requests during a scan. It does not fetch remote content referenced inside scanned files (e.g. a URL found in a comment or config value).

## Symlink handling

- The filesystem scanner (`devlens/filesystem.py`) does not descend into symlinked directories, which prevents symlink-loop-based denial-of-service or directory-traversal-outside-the-scanned-root attacks.
- Broken symlinks are detected and reported as a low-severity finding rather than raising an unhandled exception.
- Each real (resolved) directory is visited at most once per scan (`_visited_real_dirs`), providing a second layer of loop protection even in unusual symlink topologies.

## Path traversal considerations

- All file paths reported in findings are relative to the scanned root (`FilesystemScanner._relative`), computed via `Path.relative_to()`. DevLens does not follow `..`-style traversal outside the scanned root because `os.walk()` only descends into directories it discovers beneath the root, and symlinked directories are explicitly skipped (see above).

## Denial-of-service via huge files

- `--max-file-size` (default 10 MB) bounds how large a file is analyzed in depth; oversized files are conservatively treated as binary and skipped for text-based analysis (secret scanning, code stats).
- Secret scanning reads at most `MAX_SECRET_SCAN_BYTES` (2 MB) per file regardless of the configured max file size, to bound per-file regex work.
- Duplicate-detection hashing skips files larger than `DUPLICATE_HASH_MAX_BYTES` (50 MB) and uses **chunked, streaming SHA-256 hashing** (`hashlib` + `HASH_CHUNK_SIZE`) rather than loading whole files into memory.

## Malformed input handling

DevLens must not crash because of a single malformed file. Verified behaviors:

- Malformed UTF-8: `safe_read_text` decodes with `errors="replace"`, never raising `UnicodeDecodeError`.
- Malformed JSON (`package.json`): caught and reported as an empty dependency list rather than crashing (`tests/test_dependencies.py::test_malformed_package_json_does_not_crash`).
- Malformed Python syntax: caught by `ast.parse`'s `SyntaxError`, reported as a `MEDIUM` finding, and does not stop the rest of the scan (`tests/test_code_analyzer.py::test_python_syntax_error_recorded_not_crashed`).
- Permission-denied directories/files: `os.walk`'s `onerror` callback records the error and continues; individual file stat/read failures are caught and reported as `unreadable` `FileRecord`s rather than raised.
- Broken symlinks: detected explicitly and reported, not raised.

## Regex abuse considerations (ReDoS)

The secret-scanner regex patterns (`devlens/secret_scanner.py`) are deliberately written to avoid nested-quantifier constructs known to cause catastrophic backtracking (e.g. no `(a+)+` style patterns). Each pattern matches a bounded, well-defined token shape (fixed prefixes like `AKIA`, `sk_live_`, `-----BEGIN`, bounded character classes with explicit length bounds). Per-file input to the secret scanner is additionally capped at 2 MB, limiting the worst-case work of any single regex pass.

## Secrets are never leaked into reports

- The secret scanner's `_safe_evidence()` always replaces the matched secret value with a redacted form (`redact()` in `devlens/utils.py`) before it is stored in a `Finding`. This redaction happens **before** the finding is added to the result — no code path stores the raw matched value anywhere.
- Verified by `tests/test_secrets.py::test_never_reproduces_full_secret`, which asserts the original secret string does not appear anywhere in a finding's serialized form.
- This applies uniformly across the terminal report, JSON report, and CSV report, since all three render from the same `Finding` objects.

## Honesty about detection limits

DevLens does not claim comprehensive secret detection. The scanner is heuristic (pattern matching + entropy scoring + placeholder filtering) and will have false positives and false negatives. Every scan and every relevant document states this explicitly rather than implying a guarantee.

## Reporting a vulnerability in DevLens itself

This is a hackathon submission without a dedicated security contact channel. If you find an issue in DevLens's own handling of untrusted input (e.g. a way to make it execute scanned code, or a way to make the secret redaction fail), please open an issue in the repository describing the reproduction steps.
