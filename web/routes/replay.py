"""Replay routes."""

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
import asyncio
from typing import Optional
from dataclasses import replace
import os
from pathlib import Path

from core import database
from core.models import RunStatus
from core.config import resolve_password
from engine.runner import run_test

router = APIRouter(prefix="/api/replay", tags=["Replay"])

class ReplayRequest(BaseModel):
    headless: bool = True
    slow_mo: int = 100
    env_id: Optional[str] = None

@router.post("/{test_id}")
async def start_replay(request: Request, test_id: str, data: ReplayRequest):
    """Start test replay."""
    db_path = request.app.state.db_path
    
    # Check if a run is already running
    runs = await database.list_runs(db_path)
    for run in runs:
        if run.status == RunStatus.RUNNING:
            raise HTTPException(status_code=400, detail="A test run is already in progress")
            
    try:
        test = await database.get_test(db_path, test_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Test not found")
    
    config = request.app.state.config
    
    if data.env_id:
        try:
            env = await database.get_environment(db_path, data.env_id)
            config = replace(config, fusion_url=env.url, fusion_user=env.username, fusion_pod=env.name)
            password = os.environ.get(env.password_env_var) or env.password_env_var
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to load environment: {str(e)}")
    else:
        try:
            password = resolve_password(config)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
        
    new_run = await database.create_run(
        db_path,
        test_id=test_id,
        test_name=test.name,
        consultant=config.consultant,
        pod=config.fusion_pod
    )
    
    # Start in background thread
    loop = asyncio.get_running_loop()
    loop.run_in_executor(
        None,
        run_test,
        new_run.id,
        test_id,
        config,
        password,
        db_path,
        config.output_root,
        data.headless,
        data.slow_mo
    )
    
    return {"run_id": new_run.id, "status": "pending", "message": "Run started"}

class AgentReplayRequest(BaseModel):
    api_key: str
    env_id: Optional[str] = None

@router.post("/{test_id}/agent")
async def start_agent_replay(request: Request, test_id: str, data: AgentReplayRequest):
    """Start test replay using autonomous agent."""
    db_path = request.app.state.db_path
    
    # Check if a run is already running
    runs = await database.list_runs(db_path)
    for run in runs:
        if run.status == RunStatus.RUNNING:
            raise HTTPException(status_code=400, detail="A test run is already in progress")
            
    try:
        test = await database.get_test(db_path, test_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Test not found")
    
    config = request.app.state.config
    
    password = None
    if data.env_id:
        try:
            env = await database.get_environment(db_path, data.env_id)
            config = replace(config, fusion_url=env.url, fusion_user=env.username, fusion_pod=env.name)
            password = os.environ.get(env.password_env_var) or env.password_env_var
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to load environment: {str(e)}")
    else:
        from core.config import resolve_password
        password = resolve_password(config)
        
    new_run = await database.create_run(
        db_path,
        test_id=test_id,
        test_name=f"{test.name} (Autonomous Agent)",
        consultant=config.consultant,
        pod=config.fusion_pod
    )
    # Start agent in background thread
    from engine.agent import start_agent_background
    start_agent_background(new_run.id, test_id, data.api_key, Path(config.output_root), override_config=config, override_password=password)
    
    return {"run_id": new_run.id, "status": "pending", "message": "Agent Run started"}

@router.get("/active")
async def get_active_replay(request: Request):
    """Get currently active run."""
    db_path = request.app.state.db_path
    runs = await database.list_runs(db_path)
    for run in runs:
        if run.status == RunStatus.RUNNING:
            return {"active": True, "run_id": run.id, "status": run.status.value}
            
    return {"active": False, "run_id": None, "status": None}
