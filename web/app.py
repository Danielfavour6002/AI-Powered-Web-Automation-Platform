"""FastAPI application factory for QA Platform."""

import sys
import asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from core.config import load_config
from core.database import init_db
from core.exceptions import QAPError
from core.logging import configure_logging, get_logger

from web.routes import dashboard, tests, runs, reports
from web.routes.recording import router as recording_router
from web.routes.replay import router as replay_router
from web.routes.ai_studio import router as ai_studio_router
from web.routes import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifespan context manager for FastAPI.
    Initializes database and logging on startup, cleans up on shutdown.
    """
    logger = get_logger()
    
    # Initialize DB
    await init_db(app.state.config.db_path)
    
    host = app.state.config.host
    port = app.state.config.port
    logger.info(f"QA Platform started on {host}:{port}")
    
    yield
    
    logger.info("QA Platform stopped")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        FastAPI: The configured application.
    """
    import os
    from pathlib import Path
    
    # Load config early to attach to state
    # We assume .env is in the project root
    env_path = Path(".env")
    config = load_config(env_path)
    
    # Configure root logging
    configure_logging()
    
    app = FastAPI(
        title="QA Platform",
        docs_url="/api/docs",
        lifespan=lifespan
    )
    
    # Store config on app state
    app.state.config = config
    app.state.db_path = Path(config.db_path)
    
    # Setup CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost", "http://127.0.0.1", "http://localhost:3000", "https://trace.playwright.dev"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Exception handler for QAPError
    @app.exception_handler(QAPError)
    async def qap_error_handler(request: Any, exc: QAPError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"error": str(exc), "type": type(exc).__name__}
        )
        
    # Mount static files
    app.mount("/static", StaticFiles(directory="web/static"), name="static")
    
    # Setup templates
    templates = Jinja2Templates(directory="web/templates")
    app.state.templates = templates
    
    # Include routers
    app.include_router(dashboard.router, tags=["Dashboard"])
    app.include_router(tests.router, prefix="/api", tags=["Tests"])
    app.include_router(runs.router, prefix="/api", tags=["Runs"])
    app.include_router(reports.router, prefix="/api", tags=["Reports"])
    app.include_router(settings.router, prefix="/api", tags=["Settings"])
    app.include_router(recording_router)
    app.include_router(replay_router)
    app.include_router(ai_studio_router)
    
    return app
