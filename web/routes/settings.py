"""Settings and Environment routes for QA Platform."""

from typing import Any, Dict
from fastapi import APIRouter, Request, HTTPException, UploadFile, File
from pydantic import BaseModel

from core import database
from core.models import Environment

router = APIRouter()

# --- Environments Schemas & Routes ---

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


# --- Master Password Setup & Unlock Routes ---

@router.get("/settings/master-password/status")
async def get_master_password_status(request: Request) -> Dict[str, Any]:
    """Get status of the master password vault."""
    db_path = request.app.state.db_path
    verify_info = await database.get_master_password_verify(db_path)
    is_set = verify_info is not None
    is_unlocked = hasattr(request.app.state, "master_key") and request.app.state.master_key is not None
    return {
        "is_set": is_set,
        "is_unlocked": is_unlocked
    }

@router.get("/clients/{id}/export")
async def export_client_api(request: Request, id: str) -> Dict[str, Any]:
    """Export a single client profile as JSON (excluding passwords)."""
    db_path = request.app.state.db_path
    client = await database.get_client(db_path, id)
    # Remove sensitive fields
    client_dict = client.__dict__ if hasattr(client, "__dict__") else dict(client)
    for key in ["id", "created_at", "updated_at", "password"]:
        client_dict.pop(key, None)
    from fastapi.responses import JSONResponse
    return JSONResponse(content=client_dict, headers={"Content-Disposition": f"attachment; filename=client_{id}_profile.json"})

@router.post("/settings/master-password/setup")
async def setup_master_password(request: Request, data: Dict[str, str]) -> Dict[str, Any]:
    """Set the master password and verify database marker."""
    password = data.get("password")
    if not password or len(password) < 4:
        raise HTTPException(status_code=400, detail="Master password must be at least 4 characters")
    
    db_path = request.app.state.db_path
    existing = await database.get_master_password_verify(db_path)
    if existing:
        raise HTTPException(status_code=400, detail="Master password is already set")
        
    import os
    from core.security import derive_key, encrypt_data
    salt_bytes = os.urandom(16)
    salt_str = salt_bytes.hex()
    master_key = derive_key(password, salt_bytes)
    verifier_encrypted = encrypt_data(master_key, "verifier")
    
    await database.set_master_password_verify(db_path, salt_str, verifier_encrypted)
    request.app.state.master_key = master_key
    return {"message": "Master password configured and vault unlocked successfully"}

@router.post("/settings/master-password/unlock")
async def unlock_master_password(request: Request, data: Dict[str, str]) -> Dict[str, Any]:
    """Unlock the vault using master password."""
    password = data.get("password")
    if not password:
        raise HTTPException(status_code=400, detail="Password is required")
        
    db_path = request.app.state.db_path
    verify_info = await database.get_master_password_verify(db_path)
    if not verify_info:
        raise HTTPException(status_code=404, detail="Master password is not set yet")
        
    salt_str = verify_info["salt"]
    verifier_encrypted = verify_info["verifier"]
    
    from core.security import derive_key, decrypt_data
    try:
        salt_bytes = bytes.fromhex(salt_str)
        master_key = derive_key(password, salt_bytes)
        decrypted = decrypt_data(master_key, verifier_encrypted)
        if decrypted != "verifier":
            raise ValueError("Incorrect password")
    except Exception:
        raise HTTPException(status_code=401, detail="Incorrect master password")
        
    request.app.state.master_key = master_key
    return {"message": "Vault unlocked successfully"}

@router.post("/settings/master-password/lock")
async def lock_master_password(request: Request) -> Dict[str, Any]:
    """Lock the vault, discarding the key from memory."""
    if hasattr(request.app.state, "master_key"):
        delattr(request.app.state, "master_key")
    return {"message": "Vault locked successfully"}


# --- Clients Profile Schemas & Routes ---

class CreateClientRequest(BaseModel):
    display_name: str
    app_type: str
    base_url: str
    username: str
    password: str
    pod_identifier: str | None = None
    consultant_initials: str | None = None
    is_active: bool = True
    custom_wait_selectors: str | None = None
    extra_headers: str | None = None
    extra_cookies: str | None = None

class UpdateClientRequest(BaseModel):
    display_name: str | None = None
    app_type: str | None = None
    base_url: str | None = None
    username: str | None = None
    password: str | None = None
    pod_identifier: str | None = None
    consultant_initials: str | None = None
    is_active: bool | None = None
    custom_wait_selectors: str | None = None
    extra_headers: str | None = None
    extra_cookies: str | None = None

@router.get("/clients")
async def list_clients_api(request: Request) -> Dict[str, Any]:
    """List all clients profiles."""
    db_path = request.app.state.db_path
    clients = await database.list_clients(db_path)
    return {"data": clients, "message": f"{len(clients)} client profiles found"}

@router.get("/clients/{id}")
async def get_client_api(request: Request, id: str) -> Dict[str, Any]:
    """Get details of a specific client profile."""
    db_path = request.app.state.db_path
    try:
        client = await database.get_client(db_path, id)
        return {"data": client, "message": "Client profile retrieved"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/clients")
async def create_client_api(request: Request, data: CreateClientRequest) -> Dict[str, Any]:
    """Create a new client profile and secure their credentials."""
    db_path = request.app.state.db_path
    master_key = getattr(request.app.state, "master_key", None)
    
    from core.security import is_keyring_working, set_client_password
    if not is_keyring_working() and not master_key:
        raise HTTPException(status_code=400, detail="Master password must be unlocked to encrypt fallback secrets when OS keyring is unavailable")
        
    client = await database.create_client(
        db_path,
        display_name=data.display_name,
        app_type=data.app_type,
        base_url=data.base_url,
        username=data.username,
        pod_identifier=data.pod_identifier,
        consultant_initials=data.consultant_initials,
        is_active=data.is_active,
        custom_wait_selectors=data.custom_wait_selectors,
        extra_headers=data.extra_headers,
        extra_cookies=data.extra_cookies
    )
    
    set_client_password(client.id, data.password, master_key)
    return {"data": client, "message": "Client profile created successfully"}

@router.put("/clients/{id}")
async def update_client_api(request: Request, id: str, data: UpdateClientRequest) -> Dict[str, Any]:
    """Update a client profile."""
    db_path = request.app.state.db_path
    master_key = getattr(request.app.state, "master_key", None)
    
    from core.security import is_keyring_working, set_client_password
    update_dict = data.model_dump(exclude_unset=True)
    password = update_dict.pop("password", None)
    
    try:
        client = await database.update_client(db_path, id, **update_dict)
        if password is not None:
            if not is_keyring_working() and not master_key:
                raise HTTPException(status_code=400, detail="Master password must be unlocked to encrypt fallback secrets when OS keyring is unavailable")
            set_client_password(id, password, master_key)
        return {"data": client, "message": "Client profile updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/clients/{id}")
async def delete_client_api(request: Request, id: str) -> Dict[str, Any]:
    """Delete a client profile."""
    db_path = request.app.state.db_path
    await database.delete_client(db_path, id)
    return {"data": None, "message": "Client profile deleted successfully"}


# --- LLM Providers Schemas & Routes ---

class CreateLLMProviderRequest(BaseModel):
    name: str
    api_key: str
    model_name: str
    base_url_override: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.7
    is_active: bool = False

class UpdateLLMProviderRequest(BaseModel):
    api_key: str | None = None
    model_name: str | None = None
    base_url_override: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    is_active: bool | None = None

@router.get("/llm-providers")
async def list_llm_providers_api(request: Request) -> Dict[str, Any]:
    """List all configured LLM providers."""
    db_path = request.app.state.db_path
    providers = await database.list_llm_providers(db_path)
    for p in providers:
        if p.api_key_encrypted:
            p.api_key_encrypted = "[ENCRYPTED]"
    return {"data": providers, "message": f"{len(providers)} LLM providers found"}

@router.post("/llm-providers")
async def create_llm_provider_api(request: Request, data: CreateLLMProviderRequest) -> Dict[str, Any]:
    """Add a new LLM provider with encrypted API key."""
    db_path = request.app.state.db_path
    master_key = getattr(request.app.state, "master_key", None)
    if not master_key:
        raise HTTPException(status_code=400, detail="Master password must be unlocked to encrypt LLM API keys")
        
    from core.security import encrypt_data
    encrypted_key = encrypt_data(master_key, data.api_key)
    
    provider = await database.create_llm_provider(
        db_path,
        name=data.name,
        api_key_encrypted=encrypted_key,
        model_name=data.model_name,
        base_url_override=data.base_url_override,
        max_tokens=data.max_tokens,
        temperature=data.temperature,
        is_active=data.is_active
    )
    provider.api_key_encrypted = "[ENCRYPTED]"
    return {"data": provider, "message": "LLM provider created successfully"}

@router.put("/llm-providers/{name}")
async def update_llm_provider_api(request: Request, name: str, data: UpdateLLMProviderRequest) -> Dict[str, Any]:
    """Update an existing LLM provider."""
    db_path = request.app.state.db_path
    master_key = getattr(request.app.state, "master_key", None)
    
    update_dict = data.model_dump(exclude_unset=True)
    api_key = update_dict.pop("api_key", None)
    
    if api_key is not None:
        if not master_key:
            raise HTTPException(status_code=400, detail="Master password must be unlocked to encrypt LLM API keys")
        from core.security import encrypt_data
        update_dict["api_key_encrypted"] = encrypt_data(master_key, api_key)
        
    try:
        provider = await database.update_llm_provider(db_path, name, **update_dict)
        provider.api_key_encrypted = "[ENCRYPTED]"
        return {"data": provider, "message": "LLM provider updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/llm-providers/{name}")
async def delete_llm_provider_api(request: Request, name: str) -> Dict[str, Any]:
    """Delete an LLM provider."""
    db_path = request.app.state.db_path
    await database.delete_llm_provider(db_path, name)
    return {"data": None, "message": "LLM provider deleted successfully"}


# --- App Config Settings Routes ---

@router.get("/config")
async def get_configs_api(request: Request) -> Dict[str, Any]:
    """Get all key-value application configurations."""
    db_path = request.app.state.db_path
    configs = await database.get_all_configs(db_path)
    return {"data": configs}

@router.post("/config")
async def save_configs_api(request: Request, data: Dict[str, str]) -> Dict[str, Any]:
    """Save key-value application configurations."""
    db_path = request.app.state.db_path
    from pathlib import Path
    for k, v in data.items():
        await database.set_config_value(db_path, k, v)
        
    # Reload config in app state
    from core.config import load_config
    request.app.state.config = load_config(Path(".env"))
    return {"message": "Configurations saved successfully"}


@router.get("/clients/export")
async def export_clients_api(request: Request):
    """Export all client profiles as a JSON file response (excluding passwords)."""
    db_path = request.app.state.db_path
    clients = await database.list_clients(db_path)
    from fastapi.responses import JSONResponse
    clients_dict = [c.__dict__ if hasattr(c, "__dict__") else dict(c) for c in clients]
    for c in clients_dict:
        c.pop("id", None)
        c.pop("created_at", None)
        c.pop("updated_at", None)
    
    return JSONResponse(
        content=clients_dict,
        headers={"Content-Disposition": "attachment; filename=client_profiles_export.json"}
    )


@router.post("/clients/import")
async def import_clients_api(request: Request, file: UploadFile = File(...)):
    """Import client profiles from an uploaded JSON file."""
    db_path = request.app.state.db_path
    content = await file.read()
    import json
    try:
        data = json.loads(content)
        if not isinstance(data, list):
            data = [data]
        
        imported_count = 0
        for item in data:
            display_name = item.get("display_name")
            if not display_name:
                continue
            await database.create_client(
                db_path,
                display_name=display_name,
                app_type=item.get("app_type", "Generic Web"),
                base_url=item.get("base_url", "http://localhost"),
                username=item.get("username", "admin"),
                pod_identifier=item.get("pod_identifier"),
                consultant_initials=item.get("consultant_initials"),
                is_active=bool(item.get("is_active", True)),
                custom_wait_selectors=item.get("custom_wait_selectors"),
                extra_headers=item.get("extra_headers"),
                extra_cookies=item.get("extra_cookies")
            )
            imported_count += 1
            
        return {"status": "success", "message": f"Successfully imported {imported_count} client profiles"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse or import client profiles: {str(e)}")
