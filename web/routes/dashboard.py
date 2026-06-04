"""Dashboard routes for QA Platform."""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from typing import Any

from core import database

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request) -> Any:
    """Render dashboard home."""
    db_path = request.app.state.db_path
    stats = await database.get_dashboard_stats(db_path)
    clients = await database.list_clients(db_path)
    active_clients = [c for c in clients if c.is_active]
    return request.app.state.templates.TemplateResponse("dashboard.html", {
        "request": request,
        "stats": stats,
        "clients": active_clients
    })

@router.get("/tests", response_class=HTMLResponse)
async def tests_list(request: Request) -> Any:
    """Render tests list."""
    db_path = request.app.state.db_path
    tests = await database.list_tests(db_path)
    clients = await database.list_clients(db_path)
    active_clients = [c for c in clients if c.is_active]
    return request.app.state.templates.TemplateResponse("tests/list.html", {
        "request": request,
        "tests": tests,
        "clients": active_clients
    })

@router.get("/tests/create", response_class=HTMLResponse)
async def tests_create(request: Request) -> Any:
    """Render test creation page."""
    db_path = request.app.state.db_path
    environments = await database.list_environments(db_path)
    return request.app.state.templates.TemplateResponse("tests/create.html", {"request": request, "environments": environments})

@router.get("/tests/{id}", response_class=HTMLResponse)
async def test_detail(request: Request, id: str) -> Any:
    """Render test detail page."""
    db_path = request.app.state.db_path
    try:
        test = await database.get_test(db_path, id)
        steps = await database.get_steps_for_test(db_path, id)
        runs = await database.list_runs(db_path, test_id=id)
        environments = await database.list_environments(db_path)
    except Exception:
        raise HTTPException(status_code=404, detail="Test not found")
        
    return request.app.state.templates.TemplateResponse("tests/detail.html", {
        "request": request, 
        "test": test, 
        "steps": steps, 
        "runs": runs[:10],
        "environments": environments
    })

@router.get("/runs", response_class=HTMLResponse)
async def runs_list(request: Request) -> Any:
    """Render runs list."""
    db_path = request.app.state.db_path
    runs = await database.list_runs(db_path)
    return request.app.state.templates.TemplateResponse("runs/list.html", {"request": request, "runs": runs})

@router.get("/runs/{id}", response_class=HTMLResponse)
async def run_detail(request: Request, id: str) -> Any:
    """Render run detail page."""
    db_path = request.app.state.db_path
    try:
        run = await database.get_run(db_path, id)
        results = await database.get_results_for_run(db_path, id)
    except Exception:
        raise HTTPException(status_code=404, detail="Run not found")
        
    return request.app.state.templates.TemplateResponse("runs/detail.html", {
        "request": request, 
        "run": run, 
        "results": results
    })

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request) -> Any:
    """Render settings page."""
    config = request.app.state.config
    db_path = request.app.state.db_path
    environments = await database.list_environments(db_path)
    clients = await database.list_clients(db_path)
    llm_providers = await database.list_llm_providers(db_path)
    
    # Check master password status
    verify_info = await database.get_master_password_verify(db_path)
    master_password_set = verify_info is not None
    master_password_unlocked = hasattr(request.app.state, "master_key") and request.app.state.master_key is not None
    
    return request.app.state.templates.TemplateResponse(
        "settings.html", 
        {
            "request": request, 
            "config": config, 
            "environments": environments,
            "clients": clients,
            "llm_providers": llm_providers,
            "master_password_set": master_password_set,
            "master_password_unlocked": master_password_unlocked
        }
    )
