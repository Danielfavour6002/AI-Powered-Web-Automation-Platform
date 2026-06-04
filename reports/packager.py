"""
Documentation packaging: assembles a complete run delivery ZIP.

ZIP structure:
    <client>_<testname>_<ts>/
        executive_summary.xlsx     — Excel report
        executive_summary.html     — Standalone HTML report
        screenshots/               — All captured screenshots
        video/                     — Screen recording (if exists)
        trace/                     — Playwright trace archive (if exists)
        manifest.json              — Machine-readable run metadata
"""

import json
import logging
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from core.models import Run, Result
from core.exceptions import ReportError
from reports.excel_report import generate_excel_report, build_report_filename
from reports.html_report import generate_html_report

logger = logging.getLogger(__name__)


def _safe_arcname(name: str) -> str:
    """Strip potentially dangerous path components from archive names."""
    return Path(name).name


def _build_manifest(run: Run, results: List[Result], client_code: str) -> dict:
    """Build a machine-readable manifest dict for the delivery ZIP."""
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "client_code": client_code,
        "run": {
            "id":               run.id,
            "test_name":        run.test_name,
            "test_id":          run.test_id,
            "status":           run.status.value,
            "started_at":       run.started_at,
            "completed_at":     run.completed_at,
            "duration_seconds": run.duration_seconds,
            "consultant":       run.consultant,
            "pod":              run.pod,
            "step_count":       run.step_count,
            "passed_count":     run.passed_count,
            "failed_count":     run.failed_count,
            "pass_rate_pct":    round(
                (run.passed_count / run.step_count * 100) if run.step_count else 0, 2
            ),
            "error_message":    run.error_message,
        },
        "steps": [
            {
                "sequence":     r.sequence,
                "action":       r.action.value if hasattr(r.action, "value") else str(r.action),
                "description":  r.description,
                "status":       r.status if isinstance(r.status, str) else r.status.value,
                "duration_ms":  r.duration_ms,
                "has_screenshot": bool(r.screenshot_path),
            }
            for r in results
        ],
    }


def build_delivery_zip(
    run: Run,
    results: List[Result],
    output_dir: Path,
    client_code: Optional[str] = None,
    tmp_dir: Optional[Path] = None,
) -> Path:
    """
    Assemble and return a complete delivery ZIP for a finished test run.

    The ZIP contains the Excel report, standalone HTML report, all
    screenshots, the video / trace files when present, and a JSON
    manifest. Every file is placed under a single top-level folder
    named ``<ClientCode>_<TestName>_<Timestamp>``.

    Args:
        run: Completed Run entity.
        results: Ordered list of Result entities for this run.
        output_dir: Directory in which to write the output .zip file.
        client_code: Short client identifier (falls back to run.pod).
        tmp_dir: Optional directory for staging intermediate reports.
                 If omitted, ``output_dir`` is used.

    Returns:
        Path: Absolute path of the created ``.zip`` file.

    Raises:
        ReportError: On any failure during report or archive creation.
    """
    try:
        code = client_code or run.pod or "QA"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in run.test_name)[:40]
        safe_code = "".join(c if c.isalnum() else "_" for c in code)[:10]
        folder_name = f"{safe_code}_{safe_name}_{ts}"

        output_dir.mkdir(parents=True, exist_ok=True)
        staging = tmp_dir or output_dir
        staging.mkdir(parents=True, exist_ok=True)

        zip_path = output_dir / f"{folder_name}.zip"

        # ── Generate intermediate reports ─────────────────────────────────────
        xlsx_filename = build_report_filename(code, run.test_name, ts)
        xlsx_path = staging / xlsx_filename
        generate_excel_report(run, results, xlsx_path, client_code=code)

        html_filename = xlsx_filename.replace(".xlsx", ".html")
        html_path = staging / html_filename
        generate_html_report(run, results, html_path, client_code=code)

        manifest_path = staging / "manifest.json"
        manifest_path.write_text(
            json.dumps(_build_manifest(run, results, code), indent=2, default=str),
            encoding="utf-8",
        )

        # ── Assemble ZIP ──────────────────────────────────────────────────────
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
            # Reports
            zf.write(xlsx_path, f"{folder_name}/executive_summary.xlsx")
            zf.write(html_path, f"{folder_name}/executive_summary.html")
            zf.write(manifest_path, f"{folder_name}/manifest.json")

            # Screenshots
            screenshots_added = 0
            for res in results:
                if res.screenshot_path:
                    ss = Path(res.screenshot_path)
                    if ss.exists():
                        arcname = f"{folder_name}/screenshots/{ss.name}"
                        zf.write(str(ss), arcname)
                        screenshots_added += 1

            # Video
            if run.video_path:
                vp = Path(run.video_path)
                if vp.exists():
                    zf.write(str(vp), f"{folder_name}/video/{vp.name}")

            # Playwright trace
            if run.trace_path:
                tp = Path(run.trace_path)
                if tp.exists():
                    zf.write(str(tp), f"{folder_name}/trace/{tp.name}")

        logger.info(
            f"Delivery ZIP assembled: {zip_path} "
            f"({screenshots_added} screenshots, video={'yes' if run.video_path else 'no'})"
        )

        # Clean up staging files (don't raise on failure)
        for tmp in (xlsx_path, html_path, manifest_path):
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass

        return zip_path

    except ReportError:
        raise
    except Exception as exc:
        raise ReportError(f"Failed to build delivery ZIP: {exc}") from exc
