"""Script to clean up old traces and videos."""

import os
import time
from pathlib import Path
import logging

from core.config import load_config
from core.logging import configure_logging

def cleanup_old_files(output_root: Path, days_old: int = 180):
    """Delete .zip and .webm files older than specified days."""
    configure_logging(output_root)
    logger = logging.getLogger("cleanup")
    
    current_time = time.time()
    cutoff_time = current_time - (days_old * 86400)
    
    deleted_count = 0
    bytes_freed = 0
    
    # Iterate through all run directories
    for root, _, files in os.walk(output_root):
        for file in files:
            if file.endswith('.zip') or file.endswith('.webm'):
                file_path = Path(root) / file
                try:
                    stat = file_path.stat()
                    # Check if file is older than cutoff
                    if stat.st_mtime < cutoff_time:
                        file_size = stat.st_size
                        file_path.unlink()
                        deleted_count += 1
                        bytes_freed += file_size
                        logger.info(f"Deleted old file: {file_path}")
                except Exception as e:
                    logger.error(f"Failed to process {file_path}: {e}")
                    
    freed_mb = bytes_freed / (1024 * 1024)
    logger.info(f"Cleanup complete. Deleted {deleted_count} files, freed {freed_mb:.2f} MB.")
    print(f"Cleanup complete. Deleted {deleted_count} files, freed {freed_mb:.2f} MB.")

if __name__ == "__main__":
    env_path = Path(".env")
    try:
        config = load_config(env_path)
        # Default to 6 months (180 days)
        cleanup_old_files(config.output_root, days_old=180)
    except Exception as e:
        print(f"Failed to run cleanup: {e}")
