"""Reports routes for QA Platform."""

from typing import Any, Dict
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from fastapi.responses import FileResponse
from pathlib import Path
import os
import shutil

from core.database import get_run, get_results_for_run, create_step
from core.config import load_config
from core.exceptions import ReportError
from reports.excel_report import generate_excel_report
from reports.docx_report import generate_docx_report
from reports.allure_report import get_allure_results_dir, get_allure_report_response
from reports.excel_importer import list_excel_scenarios, import_excel_steps

router = APIRouter()

@router.get("/reports/{run_id}/excel")
async def get_excel_report(run_id: str) -> FileResponse:
    config = load_config(Path('.env'))
    db_path = Path(config.db_path)
    try:
        run = await get_run(db_path, run_id)
        results = await get_results_for_run(db_path, run_id)
        
        run_dir = Path(run.run_dir) if run.run_dir else Path(config.output_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        output_path = run_dir / f"report_{run_id}.xlsx"
        
        generate_excel_report(run, results, output_path)
        
        filename = f"QA_Report_{run.test_name.replace(' ', '_')}_{run.created_at[:10]}.xlsx"
        return FileResponse(
            path=output_path, 
            filename=filename, 
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/reports/{run_id}/docx")
async def get_docx_report(run_id: str) -> FileResponse:
    config = load_config(Path('.env'))
    db_path = Path(config.db_path)
    try:
        run = await get_run(db_path, run_id)
        results = await get_results_for_run(db_path, run_id)
        
        run_dir = Path(run.run_dir) if run.run_dir else Path(config.output_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        screenshots_dir = run_dir / "screenshots"
        output_path = run_dir / f"report_{run_id}.docx"
        
        generate_docx_report(run, results, screenshots_dir, output_path)
        
        filename = f"QA_Report_{run.test_name.replace(' ', '_')}_{run.created_at[:10]}.docx"
        return FileResponse(
            path=output_path, 
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/reports/{run_id}/allure")
async def get_allure_report(run_id: str) -> FileResponse:
    config = load_config(Path('.env'))
    db_path = Path(config.db_path)
    try:
        run = await get_run(db_path, run_id)
        results = await get_results_for_run(db_path, run_id)
        
        run_dir = Path(run.run_dir) if run.run_dir else Path(config.output_dir)
        allure_dir = get_allure_results_dir(run_dir)
        index_path = get_allure_report_response(run, results, allure_dir)
        
        return FileResponse(
            path=index_path,
            media_type="text/html"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reports/import-excel")
async def import_excel_upload(file: UploadFile = File(...)) -> Dict[str, Any]:
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="Must be an .xlsx file")
        
    temp_dir = Path("temp")
    temp_dir.mkdir(exist_ok=True)
    temp_path = temp_dir / file.filename
    
    with temp_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        scenarios = list_excel_scenarios(temp_path)
        return {"scenarios": scenarios, "file_path": str(temp_path)}
    except ReportError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/reports/import-excel/{test_id}/confirm")
async def import_excel_confirm(test_id: str, data: dict) -> Dict[str, Any]:
    config = load_config(Path('.env'))
    db_path = Path(config.db_path)
    scenario_id = data.get('scenario_id')
    xlsx_path = Path(data.get('xlsx_path', ''))
    
    if not xlsx_path.exists():
        raise HTTPException(status_code=404, detail="Temp Excel file not found")
        
    try:
        steps = import_excel_steps(xlsx_path, scenario_id)
        
        for step in steps:
            await create_step(
                db_path=db_path,
                test_id=test_id,
                sequence=step['sequence'],
                action=step['action'],
                selector=step['selector'],
                value=step['value'],
                description=step['description'],
                is_sensitive=step['is_sensitive']
            )
            
        # Clean up temp file
        try:
            xlsx_path.unlink()
        except:
            pass
            
        return {"step_count": len(steps), "message": f"Successfully imported {len(steps)} steps."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
