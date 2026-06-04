"""Database layer for QA Platform."""

import aiosqlite
from typing import List, Optional, Dict, Any
from uuid import uuid4
from datetime import datetime, timezone
from pathlib import Path
from enum import Enum

from core.models import Test, Step, Run, Result, DashboardStats, RunStatus, ActionType, Environment, ClientProfile, LLMProvider
from core.exceptions import DatabaseError

def _now_iso() -> str:
    """Get current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


async def init_db(db_path: Path) -> None:
    """Initialize the database and create tables if not exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS tests (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    url TEXT NOT NULL,
                    mode TEXT NOT NULL CHECK(mode IN ('recorded','excel')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    step_count INTEGER DEFAULT 0
                )
            ''')
            
            await db.execute('''
                CREATE TABLE IF NOT EXISTS steps (
                    id TEXT PRIMARY KEY,
                    test_id TEXT NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
                    sequence INTEGER NOT NULL,
                    action TEXT NOT NULL CHECK(action IN 
                        ('navigate','click','fill','select','check','uncheck',
                         'press','wait','assert_visible','assert_text','screenshot')),
                    selector TEXT,
                    value TEXT,
                    description TEXT,
                    is_sensitive INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            ''')

            await db.execute('''
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    test_id TEXT NOT NULL REFERENCES tests(id),
                    test_name TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending' 
                        CHECK(status IN ('pending','running','passed','failed','error')),
                    started_at TEXT,
                    completed_at TEXT,
                    duration_seconds REAL,
                    consultant TEXT,
                    pod TEXT,
                    run_dir TEXT,
                    video_path TEXT,
                    trace_path TEXT,
                    step_count INTEGER DEFAULT 0,
                    passed_count INTEGER DEFAULT 0,
                    failed_count INTEGER DEFAULT 0,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    client_id TEXT,
                    run_params TEXT
                )
            ''')

            await db.execute('''
                CREATE TABLE IF NOT EXISTS results (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                    step_id TEXT REFERENCES steps(id),
                    sequence INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    description TEXT,
                    selector TEXT,
                    value TEXT,
                    status TEXT NOT NULL CHECK(status IN ('passed','failed','skipped')),
                    actual_value TEXT,
                    expected_value TEXT,
                    error_message TEXT,
                    screenshot_path TEXT,
                    duration_ms INTEGER,
                    executed_at TEXT NOT NULL
                )
            ''')

            await db.execute('''
                CREATE TABLE IF NOT EXISTS environments (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    username TEXT NOT NULL,
                    password_env_var TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            ''')

            await db.execute('''
                CREATE TABLE IF NOT EXISTS app_config (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            
            await db.execute('''
                CREATE TABLE IF NOT EXISTS clients (
                    id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    app_type TEXT NOT NULL,
                    base_url TEXT NOT NULL,
                    username TEXT NOT NULL,
                    pod_identifier TEXT,
                    consultant_initials TEXT,
                    is_active INTEGER DEFAULT 1,
                    custom_wait_selectors TEXT,
                    extra_headers TEXT,
                    extra_cookies TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            ''')
            
            await db.execute('''
                CREATE TABLE IF NOT EXISTS llm_providers (
                    name TEXT PRIMARY KEY,
                    api_key_encrypted TEXT,
                    model_name TEXT NOT NULL,
                    base_url_override TEXT,
                    max_tokens INTEGER DEFAULT 4096,
                    temperature REAL DEFAULT 0.7,
                    is_active INTEGER DEFAULT 0
                )
            ''')
            
            await db.execute('''
                CREATE TABLE IF NOT EXISTS master_password_verify (
                    salt TEXT PRIMARY KEY,
                    verifier TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            ''')

            # Run table runs migrations for existing schema backward compatibility
            async with db.execute("PRAGMA table_info(runs)") as cursor:
                columns = [row[1] for row in await cursor.fetchall()]
                if 'client_id' not in columns:
                    await db.execute("ALTER TABLE runs ADD COLUMN client_id TEXT")
                if 'run_params' not in columns:
                    await db.execute("ALTER TABLE runs ADD COLUMN run_params TEXT")

            # Migrate any outdated Gemini model name to gemini-2.0-flash (stable).
            # gemini-1.5-flash and gemini-1.5-pro are no longer available on the
            # v1beta endpoint that litellm targets — upgrade all legacy records.
            await db.execute(
                "UPDATE llm_providers SET model_name = 'gemini/gemini-2.0-flash' "
                "WHERE model_name LIKE '%gemini-1.5%'"
            )
            await db.commit()
    except Exception as e:
        raise DatabaseError(f"Failed to initialize database: {e}")


def _dict_factory(cursor: aiosqlite.Cursor, row: tuple) -> dict:
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

# --- Tests CRUD ---

async def create_test(db_path: Path, name: str, url: str, mode: str, description: Optional[str] = None) -> Test:
    test_id = uuid4().hex
    now = _now_iso()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO tests (id, name, description, url, mode, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (test_id, name, description, url, mode, now, now)
        )
        await db.commit()
    return await get_test(db_path, test_id)


async def get_test(db_path: Path, test_id: str) -> Test:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = _dict_factory
        async with db.execute("SELECT * FROM tests WHERE id = ?", (test_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                raise DatabaseError(f"Test not found: {test_id}")
            return Test(**row)


async def list_tests(db_path: Path) -> List[Test]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = _dict_factory
        async with db.execute("SELECT * FROM tests ORDER BY created_at DESC") as cursor:
            rows = await cursor.fetchall()
            return [Test(**row) for row in rows]


async def update_test(db_path: Path, test_id: str, name: Optional[str] = None, description: Optional[str] = None) -> Test:
    now = _now_iso()
    updates = []
    params = []
    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if description is not None:
        updates.append("description = ?")
        params.append(description)
        
    updates.append("updated_at = ?")
    params.append(now)
    
    params.append(test_id)
    
    async with aiosqlite.connect(db_path) as db:
        await db.execute(f"UPDATE tests SET {', '.join(updates)} WHERE id = ?", tuple(params))
        await db.commit()
    return await get_test(db_path, test_id)


async def delete_test(db_path: Path, test_id: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("DELETE FROM tests WHERE id = ?", (test_id,))
        await db.commit()


def normalize_action(action: str) -> str:
    """Normalize action string to match SQLite check constraints and ActionType enum."""
    if not action:
        return "assert_text"
    act = action.strip().lower()
    mapping = {
        "navigate": "navigate",
        "goto": "navigate",
        "open": "navigate",
        "click": "click",
        "hover": "click",
        "fill": "fill",
        "type": "fill",
        "input": "fill",
        "select": "select",
        "choose": "select",
        "check": "check",
        "uncheck": "uncheck",
        "press": "press",
        "key": "press",
        "type_key": "press",
        "wait": "wait",
        "delay": "wait",
        "sleep": "wait",
        "assert_visible": "assert_visible",
        "assert_element": "assert_visible",
        "verify_visible": "assert_visible",
        "assert_text": "assert_text",
        "verify_text": "assert_text",
        "assert": "assert_text",
        "verify": "assert_text",
        "screenshot": "screenshot",
        "capture": "screenshot",
    }
    if act in mapping:
        return mapping[act]
    if "navigate" in act or "goto" in act or "open" in act:
        return "navigate"
    if "assert" in act or "verify" in act or "check" in act:
        if "text" in act or "value" in act:
            return "assert_text"
        return "assert_visible"
    if "input" in act or "type" in act or "write" in act:
        return "fill"
    if "click" in act or "press" in act or "tap" in act or "hover" in act:
        return "click"
    if "wait" in act or "sleep" in act or "delay" in act:
        return "wait"
    if "screenshot" in act or "capture" in act or "image" in act:
        return "screenshot"
    valid_actions = {
        'navigate', 'click', 'fill', 'select', 'check', 'uncheck',
        'press', 'wait', 'assert_visible', 'assert_text', 'screenshot'
    }
    if act in valid_actions:
        return act
    return "assert_text"


# --- Steps CRUD ---

async def create_step(db_path: Path, test_id: str, sequence: int, action: str, 
                      selector: Optional[str] = None, value: Optional[str] = None, 
                      description: Optional[str] = None, is_sensitive: bool = False) -> Step:
    step_id = uuid4().hex
    now = _now_iso()
    is_sensitive_int = 1 if is_sensitive else 0
    normalized_act = normalize_action(action)
    
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute(
            """INSERT INTO steps (id, test_id, sequence, action, selector, value, description, is_sensitive, created_at) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (step_id, test_id, sequence, normalized_act, selector, value, description, is_sensitive_int, now)
        )
        await db.execute("UPDATE tests SET step_count = step_count + 1, updated_at = ? WHERE id = ?", (now, test_id))
        await db.commit()
        
        db.row_factory = _dict_factory
        async with db.execute("SELECT * FROM steps WHERE id = ?", (step_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                raise DatabaseError(f"Step creation failed: {step_id}")
            
            row['is_sensitive'] = bool(row['is_sensitive'])
            row['action'] = ActionType(row['action'])
            return Step(**row)


async def get_steps_for_test(db_path: Path, test_id: str) -> List[Step]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = _dict_factory
        async with db.execute("SELECT * FROM steps WHERE test_id = ? ORDER BY sequence ASC", (test_id,)) as cursor:
            rows = await cursor.fetchall()
            steps = []
            for row in rows:
                row['is_sensitive'] = bool(row['is_sensitive'])
                row['action'] = ActionType(row['action'])
                steps.append(Step(**row))
            return steps


async def update_step(db_path: Path, step_id: str, sequence: int) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("UPDATE steps SET sequence = ? WHERE id = ?", (sequence, step_id))
        await db.commit()


async def update_step_properties(db_path: Path, step_id: str, action: str,
                                 selector: Optional[str], value: Optional[str],
                                 description: Optional[str], is_sensitive: bool) -> None:
    now = _now_iso()
    is_sensitive_int = 1 if is_sensitive else 0
    normalized_act = normalize_action(action)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """UPDATE steps 
               SET action = ?, selector = ?, value = ?, description = ?, is_sensitive = ?
               WHERE id = ?""",
            (normalized_act, selector, value, description, is_sensitive_int, step_id)
        )
        cursor = await db.execute("SELECT test_id FROM steps WHERE id = ?", (step_id,))
        row = await cursor.fetchone()
        if row:
            test_id = row[0]
            await db.execute("UPDATE tests SET updated_at = ? WHERE id = ?", (now, test_id))
        await db.commit()


async def delete_step(db_path: Path, step_id: str) -> None:
    now = _now_iso()
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT test_id FROM steps WHERE id = ?", (step_id,))
        row = await cursor.fetchone()
        if not row:
            return
        test_id = row[0]
        
        await db.execute("DELETE FROM steps WHERE id = ?", (step_id,))
        await db.execute("UPDATE tests SET step_count = step_count - 1, updated_at = ? WHERE id = ?", (now, test_id))
        
        # Resequence remaining steps
        cursor = await db.execute("SELECT id FROM steps WHERE test_id = ? ORDER BY sequence ASC", (test_id,))
        rows = await cursor.fetchall()
        for index, r in enumerate(rows):
            new_seq = index + 1
            await db.execute("UPDATE steps SET sequence = ? WHERE id = ?", (new_seq, r[0]))
            
        await db.commit()


async def delete_steps_for_test(db_path: Path, test_id: str) -> None:
    now = _now_iso()
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM steps WHERE test_id = ?", (test_id,))
        await db.execute("UPDATE tests SET step_count = 0, updated_at = ? WHERE id = ?", (now, test_id))
        await db.commit()


# --- Runs CRUD ---

async def create_run(db_path: Path, test_id: str, test_name: str, consultant: Optional[str] = None, pod: Optional[str] = None, client_id: Optional[str] = None, run_params: Optional[str] = None) -> Run:
    run_id = uuid4().hex
    now = _now_iso()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """INSERT INTO runs (id, test_id, test_name, status, consultant, pod, created_at, client_id, run_params)
               VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, ?)""",
            (run_id, test_id, test_name, consultant, pod, now, client_id, run_params)
        )
        await db.commit()
    return await get_run(db_path, run_id)


async def get_run(db_path: Path, run_id: str) -> Run:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = _dict_factory
        async with db.execute("SELECT * FROM runs WHERE id = ?", (run_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                raise DatabaseError(f"Run not found: {run_id}")
            row['status'] = RunStatus(row['status'])
            return Run(**row)


async def list_runs(db_path: Path, test_id: Optional[str] = None) -> List[Run]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = _dict_factory
        if test_id:
            cursor = await db.execute("SELECT * FROM runs WHERE test_id = ? ORDER BY created_at DESC", (test_id,))
        else:
            cursor = await db.execute("SELECT * FROM runs ORDER BY created_at DESC")
            
        rows = await cursor.fetchall()
        runs = []
        for row in rows:
            row['status'] = RunStatus(row['status'])
            runs.append(Run(**row))
        return runs


async def update_run(db_path: Path, run_id: str, **kwargs: Any) -> Run:
    updates = []
    params = []
    for k, v in kwargs.items():
        updates.append(f"{k} = ?")
        params.append(v.value if isinstance(v, Enum) else v)
            
    if not updates:
        return await get_run(db_path, run_id)
        
    params.append(run_id)
    query = f"UPDATE runs SET {', '.join(updates)} WHERE id = ?"
    
    async with aiosqlite.connect(db_path) as db:
        await db.execute(query, tuple(params))
        await db.commit()
    return await get_run(db_path, run_id)


async def get_recent_runs(db_path: Path, limit: int = 10) -> List[Run]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = _dict_factory
        async with db.execute("SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)) as cursor:
            rows = await cursor.fetchall()
            runs = []
            for row in rows:
                row['status'] = RunStatus(row['status'])
                runs.append(Run(**row))
            return runs


# --- Results CRUD ---

async def create_result(db_path: Path, run_id: str, sequence: int, action: str, status: str,
                        step_id: Optional[str] = None, description: Optional[str] = None,
                        selector: Optional[str] = None, value: Optional[str] = None,
                        actual_value: Optional[str] = None, expected_value: Optional[str] = None,
                        error_message: Optional[str] = None, screenshot_path: Optional[str] = None,
                        duration_ms: Optional[int] = None) -> Result:
    result_id = uuid4().hex
    now = _now_iso()
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute(
            """INSERT INTO results (
                id, run_id, step_id, sequence, action, description, selector, value, status,
                actual_value, expected_value, error_message, screenshot_path, duration_ms, executed_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (result_id, run_id, step_id, sequence, action, description, selector, value, status,
             actual_value, expected_value, error_message, screenshot_path, duration_ms, now)
        )
        await db.commit()
        
        db.row_factory = _dict_factory
        async with db.execute("SELECT * FROM results WHERE id = ?", (result_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                raise DatabaseError(f"Result creation failed: {result_id}")
            row['action'] = ActionType(row['action'])
            return Result(**row)


async def get_results_for_run(db_path: Path, run_id: str) -> List[Result]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = _dict_factory
        async with db.execute("SELECT * FROM results WHERE run_id = ? ORDER BY sequence ASC", (run_id,)) as cursor:
            rows = await cursor.fetchall()
            results = []
            for row in rows:
                row['action'] = ActionType(row['action'])
                results.append(Result(**row))
            return results


# --- Environments CRUD ---

async def create_environment(db_path: Path, name: str, url: str, username: str, password_env_var: str) -> Environment:
    env_id = uuid4().hex
    now = _now_iso()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO environments (id, name, url, username, password_env_var, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (env_id, name, url, username, password_env_var, now, now)
        )
        await db.commit()
    return await get_environment(db_path, env_id)


async def get_environment(db_path: Path, env_id: str) -> Environment:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = _dict_factory
        async with db.execute("SELECT * FROM environments WHERE id = ?", (env_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                raise DatabaseError(f"Environment not found: {env_id}")
            return Environment(**row)


async def list_environments(db_path: Path) -> List[Environment]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = _dict_factory
        async with db.execute("SELECT * FROM environments ORDER BY name ASC") as cursor:
            rows = await cursor.fetchall()
            return [Environment(**row) for row in rows]


async def update_environment(db_path: Path, env_id: str, name: Optional[str] = None, url: Optional[str] = None, username: Optional[str] = None, password_env_var: Optional[str] = None) -> Environment:
    now = _now_iso()
    updates = []
    params = []
    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if url is not None:
        updates.append("url = ?")
        params.append(url)
    if username is not None:
        updates.append("username = ?")
        params.append(username)
    if password_env_var is not None:
        updates.append("password_env_var = ?")
        params.append(password_env_var)
        
    updates.append("updated_at = ?")
    params.append(now)
    
    params.append(env_id)
    
    async with aiosqlite.connect(db_path) as db:
        await db.execute(f"UPDATE environments SET {', '.join(updates)} WHERE id = ?", tuple(params))
        await db.commit()
    return await get_environment(db_path, env_id)


async def delete_environment(db_path: Path, env_id: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM environments WHERE id = ?", (env_id,))
        await db.commit()


# --- Stats ---

async def get_dashboard_stats(db_path: Path) -> DashboardStats:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM tests")
        total_tests = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT COUNT(*) FROM runs")
        total_runs = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT COUNT(*) FROM runs WHERE status = 'passed'")
        passed_runs = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT COUNT(*) FROM runs WHERE status = 'failed'")
        failed_runs = (await cursor.fetchone())[0]
            
        pass_rate = (passed_runs / total_runs * 100) if total_runs > 0 else 0.0
        
    recent_runs = await get_recent_runs(db_path, limit=5)
    
    return DashboardStats(
        total_tests=total_tests,
        total_runs=total_runs,
        passed_runs=passed_runs,
        failed_runs=failed_runs,
        pass_rate=pass_rate,
        recent_runs=recent_runs
    )


# --- App Config CRUD ---

async def get_config_value(db_path: Path, key: str, default: Optional[str] = None) -> Optional[str]:
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT value FROM app_config WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0]
            return default

async def set_config_value(db_path: Path, key: str, value: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT OR REPLACE INTO app_config (key, value) VALUES (?, ?)",
            (key, value)
        )
        await db.commit()

async def get_all_configs(db_path: Path) -> Dict[str, str]:
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT key, value FROM app_config") as cursor:
            rows = await cursor.fetchall()
            return {row[0]: row[1] for row in rows}


# --- Clients CRUD ---

async def create_client(db_path: Path, display_name: str, app_type: str, base_url: str, username: str,
                        pod_identifier: Optional[str] = None, consultant_initials: Optional[str] = None,
                        is_active: bool = True, custom_wait_selectors: Optional[str] = None,
                        extra_headers: Optional[str] = None, extra_cookies: Optional[str] = None) -> ClientProfile:
    client_id = uuid4().hex
    now = _now_iso()
    is_active_int = 1 if is_active else 0
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """INSERT INTO clients (
                id, display_name, app_type, base_url, username, pod_identifier, consultant_initials,
                is_active, custom_wait_selectors, extra_headers, extra_cookies, created_at, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (client_id, display_name, app_type, base_url, username, pod_identifier, consultant_initials,
             is_active_int, custom_wait_selectors, extra_headers, extra_cookies, now, now)
        )
        await db.commit()
    return await get_client(db_path, client_id)

async def get_client(db_path: Path, client_id: str) -> ClientProfile:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = _dict_factory
        async with db.execute("SELECT * FROM clients WHERE id = ?", (client_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                raise DatabaseError(f"Client profile not found: {client_id}")
            row['is_active'] = bool(row['is_active'])
            return ClientProfile(**row)

async def list_clients(db_path: Path, active_only: bool = False) -> List[ClientProfile]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = _dict_factory
        if active_only:
            query = "SELECT * FROM clients WHERE is_active = 1 ORDER BY display_name ASC"
        else:
            query = "SELECT * FROM clients ORDER BY display_name ASC"
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
            clients = []
            for row in rows:
                row['is_active'] = bool(row['is_active'])
                clients.append(ClientProfile(**row))
            return clients

async def update_client(db_path: Path, client_id: str, **kwargs: Any) -> ClientProfile:
    now = _now_iso()
    updates = []
    params = []
    for k, v in kwargs.items():
        if k in ['display_name', 'app_type', 'base_url', 'username', 'pod_identifier', 
                 'consultant_initials', 'is_active', 'custom_wait_selectors', 'extra_headers', 'extra_cookies']:
            updates.append(f"{k} = ?")
            if k == 'is_active':
                params.append(1 if v else 0)
            else:
                params.append(v)
    if updates:
        updates.append("updated_at = ?")
        params.append(now)
        params.append(client_id)
        query = f"UPDATE clients SET {', '.join(updates)} WHERE id = ?"
        async with aiosqlite.connect(db_path) as db:
            await db.execute(query, tuple(params))
            await db.commit()
    return await get_client(db_path, client_id)

async def delete_client(db_path: Path, client_id: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        await db.commit()


# --- LLM Providers CRUD ---

async def create_llm_provider(db_path: Path, name: str, api_key_encrypted: Optional[str], model_name: str,
                              base_url_override: Optional[str] = None, max_tokens: int = 4096,
                              temperature: float = 0.7, is_active: bool = False) -> LLMProvider:
    is_active_int = 1 if is_active else 0
    async with aiosqlite.connect(db_path) as db:
        if is_active:
            await db.execute("UPDATE llm_providers SET is_active = 0")
        await db.execute(
            """INSERT INTO llm_providers (
                name, api_key_encrypted, model_name, base_url_override, max_tokens, temperature, is_active
               ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (name, api_key_encrypted, model_name, base_url_override, max_tokens, temperature, is_active_int)
        )
        await db.commit()
    return await get_llm_provider(db_path, name)

async def get_llm_provider(db_path: Path, name: str) -> LLMProvider:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = _dict_factory
        async with db.execute("SELECT * FROM llm_providers WHERE name = ?", (name,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                raise DatabaseError(f"LLM Provider not found: {name}")
            row['is_active'] = bool(row['is_active'])
            return LLMProvider(**row)

async def get_active_llm_provider(db_path: Path) -> Optional[LLMProvider]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = _dict_factory
        async with db.execute("SELECT * FROM llm_providers WHERE is_active = 1 LIMIT 1") as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            row['is_active'] = bool(row['is_active'])
            return LLMProvider(**row)

async def list_llm_providers(db_path: Path) -> List[LLMProvider]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = _dict_factory
        async with db.execute("SELECT * FROM llm_providers ORDER BY name ASC") as cursor:
            rows = await cursor.fetchall()
            providers = []
            for row in rows:
                row['is_active'] = bool(row['is_active'])
                providers.append(LLMProvider(**row))
            return providers

async def update_llm_provider(db_path: Path, name: str, **kwargs: Any) -> LLMProvider:
    updates = []
    params = []
    is_active = kwargs.get('is_active')
    async with aiosqlite.connect(db_path) as db:
        if is_active:
            await db.execute("UPDATE llm_providers SET is_active = 0 WHERE name != ?", (name,))
        for k, v in kwargs.items():
            if k in ['api_key_encrypted', 'model_name', 'base_url_override', 'max_tokens', 'temperature', 'is_active']:
                updates.append(f"{k} = ?")
                if k == 'is_active':
                    params.append(1 if v else 0)
                else:
                    params.append(v)
        if updates:
            params.append(name)
            query = f"UPDATE llm_providers SET {', '.join(updates)} WHERE name = ?"
            await db.execute(query, tuple(params))
            await db.commit()
    return await get_llm_provider(db_path, name)

async def delete_llm_provider(db_path: Path, name: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM llm_providers WHERE name = ?", (name,))
        await db.commit()


# --- Master Password Verification CRUD ---

async def get_master_password_verify(db_path: Path) -> Optional[Dict[str, str]]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = _dict_factory
        async with db.execute("SELECT * FROM master_password_verify LIMIT 1") as cursor:
            return await cursor.fetchone()

async def set_master_password_verify(db_path: Path, salt: str, verifier: str) -> None:
    now = _now_iso()
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM master_password_verify")
        await db.execute(
            "INSERT INTO master_password_verify (salt, verifier, created_at) VALUES (?, ?, ?)",
            (salt, verifier, now)
        )
        await db.commit()


