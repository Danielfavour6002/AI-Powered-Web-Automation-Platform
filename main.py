"""Main entry point for QA Platform."""

import argparse
import asyncio
import sys
import uvicorn
from pathlib import Path
import uuid

from core.config import load_config, resolve_password
from core.database import init_db, create_test, create_step
from core.logging import configure_logging, get_logger
from engine.runner import run_test
from reports.excel_importer import list_excel_scenarios, import_excel_steps

def serve() -> None:
    """Start the FastAPI server."""
    env_path = Path(".env")
    try:
        config = load_config(env_path)
    except Exception as e:
        print(f"Configuration error: {e}")
        sys.exit(1)
        
    print(f"QA Platform started on http://{config.host}:{config.port}")
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
    uvicorn.run(
        "web.app:create_app",
        host=config.host,
        port=config.port,
        factory=True,
        reload=True,
        log_level="error",
        loop="asyncio"
    )

def do_init() -> None:
    """Initialize the database."""
    env_path = Path(".env")
    config = load_config(env_path)
    asyncio.run(init_db(Path(config.db_path)))
    print("Database initialized. QA Platform ready.")

def run_scenario(test_id: str, headless: bool, slow_mo: int) -> None:
    """Run a scenario directly from CLI."""
    env_path = Path(".env")
    config = load_config(env_path)
    configure_logging(Path(config.output_root))
    logger = get_logger()
    
    password = resolve_password(config)
    run_id = uuid.uuid4().hex
    
    # We need to create a Run in DB first, but `run_test` expects the Run to already exist in some flows.
    # Actually, the API does create_run before run_test. Let's do that here too.
    import core.database as db
    async def _setup_run():
        test = await db.get_test(Path(config.db_path), test_id)
        return await db.create_run(Path(config.db_path), test.id, test.name, config.consultant, config.fusion_pod)
        
    try:
        run = asyncio.run(_setup_run())
    except Exception as e:
        logger.error(f"Failed to setup run: {e}")
        sys.exit(1)
        
    print(f"Starting test {test_id} (run {run.id})")
    status = run_test(
        run_id=run.id,
        test_id=test_id,
        config=config,
        password=password,
        db_path=Path(config.db_path),
        output_root=Path(config.output_root),
        headless=headless,
        slow_mo=slow_mo
    )
    print(f"Run completed with status: {status}")

def import_excel(file_path: str) -> None:
    """Import scenarios from Excel."""
    path = Path(file_path)
    if not path.exists():
        print(f"File not found: {file_path}")
        return
        
    env_path = Path(".env")
    config = load_config(env_path)
    db_path = Path(config.db_path)
    
    scenarios = list_excel_scenarios(path)
    if not scenarios:
        print("No scenarios found.")
        return
        
    print("Available scenarios:")
    for i, s in enumerate(scenarios):
        print(f"[{i}] {s['id']} - {s['name']} ({s['step_count']} steps)")
        
    choice = input("Enter number to import (or 'all'): ")
    
    if choice.lower() == 'all':
        targets = scenarios
    else:
        try:
            targets = [scenarios[int(choice)]]
        except (ValueError, IndexError):
            print("Invalid choice.")
            return
            
    async def _save_scenario(s):
        steps = import_excel_steps(path, s['id'])
        test = await create_test(db_path, s['name'], "https://example.com", "excel", s['description'])
        for step in steps:
            await create_step(
                db_path, test.id, step['sequence'], step['action'],
                step['selector'], step['value'], step['description'], step['is_sensitive']
            )
        print(f"Imported '{s['name']}' ({len(steps)} steps) -> Test ID: {test.id}")
            
    for s in targets:
        asyncio.run(_save_scenario(s))

def main() -> None:
    """Parse arguments and execute commands."""
    parser = argparse.ArgumentParser(description="QA Platform CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # init
    subparsers.add_parser("init", help="Initialize the database")
    
    # serve
    subparsers.add_parser("serve", help="Start the FastAPI server")
    
    # run
    run_parser = subparsers.add_parser("run", help="Run a test scenario")
    run_parser.add_argument("--test", required=True, help="Test ID to run")
    run_parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    run_parser.add_argument("--slow-mo", type=int, default=100, help="Slow down execution by ms")
    
    # import
    import_parser = subparsers.add_parser("import", help="Import Excel steps")
    import_parser.add_argument("--file", required=True, help="Path to .xlsx file")
    
    args = parser.parse_args()
    
    if args.command == "serve":
        serve()
    elif args.command == "init":
        do_init()
    elif args.command == "run":
        run_scenario(args.test, args.headless, args.slow_mo)
    elif args.command == "import":
        import_excel(args.file)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
