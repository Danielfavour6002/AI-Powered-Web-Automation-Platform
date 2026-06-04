"""Replay routes for QA Platform (Process Isolated)."""

import os
import sys
import subprocess
import json
from typing import Optional, Dict, Any
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from core import database
from core.models import RunStatus
from core.security import get_client_password

router = APIRouter(prefix="/api/replay", tags=["Replay"])


class ReplayRequest(BaseModel):
    headless: bool = True
    slow_mo: int = 100
    env_id: Optional[str] = None  # Represents the selected ClientProfile ID
    run_params: Optional[Dict[str, Any]] = None


@router.post("/{test_id}")
async def start_replay(request: Request, test_id: str, data: ReplayRequest):
    """Start test replay using a separate background process."""
    db_path = request.app.state.db_path
    
    # 1. Check if a run is already running
    runs = await database.list_runs(db_path)
    for run in runs:
        if run.status == RunStatus.RUNNING:
            raise HTTPException(status_code=400, detail="A test run is already in progress")
            
    # 2. Check if the test exists
    try:
        test = await database.get_test(db_path, test_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Test not found")
    
    config = request.app.state.config
    
    client_id = None
    consultant = config.consultant
    pod = config.fusion_pod
    
    # 3. Resolve Client Profile if selected
    if data.env_id:
        try:
            client = await database.get_client(db_path, data.env_id)
            client_id = client.id
            consultant = client.consultant_initials or consultant
            pod = client.pod_identifier or pod
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to load client profile: {str(e)}")
            
    # Serialize run parameters
    run_params_str = None
    if data.run_params:
        run_params_str = json.dumps(data.run_params)
        
    # 4. Create Run record in the database
    new_run = await database.create_run(
        db_path,
        test_id=test_id,
        test_name=test.name,
        consultant=consultant,
        pod=pod,
        client_id=client_id,
        run_params=run_params_str
    )
    
    # 5. Spawn background replay worker process (completely isolated)
    cmd = [
        sys.executable,
        "main.py",
        "run",
        "--test", test_id,
        "--run-id", new_run.id,
        "--slow-mo", str(data.slow_mo)
    ]
    if data.headless:
        cmd.append("--headless")
        
    try:
        subprocess.Popen(
            cmd,
            cwd=str(Path(__file__).resolve().parents[2]),  # project root
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0,
            close_fds=True
        )
    except Exception as e:
        await database.update_run(db_path, new_run.id, status="error", error_message=f"Failed to spawn worker process: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to launch replay worker: {e}")
        
    return {"run_id": new_run.id, "status": "pending", "message": "Replay run started"}


class AgentReplayRequest(BaseModel):
    api_key: str
    env_id: Optional[str] = None
    run_params: Optional[Dict[str, Any]] = None


@router.post("/{test_id}/agent")
async def start_agent_replay(request: Request, test_id: str, data: AgentReplayRequest):
    """Start autonomous agent replay in the background."""
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
    client_id = None
    consultant = config.consultant
    pod = config.fusion_pod
    
    if data.env_id:
        try:
            client = await database.get_client(db_path, data.env_id)
            client_id = client.id
            consultant = client.consultant_initials or consultant
            pod = client.pod_identifier or pod
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to load client profile: {str(e)}")
            
    run_params_str = None
    if data.run_params:
        run_params_str = json.dumps(data.run_params)
        
    new_run = await database.create_run(
        db_path,
        test_id=test_id,
        test_name=f"{test.name} (AI-Guided)",
        consultant=consultant,
        pod=pod,
        client_id=client_id,
        run_params=run_params_str
    )
    
    # Resolve password for the agent login if needed
    from core.config import resolve_password
    password = resolve_password(config)
    if client_id:
        client_pass = get_client_password(client_id)
        if client_pass:
            password = client_pass
            
    # Trigger custom AI browser agent in background task/thread
    from engine.agent import start_agent_background
    start_agent_background(
        new_run.id,
        test_id,
        data.api_key,
        Path(config.output_root),
        override_config=config,
        override_password=password
    )
    
    return {"run_id": new_run.id, "status": "pending", "message": "AI-Guided Run started"}


@router.get("/active")
async def get_active_replay(request: Request):
    """Get currently active run."""
    db_path = request.app.state.db_path
    runs = await database.list_runs(db_path)
    for run in runs:
        if run.status == RunStatus.RUNNING:
            return {"active": True, "run_id": run.id, "status": run.status.value}
            
    return {"active": False, "run_id": None, "status": None}
