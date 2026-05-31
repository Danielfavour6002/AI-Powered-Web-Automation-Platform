"""Runs routes for QA Platform."""

import os
from typing import Any, Dict, Optional
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from pathlib import Path

from core import database
from core.models import RunStatus

router = APIRouter()

@router.get("/runs")
async def list_runs(request: Request, test_id: Optional[str] = None) -> Dict[str, Any]:
    """List runs, optionally filtering by test_id."""
    db_path = request.app.state.db_path
    runs = await database.list_runs(db_path, test_id=test_id)
    return {"data": runs, "message": f"{len(runs)} runs retrieved"}

@router.get("/runs/{id}")
async def get_run(request: Request, id: str) -> Dict[str, Any]:
    """Get a run and its results."""
    db_path = request.app.state.db_path
    run = await database.get_run(db_path, id)
    results = await database.get_results_for_run(db_path, id)
    return {"data": {"run": run, "results": results}, "message": "Run retrieved"}

@router.post("/runs/{id}/cancel")
async def cancel_run(request: Request, id: str) -> Dict[str, Any]:
    """Mark a running run as error."""
    db_path = request.app.state.db_path
    run = await database.get_run(db_path, id)
    if run.status in (RunStatus.RUNNING, RunStatus.PENDING):
        from engine.runner import cancel_active_run
        cancel_active_run(id)
        
        run = await database.update_run(
            db_path, 
            id, 
            status=RunStatus.ERROR, 
            error_message="Run cancelled by user"
        )
    return {"data": run, "message": "Run cancelled"}

@router.get("/runs/{id}/status")
async def get_run_status(request: Request, id: str) -> Dict[str, Any]:
    """Lightweight status poll for a run."""
    db_path = request.app.state.db_path
    run = await database.get_run(db_path, id)
    data = {
        "status": run.status.value,
        "passed": run.passed_count,
        "failed": run.failed_count,
        "step_count": run.step_count
    }
    return {"data": data, "message": "Status retrieved"}

@router.get("/runs/{id}/video")
async def get_run_video(request: Request, id: str) -> Any:
    """Download the video for a run."""
    db_path = request.app.state.db_path
    run = await database.get_run(db_path, id)
    if not run.video_path or not os.path.exists(run.video_path):
        return {"error": "Video not found", "type": "FileNotFoundError"}
    return FileResponse(run.video_path, media_type="video/webm", filename=Path(run.video_path).name)

@router.get("/runs/{id}/trace")
async def get_run_trace(request: Request, id: str) -> Any:
    """Download the trace for a run."""
    db_path = request.app.state.db_path
    run = await database.get_run(db_path, id)
    if not run.trace_path or not os.path.exists(run.trace_path):
        return {"error": "Trace not found", "type": "FileNotFoundError"}
    return FileResponse(run.trace_path, media_type="application/zip", filename=Path(run.trace_path).name)

@router.get("/runs/{id}/screenshot/{filename}")
async def get_run_screenshot(request: Request, id: str, filename: str) -> Any:
    """Download a screenshot from a run."""
    db_path = request.app.state.db_path
    run = await database.get_run(db_path, id)
    if not run.run_dir:
        return {"error": "Run directory not found", "type": "FileNotFoundError"}
        
    screenshot_path = Path(run.run_dir) / "screenshots" / filename
    if not screenshot_path.exists():
        return {"error": "Screenshot not found", "type": "FileNotFoundError"}
        
    return FileResponse(screenshot_path, media_type="image/png", filename=filename)

@router.get("/runs/{id}/log")
async def get_run_log(request: Request, id: str) -> Any:
    """Get log file contents as plain text."""
    from fastapi.responses import PlainTextResponse
    db_path = request.app.state.db_path
    run = await database.get_run(db_path, id)
    if not run.run_dir:
        return PlainTextResponse("No run directory", status_code=404)
        
    log_path = Path(run.run_dir) / "run.log"
    if not log_path.exists():
        return PlainTextResponse("Log file not found", status_code=404)
        
    content = log_path.read_text(encoding='utf-8')
    return PlainTextResponse(content)

@router.delete("/runs/{id}")
async def delete_run(request: Request, id: str) -> Dict[str, Any]:
    """Delete a run and its files from disk."""
    db_path = request.app.state.db_path
    run = await database.get_run(db_path, id)
    
    import shutil
    if run.run_dir and os.path.exists(run.run_dir):
        shutil.rmtree(run.run_dir, ignore_errors=True)
        
    # Delete from DB
    import aiosqlite
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM runs WHERE id = ?", (id,))
        await db.commit()
            
    return {"data": None, "message": "Run deleted"}
