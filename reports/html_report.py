"""
Self-contained HTML report generator for the QA Platform.

Produces a single .html file with all screenshots embedded as base64
data URIs — no external dependencies required when sharing the report.
"""

import base64
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from core.models import Run, Result
from core.exceptions import ReportError

logger = logging.getLogger(__name__)

_STATUS_BADGE: dict[str, tuple[str, str]] = {
    "passed":  ("#16a34a", "#dcfce7"),
    "failed":  ("#dc2626", "#fee2e2"),
    "skipped": ("#d97706", "#fef3c7"),
}


def _b64_image(path: str) -> Optional[str]:
    """Return a base64-encoded data URI for an image, or None if not readable."""
    try:
        p = Path(path)
        if not p.exists():
            return None
        mime = "image/webp" if p.suffix.lower() == ".webp" else "image/png"
        data = base64.b64encode(p.read_bytes()).decode()
        return f"data:{mime};base64,{data}"
    except Exception as exc:
        logger.warning(f"Could not embed image {path}: {exc}")
        return None


def _status_badge(status: str) -> str:
    fg, bg = _STATUS_BADGE.get(status, ("#6b7280", "#f3f4f6"))
    return (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:999px;'
        f'font-size:11px;font-weight:700;text-transform:uppercase;'
        f'background:{bg};color:{fg};">{status.upper()}</span>'
    )


def _progress_bar(pct: float) -> str:
    colour = "#16a34a" if pct >= 80 else ("#d97706" if pct >= 50 else "#dc2626")
    return (
        f'<div style="background:#e5e7eb;border-radius:999px;height:10px;overflow:hidden;">'
        f'<div style="width:{pct:.1f}%;height:100%;background:{colour};'
        f'border-radius:999px;transition:width .4s;"></div></div>'
    )


def _css() -> str:
    return """
    <style>
      *{box-sizing:border-box;margin:0;padding:0;}
      body{font-family:'Segoe UI',system-ui,sans-serif;background:#f1f5f9;color:#1e293b;font-size:14px;}
      a{color:#2563eb;text-decoration:none;}
      .container{max-width:1200px;margin:0 auto;padding:40px 24px;}
      .banner{background:linear-gradient(135deg,#1e3a5f,#2563eb);color:#fff;padding:48px 56px;
              border-radius:16px;margin-bottom:32px;position:relative;overflow:hidden;}
      .banner::after{content:'';position:absolute;top:-60px;right:-60px;width:240px;height:240px;
                     border-radius:50%;background:rgba(255,255,255,.06);}
      .banner h1{font-size:28px;font-weight:700;margin-bottom:6px;}
      .banner .meta{font-size:13px;opacity:.75;}
      .kpi-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:20px;margin-bottom:32px;}
      .kpi{background:#fff;border-radius:12px;padding:24px;box-shadow:0 1px 4px rgba(0,0,0,.08);}
      .kpi .label{font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px;}
      .kpi .value{font-size:36px;font-weight:300;letter-spacing:-.02em;}
      .kpi .value.green{color:#16a34a;} .kpi .value.red{color:#dc2626;}
      .kpi .value.amber{color:#d97706;}
      .section{background:#fff;border-radius:12px;box-shadow:0 1px 4px rgba(0,0,0,.08);
               margin-bottom:32px;overflow:hidden;}
      .section-header{padding:20px 24px;border-bottom:1px solid #e2e8f0;font-weight:600;font-size:15px;}
      table{width:100%;border-collapse:collapse;}
      th{padding:12px 16px;text-align:left;font-size:11px;font-weight:700;text-transform:uppercase;
         letter-spacing:.06em;color:#64748b;background:#f8fafc;border-bottom:1px solid #e2e8f0;}
      td{padding:12px 16px;border-bottom:1px solid #f1f5f9;vertical-align:middle;}
      tr:last-child td{border-bottom:none;}
      tr:hover td{background:#fafafa;}
      .mono{font-family:'Cascadia Code','JetBrains Mono',monospace;font-size:12px;}
      .step-num{font-weight:700;color:#1e293b;white-space:nowrap;}
      .ss-thumb{width:160px;height:90px;object-fit:cover;border-radius:6px;
                border:1px solid #e2e8f0;cursor:pointer;transition:transform .2s;}
      .ss-thumb:hover{transform:scale(1.05);}
      .tag{display:inline-block;background:#f1f5f9;border:1px solid #e2e8f0;
           border-radius:4px;padding:1px 6px;font-size:11px;color:#64748b;}
      /* lightbox */
      #lb{display:none;position:fixed;inset:0;background:rgba(0,0,0,.92);z-index:999;
          align-items:center;justify-content:center;}
      #lb.open{display:flex;}
      #lb img{max-width:92vw;max-height:88vh;border-radius:8px;}
      #lb-close{position:absolute;top:16px;right:24px;color:#fff;font-size:28px;cursor:pointer;}
      footer{text-align:center;color:#94a3b8;font-size:12px;margin-top:40px;}
      @media print{
        body{background:#fff;} .section,.banner,.kpi{box-shadow:none;}
        #lb{display:none!important;}
      }
    </style>
    """


def _lightbox_js() -> str:
    return """
    <div id="lb"><span id="lb-close" onclick="document.getElementById('lb').classList.remove('open')">&times;</span>
      <img id="lb-img" src="" alt="screenshot"></div>
    <script>
      function openLb(src){document.getElementById('lb-img').src=src;
        document.getElementById('lb').classList.add('open');}
      document.getElementById('lb').addEventListener('click',function(e){
        if(e.target===this)this.classList.remove('open');});
      document.addEventListener('keydown',function(e){
        if(e.key==='Escape')document.getElementById('lb').classList.remove('open');});
    </script>
    """


def generate_html_report(
    run: Run,
    results: List[Result],
    output_path: Path,
    client_code: Optional[str] = None,
) -> Path:
    """
    Build a self-contained HTML test report with embedded screenshots.

    All screenshots are inlined as base64 data URIs so the report can
    be shared as a single file without any directory structure.

    Args:
        run: Run entity to report on.
        results: Ordered list of Result entities.
        output_path: Destination .html file path.
        client_code: Optional short client code for the banner.

    Returns:
        Path: Saved report file path.
    """
    try:
        passed = run.passed_count
        failed = run.failed_count
        total  = run.step_count
        skipped = max(0, total - passed - failed)
        pct = (passed / total * 100) if total else 0.0
        duration = f"{run.duration_seconds:.1f}s" if run.duration_seconds else "—"
        generated_ts = datetime.now().strftime("%d %b %Y %H:%M UTC")
        started = (run.started_at or run.created_at or "")[:16].replace("T", " ")

        # Build steps HTML
        rows_html = ""
        for res in results:
            status = res.status if isinstance(res.status, str) else res.status.value
            action = res.action.value if hasattr(res.action, "value") else str(res.action)

            ss_html = ""
            if res.screenshot_path:
                src = _b64_image(res.screenshot_path)
                if src:
                    ss_html = (
                        f'<img class="ss-thumb" src="{src}" '
                        f'alt="Step {res.sequence}" onclick="openLb(this.src)">'
                    )
                else:
                    ss_html = '<span class="tag">file missing</span>'

            actual = res.error_message[:200] if res.error_message else (res.actual_value or "")
            selector = res.selector or ""
            duration_ms = res.duration_ms or 0

            rows_html += f"""
            <tr>
              <td class="step-num">#{res.sequence}</td>
              <td><span class="tag mono">{action}</span></td>
              <td>{res.description or ""}</td>
              <td class="mono" style="color:#64748b;font-size:11px;">{selector[:80]}</td>
              <td style="color:#334155;">{res.expected_value or ""}</td>
              <td style="color:#64748b;">{actual}</td>
              <td>{_status_badge(status)}</td>
              <td style="color:#94a3b8;" class="mono">{duration_ms}ms</td>
              <td>{ss_html}</td>
            </tr>"""

        # Metadata rows
        meta_rows = ""
        meta_pairs = [
            ("Run ID",         run.id),
            ("Test ID",        run.test_id),
            ("Client",         client_code or run.pod or "—"),
            ("Consultant",     run.consultant or "—"),
            ("Run Directory",  run.run_dir or "—"),
            ("Video",          run.video_path or "—"),
            ("Trace",          run.trace_path or "—"),
            ("Error",          run.error_message or "—"),
            ("Completed",      run.completed_at or "—"),
        ]
        for k, v in meta_pairs:
            meta_rows += (
                f'<tr><td style="font-weight:600;white-space:nowrap;width:180px;">{k}</td>'
                f'<td class="mono" style="word-break:break-all;">{v}</td></tr>'
            )

        pct_colour = "green" if pct >= 80 else ("amber" if pct >= 50 else "red")

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>QA Report — {run.test_name}</title>
{_css()}
</head>
<body>
{_lightbox_js()}
<div class="container">

  <div class="banner">
    <div class="meta">QA AUTOMATION PLATFORM &nbsp;|&nbsp; Generated {generated_ts}</div>
    <h1>{run.test_name}</h1>
    <div class="meta" style="margin-top:8px;">
      Run ID: {run.id} &nbsp;·&nbsp;
      Client: {client_code or run.pod or "—"} &nbsp;·&nbsp;
      Consultant: {run.consultant or "—"} &nbsp;·&nbsp;
      Started: {started}
    </div>
  </div>

  <div class="kpi-row">
    <div class="kpi">
      <div class="label">Status</div>
      <div class="value" style="font-size:22px;">{_status_badge(run.status.value)}</div>
    </div>
    <div class="kpi">
      <div class="label">Pass Rate</div>
      <div class="value {pct_colour}">{pct:.1f}%</div>
      <div style="margin-top:10px;">{_progress_bar(pct)}</div>
    </div>
    <div class="kpi">
      <div class="label">Total Steps</div>
      <div class="value">{total}</div>
    </div>
    <div class="kpi">
      <div class="label">Passed</div>
      <div class="value green">{passed}</div>
    </div>
    <div class="kpi">
      <div class="label">Failed</div>
      <div class="value red">{failed}</div>
    </div>
    <div class="kpi">
      <div class="label">Skipped</div>
      <div class="value amber">{skipped}</div>
    </div>
    <div class="kpi">
      <div class="label">Duration</div>
      <div class="value" style="font-size:22px;">{duration}</div>
    </div>
  </div>

  <div class="section">
    <div class="section-header">Steps Detail ({total} steps)</div>
    <div style="overflow-x:auto;">
      <table>
        <thead>
          <tr>
            <th>#</th><th>Action</th><th>Description</th>
            <th>Selector</th><th>Expected</th><th>Actual / Error</th>
            <th>Status</th><th>Duration</th><th>Screenshot</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
  </div>

  <div class="section">
    <div class="section-header">Run Metadata</div>
    <table><tbody>{meta_rows}</tbody></table>
  </div>

  <footer>
    QA Automation Platform &nbsp;·&nbsp; Report generated {generated_ts}
  </footer>
</div>
</body>
</html>"""

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        logger.info(f"HTML report saved: {output_path}")
        return output_path

    except Exception as exc:
        raise ReportError(f"Failed to generate HTML report: {exc}") from exc
