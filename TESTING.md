# TESTING.md

## Running the tests

DevLens's test suite uses only `unittest` from the standard library — no `pytest`, no test plugins.

```bash
python -m unittest discover -v
```

Run a single file:

```bash
python -m unittest tests.test_secrets -v
```

Run a single test:

```bash
python -m unittest tests.test_secrets.TestSecretScanner.test_detects_aws_key -v
```

## Test architecture

| File | Covers |
|---|---|
| `tests/test_filesystem.py` | Recursive discovery, default/custom ignore rules, symlink loop protection, broken symlinks, binary detection, oversized-file handling, permission errors |
| `tests/test_dependencies.py` | `requirements.txt`, `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `pom.xml` parsing; malformed-JSON resilience; duplicate/pinned detection |
| `tests/test_secrets.py` | AWS/Stripe/private-key/DB-connection-string detection, placeholder filtering, short-value filtering, line-number accuracy, and the hard guarantee that raw secret values never appear in any finding |
| `tests/test_code_analyzer.py` | Line/blank/comment counting, TODO/FIXME/XXX markers, Python AST function/class counting, syntax-error handling, **non-execution of scanned code**, long-line detection, largest-file ranking |
| `tests/test_scoring.py` | Perfect scores with no findings, severity-based penalties, score floor at 0, weighted overall calculation, determinism across repeated calls |
| `tests/test_reporters.py` | JSON/CSV/text/HTML rendering correctness, HTML escaping (XSS safety), color-disabled plain output, deterministic severity ordering |
| `tests/test_cli.py` | Version flag, invalid path/argument handling, exit codes, `--no-secrets`/`--no-dependencies` flag behavior, JSON file output |
| `tests/test_fix_plan_and_ci.py` | `--fix-plan` rendering, `--ci` quality gate output, `--fail-on` exit code logic across all severity levels |
| `tests/test_reproducible_build.py` | Automated verification of `tools/reproducible_build.py` producing byte-identical zipapp artifacts |
| `tests/test_dependency_check_tool.py` | Zero-dependency verification of DevLens itself and detection of adversarial third-party imports (`requests`, `flask`, `pandas`, `numpy`, `rich`, `sqlalchemy`) |

Test fixtures are created on the fly using `tempfile.TemporaryDirectory()` rather than checked-in fixture files, which keeps every test hermetic and avoids accidentally committing fake-but-realistic-looking secrets into the repository itself.

## Notable edge cases explicitly tested

- **Symlink loops**: a directory containing a symlink back to an ancestor must not cause infinite recursion (`test_filesystem.py::test_does_not_follow_symlink_loop`).
- **Broken symlinks**: reported as an `unreadable` file record, not raised as an exception.
- **Malformed JSON manifests**: `package.json` with invalid JSON returns an empty dependency list instead of crashing.
- **Malformed Python syntax**: recorded as a `MEDIUM` finding; the rest of the scan continues normally.
- **Never executing scanned code**: a Python fixture file that would write a marker file to disk if executed is analyzed, and the test asserts the marker file was never created.
- **Never leaking raw secrets**: every secret-scanner test that produces a finding also asserts the original secret string is absent from the finding's full serialized form.
- **Determinism**: scoring and full-scan reproducibility (`tools/reproducibility_check.py`) are both explicitly verified — the same input always produces the same output, independent of thread completion order.
- **Permission-denied directories**: a directory with `chmod 000` must not raise an unhandled exception during discovery.

## Known limitations of the test suite

- Symlink-related tests are skipped automatically on platforms/environments where `os.symlink` raises `OSError`/`NotImplementedError` (e.g. some restricted sandboxes or Windows without developer mode) — this is handled via `self.skipTest(...)`, not silently ignored.
- The permission-denied test restores permissions in a `finally` block, but on some CI runners running as root, `chmod 000` may not actually block reads; the test only asserts that the scan doesn't crash, not that the file is necessarily excluded.
- Concurrency-specific behavior (thread pool sizing, `as_completed` ordering) is validated indirectly through the determinism tests rather than through direct thread-count assertions, since asserting exact concurrency behavior is inherently timing-sensitive.
