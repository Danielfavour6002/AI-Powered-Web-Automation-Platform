"""Recording routes."""

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from pathlib import Path
import tempfile
import asyncio

from core import database
from core.models import Test
from engine.recorder import get_recorder
from engine.parser import parse_codegen_output

router = APIRouter(prefix="/api/recording", tags=["Recording"])

class StartRecordingRequest(BaseModel):
    test_id: str
    url: str
    env_id: str | None = None

@router.post("/start")
async def start_recording(request: Request, data: StartRecordingRequest):
    """Start playwright codegen for a test."""
    db_path = request.app.state.db_path
    
    try:
        await database.get_test(db_path, data.test_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Test not found")
        
    recorder = get_recorder()
    if await recorder.is_alive():
        raise HTTPException(status_code=400, detail="Recording already in progress")
        
    temp_dir = Path(tempfile.gettempdir())
    output_file = temp_dir / f"qap_record_{data.test_id}.py"
    
    # Store test_id on app state to associate when stopped
    request.app.state.recording_test_id = data.test_id
    
    await recorder.start_recording(data.url, output_file, data.env_id)
    return {"status": "recording", "message": "Playwright recorder launched"}

@router.post("/stop")
async def stop_recording(request: Request):
    """Stop codegen and save steps."""
    recorder = get_recorder()
    if not recorder.is_recording:
        raise HTTPException(status_code=400, detail="No active recording")
        
    test_id = getattr(request.app.state, "recording_test_id", None)
    if not test_id:
        raise HTTPException(status_code=400, detail="No test associated with recording")
        
    output_file = await recorder.stop_recording()
    
    try:
        db_path = request.app.state.db_path
        config = request.app.state.config
        
        steps = parse_codegen_output(output_file, is_oracle=config.is_oracle_fusion)
        
        # Delete old steps
        await database.delete_steps_for_test(db_path, test_id)
        
        for step in steps:
            await database.create_step(
                db_path,
                test_id=test_id,
                sequence=step["sequence"],
                action=step["action"],
                selector=step["selector"],
                value=step["value"],
                description=step["description"],
                is_sensitive=step["is_sensitive"]
            )
            
        # Cleanup
        try:
            output_file.unlink()
        except OSError:
            pass
            
        return {"status": "saved", "step_count": len(steps), "message": f"{len(steps)} steps captured and saved"}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/status")
async def recording_status():
    """Get recording status."""
    recorder = get_recorder()
    is_rec = await recorder.is_alive()
    return {
        "is_recording": is_rec,
        "message": "Recording active" if is_rec else "No active recording"
    }
