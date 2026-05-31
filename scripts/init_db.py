"""Initialize the QA Platform database."""

import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import load_config
from core.database import init_db


async def main() -> None:
    """Initialize the database."""
    env_path = Path(".env")
    
    print(f"Loading configuration from {env_path.absolute()}")
    try:
        config = load_config(env_path)
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return
        
    print(f"Initializing database at {Path(config.db_path)}")
    
    try:
        await init_db(Path(config.db_path))
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Failed to initialize database: {e}")

if __name__ == "__main__":
    asyncio.run(main())
