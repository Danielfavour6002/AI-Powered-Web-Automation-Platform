"""Base page object for UI interaction (Asynchronous)."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from playwright.async_api import Page, Locator

from fusion.wait import wait_for_any_idle
from core.logging import get_logger

logger = get_logger()

class BasePage:
    """Base page encapsulating common Playwright interactions (Asynchronous)."""

    def __init__(self, page: Page, screenshots_dir: Optional[Path] = None, is_oracle: bool = True):
        self.page = page
        self.screenshots_dir = screenshots_dir
        self.is_oracle = is_oracle

        if self.screenshots_dir:
            self.screenshots_dir.mkdir(parents=True, exist_ok=True)

    async def wait_for_idle(self, timeout_ms: int = 30000) -> None:
        """Wait for page idle state."""
        await wait_for_any_idle(self.page, self.is_oracle, timeout_ms)

    async def screenshot(self, name: str) -> Optional[Path]:
        """Take a full page screenshot."""
        if not self.screenshots_dir:
            return None

        path = self.screenshots_dir / f"{name}.png"
        await self.page.screenshot(path=path, full_page=True)
        return path

    async def navigate(self, url: str, timeout_ms: int = 60000) -> None:
        """Navigate to URL and wait for idle."""
        logger.debug(f"Navigating to {url}")
        await self.page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
        await self.wait_for_idle()

    async def safe_click(self, selector: str, timeout_ms: int = 10000) -> None:
        """Wait for selector visible, click, and wait for idle."""
        logger.debug(f"Clicking {selector}")
        loc = self.page.locator(selector).first
        await loc.wait_for(state="visible", timeout=timeout_ms)
        await loc.click(timeout=timeout_ms)
        await self.wait_for_idle()

    async def safe_fill(self, selector: str, value: str, timeout_ms: int = 10000) -> None:
        """Wait for selector visible, clear it, and fill."""
        logger.debug(f"Filling {selector}")
        loc = self.page.locator(selector).first
        await loc.wait_for(state="visible", timeout=timeout_ms)
        await loc.click(click_count=3, timeout=timeout_ms)
        await loc.fill(value, timeout=timeout_ms)

    async def resolve_locator(self, candidates: List[str], timeout_ms: int = 15000) -> Locator:
        """Try candidates and return the first one that is visible."""
        import time
        start_t = time.time()
        while (time.time() - start_t) * 1000 < timeout_ms:
            for candidate in candidates:
                loc = self.page.locator(candidate).first
                if await loc.is_visible():
                    return loc
            await asyncio.sleep(0.5)

        # Fallback to first if none become visible, allowing standard Playwright timeout
        return self.page.locator(candidates[0]).first

