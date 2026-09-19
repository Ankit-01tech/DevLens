"""Report rendering: terminal text, JSON, CSV, and a self-contained HTML dashboard."""

from __future__ import annotations

import csv
import html
import io
import json
from typing import List

from .models import ScanResult
from .terminal import Palette


def render_text_report(result: ScanResult, palette: Palette) -> str:
    out = io.StringIO()
    w = out.write
    bar = "=" * 60
    thin = "-" * 60

    w(f"\n{bar}\n")
    w(palette("                 DEV LENS REPORT", "bold", "cyan"))
    w(f"\n{bar}\n\n")

    w(f"Project: {result.project_name}\n")
    w(f"Path: {result.project_path}\n")
    w(f"Detected technologies: {', '.join(result.detected_technologies)}\n")
    w(f"Files scanned: {len(result.files)}\n")
    w(f"Source files: {result.code_stats.source_files}\n")
    w(f"Total lines: {result.code_stats.total_lines:,}\n")
    w(f"Scan duration: {result.scan_duration_seconds:.2f}s\n\n")

    if result.scores:
        s = result.scores
        w("HEALTH SCORE\n")
        w(f"{thin}\n")
        w(f"{'Overall':<28}{_score_str(s.overall, palette)}\n\n")
        w(f"{'Security':<28}{_score_str(s.security, palette)}\n")
        w(f"{'Dependencies':<28}{_score_str(s.dependencies, palette)}\n")
        w(f"{'Code Health':<28}{_score_str(s.code_health, palette)}\n")
        w(f"{'Documentation':<28}{_score_str(s.documentation, palette)}\n")
        w(f"{'Repository Hygiene':<28}{_score_str(s.hygiene, palette)}\n\n")

    counts = result.finding_counts()
    w("FINDINGS\n")
    w(f"{thin}\n\n")
    for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
        w(f"{palette(sev, *_sev_styles(sev)):<28}{counts[sev]}\n")
    w("\n")

    findings = result.sorted_findings()
    current_sev = None
    for f in findings:
        if f.severity.value != current_sev:
            current_sev = f.severity.value
            w(f"\n{palette(current_sev, *_sev_styles(current_sev))}\n")
        loc = f"{f.path}:{f.line}" if f.line else (f.path or "")
        w(f"[{f.id}] {f.title}\n")
        if loc:
            w(f"  File: {loc}\n")
        if f.evidence:
            w(f"  Evidence: {f.evidence}\n")
        if f.explanation:
            w(f"  {f.explanation}\n")

    w(f"\n{thin}\n")
    w("RECOMMENDATIONS\n")
    w(f"{thin}\n")
    for i, rec in enumerate(result.recommendations, start=1):
        w(f"{i}. {rec}\n")

    if result.errors:
        w(f"\n{thin}\n")
        w(f"Scan warnings ({len(result.errors)}):\n")
        for err in result.errors[:10]:
            w(f"  - {err}\n")

    w("\n")
    return out.getvalue()


def _score_str(value: int, palette: Palette) -> str:
    style = "bright_green" if value >= 80 else ("yellow" if value >= 60 else "bright_red")
    return palette(f"{value}/100", style, "bold")


def _sev_styles(sev: str):
    from .terminal import SEVERITY_COLOR
    return (SEVERITY_COLOR.get(sev, "white"), "bold")


def render_json_report(result: ScanResult) -> str:
    return json.dumps(result.to_dict(), indent=2, sort_keys=False)


def render_csv_report(result: ScanResult) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["id", "severity", "category", "title", "path", "line", "explanation", "recommendation"])
    for f in result.sorted_findings():
        writer.writerow([f.id, f.severity.value, f.category, f.title, f.path, f.line or "", f.explanation, f.recommendation])
    writer.writerow([])
    writer.writerow(["summary"])
    writer.writerow(["files_scanned", len(result.files)])
    writer.writerow(["source_files", result.code_stats.source_files])
    writer.writerow(["total_lines", result.code_stats.total_lines])
    if result.scores:
        writer.writerow(["overall_score", result.scores.overall])
        writer.writerow(["security_score", result.scores.security])
        writer.writerow(["dependencies_score", result.scores.dependencies])
        writer.writerow(["code_health_score", result.scores.code_health])
        writer.writerow(["documentation_score", result.scores.documentation])
        writer.writerow(["hygiene_score", result.scores.hygiene])
    return out.getvalue()


def render_fix_plan(result: ScanResult, palette: Palette) -> str:
    out = io.StringIO()
    w = out.write
    bar = "=" * 60
    thin = "-" * 60

    w(f"\n{bar}\n")
    w(palette("            DEV LENS REMEDIATION PLAN", "bold", "cyan"))
    w(f"\n{bar}\n\n")
    w(f"Project: {result.project_name}\n")
    w(f"Target Path: {result.project_path}\n\n")

    sorted_findings = result.sorted_findings()
    if not sorted_findings:
        w("No remediation steps required. Project is clean!\n")
        return out.getvalue()

    for idx, f in enumerate(sorted_findings, start=1):
        sev_label = palette(f.severity.value, *_sev_styles(f.severity.value))
        loc = f"{f.path}:{f.line}" if f.line else (f.path or "Repository-wide")
        w(f"[{idx}] Priority: {sev_label}\n")
        w(f"    Finding:   [{f.id}] {f.title}\n")
        w(f"    Location:  {loc}\n")
        if f.explanation:
            w(f"    Reason:    {f.explanation}\n")
        rec = f.recommendation or "Review and resolve the finding according to project security policies."
        w(f"    Action:    {rec}\n")
        w(f"    {thin}\n")

    return out.getvalue()


def render_ci_report(result: ScanResult, palette: Palette, fail_on_sev: str | None = None) -> str:
    out = io.StringIO()
    w = out.write
    bar = "=" * 60

    w(f"{bar}\n")
    w(palette("DEV LENS CI QUALITY GATE REPORT", "bold", "cyan") + "\n")
    w(f"{bar}\n")
    w(f"Project: {result.project_name}\n")
    w(f"Files Scanned: {len(result.files)}\n")
    if result.scores:
        w(f"Health Score: {result.scores.overall}/100\n")
    w("\nFinding Counts:\n")
    counts = result.finding_counts()
    for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
        w(f"  {sev:<10}: {counts[sev]}\n")

    if fail_on_sev:
        from .models import Severity
        try:
            target_rank = Severity[fail_on_sev.upper()].rank
            breached = any(f.severity.rank <= target_rank for f in result.findings)
            w(f"\nThreshold Level: {fail_on_sev.upper()}\n")
            if breached:
                w(palette("Gate Status: FAIL (findings exceeded threshold)", "bright_red", "bold") + "\n")
            else:
                w(palette("Gate Status: PASS (no findings at or above threshold)", "bright_green", "bold") + "\n")
        except KeyError:
            w("\nGate Status: EVALUATED\n")
    else:
        if result.findings:
            w(palette("\nGate Status: FAIL (findings detected)", "bright_red", "bold") + "\n")
        else:
            w(palette("\nGate Status: PASS (clean scan)", "bright_green", "bold") + "\n")

    w(f"{bar}\n")
    return out.getvalue()



def render_html_dashboard(result: ScanResult) -> str:
    """Render a fully self-contained HTML dashboard: no CDN, no JS framework."""
    esc = html.escape
    scores = result.scores
    findings_rows = "".join(
        f"<tr class='sev-{f.severity.value.lower()}'>"
        f"<td>{esc(f.id)}</td><td>{esc(f.severity.value)}</td><td>{esc(f.category)}</td>"
        f"<td>{esc(f.title)}</td><td>{esc(f.path)}{':' + str(f.line) if f.line else ''}</td>"
        f"<td>{esc(f.explanation)}</td></tr>"
        for f in result.sorted_findings()
    )
    largest_rows = "".join(
        f"<tr><td>{esc(item['path'])}</td><td>{item['size']:,} bytes</td></tr>"
        for item in result.code_stats.largest_files
    )
    dep_rows = "".join(
        f"<tr><td>{esc(d.ecosystem)}</td><td>{esc(d.manifest_file)}</td>"
        f"<td>{len(d.runtime_dependencies)}</td><td>{'Yes' if d.lockfile_present else 'No'}</td></tr>"
        for d in result.dependencies
    )

    score_html = ""
    if scores:
        score_html = f"""
        <div class="score-grid">
          <div class="score-card overall">Overall<span>{scores.overall}</span></div>
          <div class="score-card">Security<span>{scores.security}</span></div>
          <div class="score-card">Dependencies<span>{scores.dependencies}</span></div>
          <div class="score-card">Code Health<span>{scores.code_health}</span></div>
          <div class="score-card">Documentation<span>{scores.documentation}</span></div>
          <div class="score-card">Hygiene<span>{scores.hygiene}</span></div>
        </div>
        """

    counts = result.finding_counts()
    count_html = "".join(
        f"<span class='badge sev-{k.lower()}'>{k}: {v}</span>" for k, v in counts.items()
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>DevLens Report - {esc(result.project_name)}</title>
<style>
  :root {{ --bg:#0f1117; --panel:#171a23; --text:#e6e6e6; --muted:#9aa0ac; --accent:#4fd1c5; }}
  * {{ box-sizing: border-box; }}
  body {{ background: var(--bg); color: var(--text); font-family: -apple-system, Segoe UI, Helvetica, Arial, sans-serif; margin:0; padding: 2rem; }}
  h1 {{ margin-bottom: 0.2rem; }}
  .muted {{ color: var(--muted); }}
  .score-grid {{ display: flex; gap: 1rem; flex-wrap: wrap; margin: 1.5rem 0; }}
  .score-card {{ background: var(--panel); border-radius: 10px; padding: 1rem 1.5rem; min-width: 130px; }}
  .score-card span {{ display:block; font-size: 2rem; font-weight: 700; color: var(--accent); }}
  .score-card.overall span {{ color: #ffd166; }}
  table {{ width: 100%; border-collapse: collapse; margin: 1rem 0 2rem; background: var(--panel); border-radius: 8px; overflow: hidden; }}
  th, td {{ text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid #2a2e3a; font-size: 0.9rem; }}
  th {{ color: var(--muted); text-transform: uppercase; font-size: 0.75rem; }}
  .badge {{ display:inline-block; padding: 0.2rem 0.6rem; border-radius: 12px; margin-right: 0.4rem; font-size: 0.8rem; }}
  .sev-critical {{ background: #4a1620; color: #ff6b81; }}
  .sev-high {{ background: #4a2a16; color: #ff9f5b; }}
  .sev-medium {{ background: #4a4416; color: #ffe066; }}
  .sev-low {{ background: #16344a; color: #6ec6ff; }}
  .sev-info {{ background: #22262f; color: #9aa0ac; }}
  section {{ margin-bottom: 2.5rem; }}
</style>
</head>
<body>
  <h1>DevLens Report</h1>
  <p class="muted">{esc(result.project_name)} &middot; {esc(result.project_path)} &middot; {len(result.files)} files scanned</p>

  {score_html}

  <section>
    <h2>Findings</h2>
    <div>{count_html}</div>
    <table>
      <tr><th>ID</th><th>Severity</th><th>Category</th><th>Title</th><th>Location</th><th>Explanation</th></tr>
      {findings_rows if findings_rows else "<tr><td colspan='6'>No findings.</td></tr>"}
    </table>
  </section>

  <section>
    <h2>Dependencies</h2>
    <table>
      <tr><th>Ecosystem</th><th>Manifest</th><th>Runtime deps</th><th>Lockfile</th></tr>
      {dep_rows if dep_rows else "<tr><td colspan='4'>No dependency manifests detected.</td></tr>"}
    </table>
  </section>

  <section>
    <h2>Largest Files</h2>
    <table>
      <tr><th>Path</th><th>Size</th></tr>
      {largest_rows if largest_rows else "<tr><td colspan='2'>No source files found.</td></tr>"}
    </table>
  </section>

  <p class="muted">Generated locally by DevLens. No source code was uploaded or transmitted anywhere.</p>
</body>
</html>
"""
