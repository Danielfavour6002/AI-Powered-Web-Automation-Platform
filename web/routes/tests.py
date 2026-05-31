"""Tests routes for QA Platform."""

from typing import Any, Dict, List
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from core import database
from core.models import Test, Step
from core.security import sanitize_step

router = APIRouter()

class CreateTestRequest(BaseModel):
    name: str
    url: str
    mode: str
    description: str | None = None

class UpdateTestRequest(BaseModel):
    name: str | None = None
    description: str | None = None

class CreateStepRequest(BaseModel):
    sequence: int
    action: str
    selector: str | None = None
    value: str | None = None
    description: str | None = None

class UpdateStepRequest(BaseModel):
    action: str
    selector: str | None = None
    value: str | None = None
    description: str | None = None

class ReorderStepItem(BaseModel):
    id: str
    sequence: int

@router.get("/tests")
async def list_tests(request: Request) -> Dict[str, Any]:
    """List all tests."""
    db_path = request.app.state.db_path
    tests = await database.list_tests(db_path)
    return {"data": tests, "message": f"{len(tests)} tests found"}

@router.get("/tests/{id}")
async def get_test(request: Request, id: str) -> Dict[str, Any]:
    """Get a test by ID, including its steps."""
    db_path = request.app.state.db_path
    test = await database.get_test(db_path, id)
    steps = await database.get_steps_for_test(db_path, id)
    return {"data": {"test": test, "steps": steps}, "message": "Test retrieved"}

@router.post("/tests")
async def create_test(request: Request, data: CreateTestRequest) -> Dict[str, Any]:
    """Create a new test."""
    db_path = request.app.state.db_path
    test = await database.create_test(
        db_path, 
        name=data.name, 
        url=data.url, 
        mode=data.mode, 
        description=data.description
    )
    return {"data": test, "message": "Test created successfully"}

@router.put("/tests/{id}")
async def update_test(request: Request, id: str, data: UpdateTestRequest) -> Dict[str, Any]:
    """Update a test's name or description."""
    db_path = request.app.state.db_path
    test = await database.update_test(
        db_path, 
        id, 
        name=data.name, 
        description=data.description
    )
    return {"data": test, "message": "Test updated successfully"}

@router.delete("/tests/{id}")
async def delete_test(request: Request, id: str) -> Dict[str, Any]:
    """Delete a test and all its steps."""
    db_path = request.app.state.db_path
    await database.delete_test(db_path, id)
    return {"data": None, "message": "Test deleted successfully"}

@router.get("/tests/{id}/steps")
async def get_steps(request: Request, id: str) -> Dict[str, Any]:
    """Get ordered steps for a test."""
    db_path = request.app.state.db_path
    steps = await database.get_steps_for_test(db_path, id)
    return {"data": steps, "message": "Steps retrieved"}

@router.post("/tests/{id}/steps")
async def add_step(request: Request, id: str, data: CreateStepRequest) -> Dict[str, Any]:
    """Add a step to a test, sanitizing it first."""
    db_path = request.app.state.db_path
    
    # Sanitize inputs
    sanitized = sanitize_step(
        action=data.action, 
        selector=data.selector or "", 
        value=data.value or ""
    )
    
    step = await database.create_step(
        db_path,
        test_id=id,
        sequence=data.sequence,
        action=sanitized["action"],
        selector=sanitized["selector"] if sanitized["selector"] else None,
        value=sanitized["value"] if sanitized["value"] else None,
        description=data.description,
        is_sensitive=sanitized["is_sensitive"]
    )
    return {"data": step, "message": "Step added successfully"}

@router.delete("/tests/{id}/steps")
async def delete_steps(request: Request, id: str) -> Dict[str, Any]:
    """Delete all steps for a test."""
    db_path = request.app.state.db_path
    await database.delete_steps_for_test(db_path, id)
    return {"data": None, "message": "All steps deleted"}

@router.put("/tests/{id}/steps/reorder")
async def reorder_steps(request: Request, id: str, items: List[ReorderStepItem]) -> Dict[str, Any]:
    """Reorder steps for a test."""
    db_path = request.app.state.db_path
    for item in items:
        await database.update_step(db_path, item.id, item.sequence)
    steps = await database.get_steps_for_test(db_path, id)
    return {"data": steps, "message": "Steps reordered successfully"}

@router.delete("/tests/{test_id}/steps/{step_id}")
async def delete_single_step(request: Request, test_id: str, step_id: str) -> Dict[str, Any]:
    """Delete a single step for a test."""
    db_path = request.app.state.db_path
    await database.delete_step(db_path, step_id)
    return {"data": None, "message": "Step deleted"}

@router.put("/tests/{test_id}/steps/{step_id}")
async def update_single_step(request: Request, test_id: str, step_id: str, data: UpdateStepRequest) -> Dict[str, Any]:
    """Update a single step for a test."""
    db_path = request.app.state.db_path
    sanitized = sanitize_step(
        action=data.action,
        selector=data.selector or "",
        value=data.value or ""
    )
    await database.update_step_properties(
        db_path,
        step_id=step_id,
        action=sanitized["action"],
        selector=sanitized["selector"] if sanitized["selector"] else None,
        value=sanitized["value"] if sanitized["value"] else None,
        description=data.description,
        is_sensitive=sanitized["is_sensitive"]
    )
    return {"data": None, "message": "Step updated successfully"}

