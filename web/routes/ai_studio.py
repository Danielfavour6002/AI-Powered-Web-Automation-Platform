from fastapi import APIRouter, Request, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
import logging
import asyncio
import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from engine.llm import LLMAdapter
from core.parser import FileParser
from core import database
from pydantic import BaseModel

router = APIRouter(prefix="/ai", tags=["AI Studio"])
logger = logging.getLogger(__name__)


async def read_file_safe(file: UploadFile) -> bytes:
    """Read upload file checking that it does not exceed 10MB limit."""
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    content = await file.read(MAX_FILE_SIZE + 1)
    if len(content) > MAX_FILE_SIZE:
        raise ValueError("File exceeds maximum allowed size of 10MB")
    return content


@router.get("/studio", response_class=HTMLResponse)
async def ai_studio_page(request: Request):
    """Render the AI Studio UI."""
    db_path = request.app.state.db_path
    active_prov = await database.get_active_llm_provider(db_path)
    clients = await database.list_clients(db_path)
    active_clients = [c for c in clients if c.is_active]
    vault_unlocked = hasattr(request.app.state, "master_key") and request.app.state.master_key is not None
    return request.app.state.templates.TemplateResponse(
        "ai_studio.html",
        {
            "request": request,
            "active_provider": active_prov,
            "clients": active_clients,
            "vault_unlocked": vault_unlocked
        }
    )


@router.post("/generate")
async def generate_tests(
    request: Request,
    file: UploadFile = File(...),
    provider: str = Form(...),
    api_key: Optional[str] = Form(None)
):
    """Generate tests from an uploaded file using the specified LLM."""
    try:
        try:
            content = await read_file_safe(file)
        except ValueError as ve:
            return JSONResponse(status_code=400, content={"status": "error", "message": str(ve)})

        db_path = request.app.state.db_path
        # Look up LLM provider config from DB to get configured model_name
        model_name = None
        try:
            prov_rec = await database.get_llm_provider(db_path, provider)
            model_name = prov_rec.model_name
        except Exception:
            pass

        # If API key is not passed, resolve from the database (try selected provider first, fall back to active provider)
        if not api_key:
            master_key = getattr(request.app.state, "master_key", None)
            if not master_key:
                return JSONResponse(status_code=400, content={"status": "error", "message": "Secure vault is locked. Please unlock the vault in Settings to use the saved API key."})
            
            resolved_provider = None
            try:
                resolved_provider = await database.get_llm_provider(db_path, provider)
            except Exception:
                pass
            
            if not resolved_provider or not resolved_provider.api_key_encrypted:
                resolved_provider = await database.get_active_llm_provider(db_path)
                
            if not resolved_provider or not resolved_provider.api_key_encrypted:
                return JSONResponse(status_code=400, content={"status": "error", "message": f"No API key provided and no saved API key configured for provider '{provider}'."})
                
            from core.security import decrypt_data
            try:
                api_key = decrypt_data(master_key, resolved_provider.api_key_encrypted)
                if not model_name and resolved_provider.name == provider:
                    model_name = resolved_provider.model_name
            except Exception:
                return JSONResponse(status_code=400, content={"status": "error", "message": "Failed to decrypt LLM API key. Check master password."})

        # 1. Parse the uploaded file into raw text steps
        raw_steps = FileParser.parse_file(file.filename, content)

        # 2. Use the LLM adapter to generate instructions
        adapter = LLMAdapter(provider=provider, api_key=api_key, model_name=model_name)
        instructions = adapter.generate_test_instructions(raw_steps)

        return JSONResponse(content={"status": "success", "instructions": instructions})

    except Exception as e:
        logger.error(f"Failed to generate tests: {e}")
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})


class AIImportRequest(BaseModel):
    name: str
    url: str
    instructions: List[Dict[str, Any]]


@router.post("/import")
async def import_ai_test(request: Request, data: AIImportRequest):
    """Create a new test from AI generated instructions."""
    db_path = request.app.state.db_path
    try:
        test = await database.create_test(
            db_path,
            name=data.name,
            url=data.url,
            mode="recorded",
            description="Generated by AI Studio"
        )

        for i, step_data in enumerate(data.instructions):
            sequence = i + 1
            action = step_data.get("action", "assert_text")
            selector = step_data.get("selector", "")
            value = step_data.get("value", "")
            description = step_data.get("description", "")

            if not selector and action != "navigate":
                selector = "element"

            await database.create_step(
                db_path,
                test_id=test.id,
                sequence=sequence,
                action=action,
                selector=selector,
                value=value,
                description=description,
                is_sensitive=False
            )

        return {"status": "success", "test_id": test.id}
    except Exception as e:
        logger.error(f"Failed to import AI test: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@router.post("/record-test")
async def start_record_test(
    request: Request,
    file: UploadFile = File(...),
    test_name: str = Form(...),
    test_url: str = Form(...),
    provider: str = Form(...),
    api_key: Optional[str] = Form(None),
    client_id: Optional[str] = Form(None),
    test_description: Optional[str] = Form(None)
):
    """Start background autonomous recording using custom visual driving agent loop."""
    try:
        # Check size (10MB limit)
        try:
            content = await read_file_safe(file)
        except ValueError as ve:
            return JSONResponse(status_code=400, content={"status": "error", "message": str(ve)})

        db_path = request.app.state.db_path
        # Look up LLM provider config from DB to get configured model_name
        model_name = None
        try:
            prov_rec = await database.get_llm_provider(db_path, provider)
            model_name = prov_rec.model_name
        except Exception:
            pass

        # If API key is not passed, resolve from the database (try selected provider first, fall back to active provider)
        if not api_key:
            master_key = getattr(request.app.state, "master_key", None)
            if not master_key:
                return JSONResponse(status_code=400, content={"status": "error", "message": "Secure vault is locked. Please unlock the vault in Settings to use the saved API key."})
            
            resolved_provider = None
            try:
                resolved_provider = await database.get_llm_provider(db_path, provider)
            except Exception:
                pass
            
            if not resolved_provider or not resolved_provider.api_key_encrypted:
                resolved_provider = await database.get_active_llm_provider(db_path)
                
            if not resolved_provider or not resolved_provider.api_key_encrypted:
                return JSONResponse(status_code=400, content={"status": "error", "message": f"No API key provided and no saved API key configured for provider '{provider}'."})
                
            from core.security import decrypt_data
            try:
                api_key = decrypt_data(master_key, resolved_provider.api_key_encrypted)
                if not model_name and resolved_provider.name == provider:
                    model_name = resolved_provider.model_name
            except Exception:
                return JSONResponse(status_code=400, content={"status": "error", "message": "Failed to decrypt LLM API key. Check master password."})

        # Get client password if client_id is provided
        password = None
        if client_id:
            from core.security import get_client_password
            master_key = getattr(request.app.state, "master_key", None)
            password = get_client_password(client_id, master_key)

        # 1. Parse steps using LLM
        raw_steps = FileParser.parse_file(file.filename, content)
        adapter = LLMAdapter(provider=provider, api_key=api_key, model_name=model_name)
        instructions = adapter.generate_test_instructions(raw_steps)

        # 2. Create test and steps in database
        test = await database.create_test(
            db_path,
            name=test_name,
            url=test_url,
            mode="recorded",
            description=test_description or "Generated autonomously by AI Studio Agent"
        )
        
        for i, step_data in enumerate(instructions):
            sequence = i + 1
            action = step_data.get("action", "assert_text")
            selector = step_data.get("selector", "")
            value = step_data.get("value", "")
            description = step_data.get("description", "")
            
            if not selector and action != "navigate":
                selector = "element"
                
            await database.create_step(
                db_path,
                test_id=test.id,
                sequence=sequence,
                action=action,
                selector=selector,
                value=value,
                description=description,
                is_sensitive=False
            )
            
        # 3. Create run
        config = request.app.state.config
        run = await database.create_run(
            db_path,
            test_id=test.id,
            test_name=test.name,
            consultant=config.consultant,
            pod=config.fusion_pod,
            client_id=client_id
        )
        
        # 4. Trigger autonomous agent in background
        from engine.agent import start_agent_background
        start_agent_background(
            run_id=run.id,
            test_id=test.id,
            api_key=api_key,
            output_root=Path(config.output_root),
            override_config=config,
            override_password=password
        )
        
        return JSONResponse(content={
            "status": "success",
            "run_id": run.id,
            "test_id": test.id
        })
        
    except Exception as e:
        logger.exception("Failed to start autonomous AI agent")
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})


@router.get("/agent-stream/{run_id}")
async def agent_stream(request: Request, run_id: str):
    """SSE streaming endpoint for autonomous agent execution logs and states."""
    from engine.agent import get_agent_queue, agent_status
    
    async def event_generator():
        queue = get_agent_queue(run_id)
        # Yield initial status if exists
        status = agent_status.get(run_id, "starting")
        yield f"data: {json.dumps({'type': 'status', 'status': status, 'message': 'Stream connected'})}\n\n"
        
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                logger.info(f"Client disconnected from SSE stream for run {run_id}")
                break
                
            try:
                # Wait for new log with a timeout to send keep-alive pings
                log_data = await asyncio.wait_for(queue.get(), timeout=15.0)
                yield f"data: {json.dumps(log_data)}\n\n"
                
                # If agent is finished, close the stream
                if log_data.get("type") == "done" or log_data.get("type") == "error":
                    break
            except asyncio.TimeoutError:
                # Ping keep-alive
                yield f"data: {json.dumps({'type': 'ping'})}\n\n"
            except Exception as e:
                logger.error(f"Error in SSE event generator: {e}")
                break

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/agent-resume/{run_id}")
async def resume_agent(run_id: str):
    """Resume a stalled/paused agent."""
    from engine.agent import signal_resume_agent
    await signal_resume_agent(run_id)
    return {"status": "success", "message": "Resume signal sent"}
