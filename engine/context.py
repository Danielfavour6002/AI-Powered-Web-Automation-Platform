"""Run context dataclass."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from playwright.sync_api import Page

from core.config import Config

@dataclass
class RunContext:
    """Context passed throughout a test run."""
    page: Page
    config: Config
    password: str
    run_dir: Path
    run_id: str
    test_id: str
    is_oracle: bool
    reporter: Any
    screenshots_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        self.screenshots_dir = self.run_dir / "screenshots"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
