"""
Reports API routes for QA Platform.

All endpoints derive configuration from the application's database-backed
config (via ``request.app.state``); no static ``.env`` lookups occur here.
"""

import logging
import shutil
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from core import database
from core.exceptions import ReportError
from reports.excel_report import generate_excel_report, build_report_filename
from reports.html_report import generate_html_report
from reports.packager import build_delivery_zip
from reports.docx_report import generate_docx_report
from reports.allure_report import get_allure_results_dir, get_allure_report_response
from reports.excel_importer import list_excel_scenarios, import_excel_steps

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _db_path(request: Request) -> Path:
    return request.app.state.db_path


def _output_dir(request: Request) -> Path:
    # Config uses output_root, not output_dir
    return Path(request.app.state.config.output_root)


async def _fetch_run_and_results(db_path: Path, run_id: str):
    run = await database.get_run(db_path, run_id)
    results = await database.get_results_for_run(db_path, run_id)
    return run, results


def _run_dir(run, output_dir: Path) -> Path:
    """Return the run directory, creating it if necessary."""
    d = Path(run.run_dir) if run.run_dir else output_dir / run.id
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Excel report ──────────────────────────────────────────────────────────────

@router.get("/reports/{run_id}/excel")
async def get_excel_report(request: Request, run_id: str) -> FileResponse:
    """
    Generate and stream an Excel (.xlsx) test-run report.

    The report includes an Executive Summary tab, a colour-coded Steps
    Detail tab with embedded screenshots, and a Metadata tab.
    """
    db_path = _db_path(request)
    try:
        run, results = await _fetch_run_and_results(db_path, run_id)
        run_d = _run_dir(run, _output_dir(request))
        filename = build_report_filename(run.pod or "QA", run.test_name)
        xlsx_path = run_d / filename
        generate_excel_report(run, results, xlsx_path, client_code=run.pod)
        return FileResponse(
            path=xlsx_path,
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ReportError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        logger.exception(f"Excel report failed for run {run_id}")
        raise HTTPException(status_code=500, detail="Report generation failed")


# ── HTML report ───────────────────────────────────────────────────────────────

@router.get("/reports/{run_id}/html")
async def get_html_report(request: Request, run_id: str) -> FileResponse:
    """
    Generate and stream a self-contained HTML test-run report.

    All screenshots are embedded as base64 data URIs so the report is
    fully portable as a single file.
    """
    db_path = _db_path(request)
    try:
        run, results = await _fetch_run_and_results(db_path, run_id)
        run_d = _run_dir(run, _output_dir(request))
        filename = build_report_filename(run.pod or "QA", run.test_name).replace(".xlsx", ".html")
        html_path = run_d / filename
        generate_html_report(run, results, html_path, client_code=run.pod)
        return FileResponse(
            path=html_path,
            filename=filename,
            media_type="text/html",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ReportError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        logger.exception(f"HTML report failed for run {run_id}")
        raise HTTPException(status_code=500, detail="Report generation failed")


# ── DOCX report ───────────────────────────────────────────────────────────────

@router.get("/reports/{run_id}/docx")
async def get_docx_report(request: Request, run_id: str) -> FileResponse:
    """Generate and stream a Word (.docx) test-run report."""
    db_path = _db_path(request)
    try:
        run, results = await _fetch_run_and_results(db_path, run_id)
        run_d = _run_dir(run, _output_dir(request))
        screenshots_dir = run_d / "screenshots"
        filename = f"Report_{run.test_name[:40]}_{run.created_at[:10]}.docx".replace(" ", "_")
        docx_path = run_d / filename
        generate_docx_report(run, results, screenshots_dir, docx_path)
        return FileResponse(
            path=docx_path,
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ReportError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        logger.exception(f"DOCX report failed for run {run_id}")
        raise HTTPException(status_code=500, detail="Report generation failed")


# ── Allure HTML report ────────────────────────────────────────────────────────

@router.get("/reports/{run_id}/allure")
async def get_allure_report(request: Request, run_id: str) -> FileResponse:
    """Serve the Allure HTML report index page for a run."""
    db_path = _db_path(request)
    try:
        run, results = await _fetch_run_and_results(db_path, run_id)
        run_d = _run_dir(run, _output_dir(request))
        allure_dir = get_allure_results_dir(run_d)
        index_path = get_allure_report_response(run, results, allure_dir)
        return FileResponse(path=index_path, media_type="text/html")
    except Exception as exc:
        logger.exception(f"Allure report failed for run {run_id}")
        raise HTTPException(status_code=500, detail=str(exc))


# ── Delivery ZIP ──────────────────────────────────────────────────────────────

@router.get("/reports/{run_id}/zip")
async def get_delivery_zip(request: Request, run_id: str) -> FileResponse:
    """
    Build and stream a complete client delivery ZIP package.

    The archive includes the Excel report, self-contained HTML report,
    all screenshots, video/trace files, and a machine-readable manifest.
    """
    db_path = _db_path(request)
    try:
        run, results = await _fetch_run_and_results(db_path, run_id)
        output_dir = _output_dir(request)
        run_d = _run_dir(run, output_dir)
        zip_path = build_delivery_zip(
            run,
            results,
            output_dir=run_d,
            client_code=run.pod,
            tmp_dir=run_d / "_tmp",
        )
        return FileResponse(
            path=zip_path,
            filename=zip_path.name,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{zip_path.name}"'},
        )
    except ReportError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        logger.exception(f"Delivery ZIP failed for run {run_id}")
        raise HTTPException(status_code=500, detail="Package assembly failed")


# ── Excel import ──────────────────────────────────────────────────────────────

@router.post("/reports/import-excel")
async def import_excel_upload(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Upload an Excel test definition workbook and return a scenario preview.

    Responds with a list of sheet/scenario names and a temporary file
    path to pass back to the confirm endpoint.
    """
    if not (file.filename or "").endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Upload must be a .xlsx file")

    tmp_dir = Path("temp")
    tmp_dir.mkdir(exist_ok=True)
    tmp_path = tmp_dir / (file.filename or "import.xlsx")

    with tmp_path.open("wb") as buf:
        shutil.copyfileobj(file.file, buf)

    try:
        scenarios = list_excel_scenarios(tmp_path)
        return {"scenarios": scenarios, "file_path": str(tmp_path)}
    except ReportError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/reports/import-excel/{test_id}/confirm")
async def import_excel_confirm(
    request: Request, test_id: str, data: dict
) -> Dict[str, Any]:
    """
    Confirm an Excel import and create steps for the given test.

    Expects ``scenario_id`` and ``xlsx_path`` in the request body JSON.
    Deletes the temporary file after successful import.
    """
    db_path = _db_path(request)
    scenario_id = data.get("scenario_id")
    xlsx_path = Path(data.get("xlsx_path", ""))

    if not xlsx_path.exists():
        raise HTTPException(status_code=404, detail="Temporary Excel file not found")

    try:
        steps = import_excel_steps(xlsx_path, scenario_id)
        for step in steps:
            await database.create_step(
                db_path=db_path,
                test_id=test_id,
                sequence=step["sequence"],
                action=step["action"],
                selector=step["selector"],
                value=step["value"],
                description=step["description"],
                is_sensitive=step["is_sensitive"],
            )
        try:
            xlsx_path.unlink(missing_ok=True)
        except Exception:
            pass
        return {"step_count": len(steps), "message": f"Imported {len(steps)} steps successfully"}
    except Exception as exc:
        logger.exception(f"Excel import confirm failed for test {test_id}")
        raise HTTPException(status_code=500, detail=str(exc))
