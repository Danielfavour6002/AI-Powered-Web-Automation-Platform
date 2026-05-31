"""Test execution reporter."""

import json
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import aiosqlite
import asyncio

from core.models import Step
from core.logging import get_logger, append_audit

logger = get_logger()

def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)

class Reporter:
    """Aggregates test execution evidence and updates DB real-time."""
    
    def __init__(self, run_id: str, run_dir: Path, db_path: Path, 
                 consultant: str, pod: str, test_name: str, test_id: str):
        self.run_id = run_id
        self.run_dir = run_dir
        self.db_path = db_path
        self.consultant = consultant
        self.pod = pod
        self.test_name = test_name
        self.test_id = test_id
        
        self.allure_dir = self.run_dir / "allure-results"
        self.allure_dir.mkdir(parents=True, exist_ok=True)
        
        self._steps_results: List[Dict[str, Any]] = []
        self._start_ms: int = _now_ms()
        self._test_uuid = str(uuid.uuid4())

    async def start_run(self) -> None:
        """Record start time and update run status."""
        self._start_ms = _now_ms()
        now = datetime.now(timezone.utc).isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE runs SET status = 'running', started_at = ? WHERE id = ?",
                (now, self.run_id)
            )
            await db.commit()

    async def record_step_result(self, step: Step, status: str, 
                                 actual: str, screenshot: Optional[Path],
                                 duration_ms: int, error: Optional[str] = None) -> None:
        """Record a single step result."""
        result_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        ss_path = str(screenshot) if screenshot else None
        
        # DB Update
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            await db.execute(
                """INSERT INTO results (
                    id, run_id, step_id, sequence, action, description, selector, value, status,
                    actual_value, error_message, screenshot_path, duration_ms, executed_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (result_id, self.run_id, step.id, step.sequence, step.action.value, step.description,
                 step.selector, step.value, status, actual, error, ss_path, duration_ms, now)
            )
            
            if status == "passed":
                await db.execute("UPDATE runs SET passed_count = passed_count + 1 WHERE id = ?", (self.run_id,))
            elif status == "failed":
                await db.execute("UPDATE runs SET failed_count = failed_count + 1 WHERE id = ?", (self.run_id,))
                
            await db.commit()
            
        # Allure Step
        attachments = []
        if screenshot and screenshot.exists():
            import shutil
            dest_name = f"{uuid.uuid4()}-attachment.png"
            shutil.copy2(screenshot, self.allure_dir / dest_name)
            attachments.append({
                "name": f"Screenshot {step.sequence}",
                "source": dest_name,
                "type": "image/png"
            })
            
        allure_status = "passed" if status == "passed" else ("failed" if status == "failed" else "skipped")
        
        step_data = {
            "name": f"Step {step.sequence}: {step.action.value} {step.selector}",
            "status": allure_status,
            "stage": "finished",
            "start": _now_ms() - duration_ms,
            "stop": _now_ms(),
            "attachments": attachments,
            "parameters": []
        }
        if error:
            step_data["statusDetails"] = {"message": error}
            
        self._steps_results.append(step_data)
        
        if status == "passed":
            logger.info(f"Step {step.sequence} passed")
        elif status == "failed":
            logger.warning(f"Step {step.sequence} failed: {error}")

    async def end_run(self, status: str, error_message: Optional[str] = None) -> None:
        """Complete the run."""
        now = datetime.now(timezone.utc).isoformat()
        end_ms = _now_ms()
        duration_s = (end_ms - self._start_ms) / 1000.0
        
        # DB Update
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """UPDATE runs SET status = ?, completed_at = ?, duration_seconds = ?, 
                   error_message = ? WHERE id = ?""",
                (status, now, duration_s, error_message, self.run_id)
            )
            await db.commit()
            
        # Write Allure Result
        allure_status = "passed" if status == "passed" else "failed"
        if status == "error":
            allure_status = "broken"
            
        allure_result = {
            "uuid": self._test_uuid,
            "historyId": self.test_id,
            "name": self.test_name,
            "fullName": f"Tests.{self.test_name}",
            "status": allure_status,
            "start": self._start_ms,
            "stop": end_ms,
            "steps": self._steps_results,
            "attachments": [],
            "labels": [
                {"name": "suite", "value": "QA Platform"},
                {"name": "feature", "value": self.test_name},
                {"name": "host", "value": "local"},
                {"name": "pod", "value": self.pod or "unknown"}
            ]
        }
        
        if error_message:
            allure_result["statusDetails"] = {"message": error_message}
            
        result_file = self.allure_dir / f"{self._test_uuid}-result.json"
        result_file.write_text(json.dumps(allure_result, indent=2), encoding='utf-8')
        
        # Audit
        audit_file = self.run_dir.parent / "audit.jsonl"
        append_audit(audit_file, {
            "run_id": self.run_id,
            "test_id": self.test_id,
            "status": status,
            "duration": duration_s
        })
        
        logger.info(f"Run completed with status: {status}")
