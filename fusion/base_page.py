"""Base page object for UI interaction."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from playwright.sync_api import Page, Locator

from fusion.wait import wait_for_any_idle
from core.logging import get_logger

logger = get_logger()

class BasePage:
    """Base page encapsulating common Playwright interactions."""

    def __init__(self, page: Page, screenshots_dir: Optional[Path] = None, is_oracle: bool = True):
        self.page = page
        self.screenshots_dir = screenshots_dir
        self.is_oracle = is_oracle

        if self.screenshots_dir:
            self.screenshots_dir.mkdir(parents=True, exist_ok=True)

    def wait_for_idle(self, timeout_ms: int = 30000) -> None:
        """Wait for page idle state."""
        wait_for_any_idle(self.page, self.is_oracle, timeout_ms)

    def screenshot(self, name: str) -> Optional[Path]:
        """Take a full page screenshot."""
        if not self.screenshots_dir:
            return None

        path = self.screenshots_dir / f"{name}.png"
        self.page.screenshot(path=path, full_page=True)
        return path

    def navigate(self, url: str, timeout_ms: int = 60000) -> None:
        """Navigate to URL and wait for idle."""
        logger.debug(f"Navigating to {url}")
        self.page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
        self.wait_for_idle()

    def safe_click(self, selector: str, timeout_ms: int = 10000) -> None:
        """Wait for selector visible, click, and wait for idle."""
        logger.debug(f"Clicking {selector}")
        loc = self.page.locator(selector).first
        loc.wait_for(state="visible", timeout=timeout_ms)
        loc.click(timeout=timeout_ms)
        self.wait_for_idle()

    def safe_fill(self, selector: str, value: str, timeout_ms: int = 10000) -> None:
        """Wait for selector visible, clear it, and fill."""
        logger.debug(f"Filling {selector}")
        loc = self.page.locator(selector).first
        loc.wait_for(state="visible", timeout=timeout_ms)
        loc.click(click_count=3, timeout=timeout_ms)
        loc.fill(value, timeout=timeout_ms)

    def resolve_locator(self, candidates: List[str], timeout_ms: int = 15000) -> Locator:
        """Try candidates and return the first one that is visible."""
        import time
        start_t = time.time()
        while (time.time() - start_t) * 1000 < timeout_ms:
            for candidate in candidates:
                loc = self.page.locator(candidate).first
                if loc.is_visible():
                    return loc
            self.page.wait_for_timeout(500)

        # Fallback to first if none become visible, allowing standard Playwright timeout
        return self.page.locator(candidates[0]).first
