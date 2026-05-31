"""Data models for QA Platform."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class RunStatus(str, Enum):
    """Status of a test run."""
    PENDING = 'pending'
    RUNNING = 'running'
    PASSED = 'passed'
    FAILED = 'failed'
    ERROR = 'error'


class ActionType(str, Enum):
    """Types of actions available in test steps."""
    NAVIGATE = 'navigate'
    CLICK = 'click'
    FILL = 'fill'
    SELECT = 'select'
    CHECK = 'check'
    UNCHECK = 'uncheck'
    PRESS = 'press'
    WAIT = 'wait'
    ASSERT_VISIBLE = 'assert_visible'
    ASSERT_TEXT = 'assert_text'
    SCREENSHOT = 'screenshot'


@dataclass
class Test:
    """Test case entity."""
    id: str
    name: str
    url: str
    mode: str
    created_at: str
    updated_at: str
    description: Optional[str] = None
    step_count: int = 0


@dataclass
class Step:
    """Test step entity."""
    id: str
    test_id: str
    sequence: int
    action: ActionType
    is_sensitive: bool
    created_at: str
    selector: Optional[str] = None
    value: Optional[str] = None
    description: Optional[str] = None


@dataclass
class StepAction:
    """Helper dataclass for creating steps."""
    action: ActionType
    selector: Optional[str] = None
    value: Optional[str] = None
    description: Optional[str] = None
    is_sensitive: bool = False


@dataclass
class Run:
    """Test run entity."""
    id: str
    test_id: str
    test_name: str
    status: RunStatus
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    consultant: Optional[str] = None
    pod: Optional[str] = None
    run_dir: Optional[str] = None
    video_path: Optional[str] = None
    trace_path: Optional[str] = None
    error_message: Optional[str] = None
    step_count: int = 0
    passed_count: int = 0
    failed_count: int = 0


@dataclass
class Result:
    """Step execution result entity."""
    id: str
    run_id: str
    sequence: int
    action: ActionType
    status: str
    executed_at: str
    step_id: Optional[str] = None
    description: Optional[str] = None
    selector: Optional[str] = None
    value: Optional[str] = None
    actual_value: Optional[str] = None
    expected_value: Optional[str] = None
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None
    duration_ms: Optional[int] = None


@dataclass
class DashboardStats:
    """Dashboard statistics."""
    total_tests: int
    total_runs: int
    passed_runs: int
    failed_runs: int
    pass_rate: float
    recent_runs: list[Run]


@dataclass
class Environment:
    """Environment configuration entity."""
    id: str
    name: str
    url: str
    username: str
    password_env_var: str
    created_at: str
    updated_at: str

