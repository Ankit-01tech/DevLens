"""Command-line interface for DevLens."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .constants import VERSION
from .reporters import (
    render_ci_report,
    render_csv_report,
    render_fix_plan,
    render_html_dashboard,
    render_json_report,
    render_text_report,
)
from .scanner import ScanOptions, run_scan
from .terminal import make_palette

EXIT_SUCCESS = 0
EXIT_FINDINGS = 1
EXIT_USAGE_ERROR = 2
EXIT_FATAL_ERROR = 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="devlens",
        description="DevLens - Zero-Dependency Software Supply-Chain & Project Health Scanner.",
    )
    parser.add_argument("path", nargs="?", default=".", help="Path to the project directory to scan (default: current directory).")
    parser.add_argument("--format", choices=["text", "json", "csv"], default="text", help="Report output format.")
    parser.add_argument("--output", metavar="FILE", help="Write the report to a file instead of stdout.")
    parser.add_argument("--verbose", action="store_true", help="Show additional progress detail.")
    parser.add_argument("--no-secrets", action="store_true", help="Disable the secret scanner.")
    parser.add_argument("--no-dependencies", action="store_true", help="Disable dependency manifest analysis.")
    parser.add_argument("--max-file-size", type=float, default=10, metavar="MB", help="Maximum file size (MB) to analyze in depth (default: 10).")
    parser.add_argument("--workers", type=int, default=4, metavar="N", help="Number of worker threads for parallel analysis (default: 4).")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI color output.")
    parser.add_argument("--fix-plan", action="store_true", help="Generate a non-modifying prioritized remediation plan.")
    parser.add_argument("--ci", action="store_true", help="Run in Continuous Integration mode with quality gate reporting.")
    parser.add_argument("--fail-on", choices=["critical", "high", "medium", "low", "info"], help="Fail (exit code 1) if findings match or exceed specified severity.")
    parser.add_argument("--serve", action="store_true", help="Serve an interactive local HTML dashboard instead of printing a report.")
    parser.add_argument("--port", type=int, default=8787, help="Port to use with --serve (default: 8787).")
    parser.add_argument("--version", action="store_true", help="Show the DevLens version and exit.")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(f"DevLens {VERSION}")
        return EXIT_SUCCESS

    target = Path(args.path)
    if not target.exists():
        print(f"Error: path does not exist: {args.path}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    if not target.is_dir():
        print(f"Error: path is not a directory: {args.path}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    if args.workers < 1:
        print("Error: --workers must be at least 1", file=sys.stderr)
        return EXIT_USAGE_ERROR

    palette = make_palette(args.no_color)

    if not args.ci:
        print(palette("DevLens", "bold", "cyan"))
        print(palette("Zero-Dependency Software Health Scanner", "dim"))
        print("-" * 60)
        print(f"\nScanning: {args.path}\n")

    def progress(step: int, total: int, message: str) -> None:
        if not args.ci or args.verbose:
            print(f"[{step}/{total}] {message}")

    options = ScanOptions(
        path=str(target),
        max_file_size_mb=args.max_file_size,
        workers=args.workers,
        enable_secrets=not args.no_secrets,
        enable_dependencies=not args.no_dependencies,
    )

    try:
        result = run_scan(options, progress=progress)
    except Exception as exc:  # noqa: BLE001 - top-level safety net
        print(f"\nFatal error during scan: {exc}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return EXIT_FATAL_ERROR

    if not args.ci:
        print("\nScan complete.\n")

    if args.serve:
        return _serve_dashboard(result, args.port)

    if args.ci:
        rendered = render_ci_report(result, palette, fail_on_sev=args.fail_on)
    elif args.fix_plan:
        rendered = render_fix_plan(result, palette)
    elif args.format == "json":
        rendered = render_json_report(result)
    elif args.format == "csv":
        rendered = render_csv_report(result)
    else:
        rendered = render_text_report(result, palette)

    if args.output:
        try:
            Path(args.output).write_text(rendered, encoding="utf-8")
            print(f"Report written to: {args.output}")
        except OSError as exc:
            print(f"Error writing output file: {exc}", file=sys.stderr)
            return EXIT_FATAL_ERROR
    else:
        print(rendered)

    # Always additionally emit a JSON report next to a text/csv run for
    # machine consumption, matching the documented UX in the README.
    if args.format != "json" and not args.output and not args.ci:
        json_path = Path("devlens-report.json")
        try:
            json_path.write_text(render_json_report(result), encoding="utf-8")
            print(f"Full report: {json_path}")
        except OSError:
            pass

    if args.fail_on:
        from .models import Severity
        target_rank = Severity[args.fail_on.upper()].rank
        if any(f.severity.rank <= target_rank for f in result.findings):
            return EXIT_FINDINGS
        return EXIT_SUCCESS

    if result.findings:
        return EXIT_FINDINGS
    return EXIT_SUCCESS


def _serve_dashboard(result, port: int) -> int:
    import http.server
    import socketserver
    import webbrowser

    html_content = render_html_dashboard(result).encode("utf-8")

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - required method name
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html_content)))
            self.end_headers()
            self.wfile.write(html_content)

        def log_message(self, format, *args):  # noqa: A002 - silence default logging
            pass

    try:
        with socketserver.TCPServer(("127.0.0.1", port), Handler) as httpd:
            url = f"http://127.0.0.1:{port}"
            print(f"Serving DevLens dashboard at {url} (Ctrl+C to stop)")
            try:
                webbrowser.open(url)
            except Exception:
                pass
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        return EXIT_SUCCESS
    except OSError as exc:
        print(f"Could not start local server: {exc}", file=sys.stderr)
        return EXIT_FATAL_ERROR
    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
