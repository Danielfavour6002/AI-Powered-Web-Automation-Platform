"""Logging configuration for QA Platform."""

import sys
import json
from pathlib import Path
from typing import Any, Dict
from datetime import datetime, timezone
from loguru import logger


def configure_logging(run_dir: Path | None = None) -> None:
    """
    Configure loguru logging with stderr and optional file sink.
    
    Args:
        run_dir: Optional path to the run directory for file logging.
    """
    logger.remove()
    
    # Stderr sink
    logger.add(
        sys.stderr,
        level="INFO",
        format="{time:HH:mm:ss} | <level>{level:<7}</level> | {message}",
        colorize=True
    )
    
    # File sink
    if run_dir:
        run_dir.mkdir(parents=True, exist_ok=True)
        log_file = run_dir / "run.log"
        logger.add(
            str(log_file),
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<7} | {name}:{line} | {message}",
            rotation="50 MB"
        )


def get_logger() -> Any:
    """
    Get the configured logger instance.
    
    Returns:
        Any: Loguru logger instance.
    """
    return logger


def append_audit(audit_file: Path, record: Dict[str, Any]) -> None:
    """
    Append an audit record to a JSONL file.
    
    Args:
        audit_file: Path to the audit file.
        record: The record dictionary to append.
    """
    audit_file.parent.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now(timezone.utc).isoformat()
    final_record = {"ts": timestamp, **record}
    
    with open(audit_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(final_record) + "\n")
