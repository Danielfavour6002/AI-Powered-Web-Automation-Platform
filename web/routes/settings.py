"""Settings and Environment routes for QA Platform."""

from typing import Any, Dict
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from core import database
from core.models import Environment

router = APIRouter()

class CreateEnvironmentRequest(BaseModel):
    name: str
    url: str
    username: str
    password_env_var: str

class UpdateEnvironmentRequest(BaseModel):
    name: str | None = None
    url: str | None = None
    username: str | None = None
    password_env_var: str | None = None

@router.get("/environments")
async def list_environments(request: Request) -> Dict[str, Any]:
    """List all environments."""
    db_path = request.app.state.db_path
    environments = await database.list_environments(db_path)
    return {"data": environments, "message": f"{len(environments)} environments found"}

@router.get("/environments/{id}")
async def get_environment(request: Request, id: str) -> Dict[str, Any]:
    """Get an environment by ID."""
    db_path = request.app.state.db_path
    try:
        environment = await database.get_environment(db_path, id)
        return {"data": environment, "message": "Environment retrieved"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/environments")
async def create_environment(request: Request, data: CreateEnvironmentRequest) -> Dict[str, Any]:
    """Create a new environment."""
    db_path = request.app.state.db_path
    environment = await database.create_environment(
        db_path,
        name=data.name,
        url=data.url,
        username=data.username,
        password_env_var=data.password_env_var
    )
    return {"data": environment, "message": "Environment created successfully"}

@router.put("/environments/{id}")
async def update_environment(request: Request, id: str, data: UpdateEnvironmentRequest) -> Dict[str, Any]:
    """Update an environment."""
    db_path = request.app.state.db_path
    try:
        environment = await database.update_environment(
            db_path,
            id,
            name=data.name,
            url=data.url,
            username=data.username,
            password_env_var=data.password_env_var
        )
        return {"data": environment, "message": "Environment updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/environments/{id}")
async def delete_environment(request: Request, id: str) -> Dict[str, Any]:
    """Delete an environment."""
    db_path = request.app.state.db_path
    await database.delete_environment(db_path, id)
    return {"data": None, "message": "Environment deleted successfully"}
