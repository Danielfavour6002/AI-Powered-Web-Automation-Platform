"""Oracle Fusion-specific wait utilities (Asynchronous)."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page

from core.logging import get_logger

logger = get_logger()

async def wait_for_fusion_idle(page: Page, timeout_ms: int = 30000) -> None:
    """Wait for Oracle Fusion specific spinners and network idle."""
    from playwright.async_api import TimeoutError as PWTimeout
    slice_ms = timeout_ms // 4

    # 1. Network idle
    logger.debug("Waiting for network idle")
    try:
        await page.wait_for_load_state("networkidle", timeout=slice_ms)
    except PWTimeout:
        pass

    # Spinners
    spinners = [
        "div.AFLoadingBlock:visible",
        "[aria-busy='true']:visible",
        ".AFLogo[role='progressbar']:visible",
        ".oj-progress-circle:visible",
        ".oj-conveyor-belt-item.oj-selected:visible"
    ]

    for spinner in spinners:
        logger.debug(f"Waiting for spinner to hide: {spinner}")
        try:
            await page.locator(spinner).wait_for(state="hidden", timeout=slice_ms)
        except PWTimeout:
            pass

async def wait_for_generic_idle(page: Page, timeout_ms: int = 15000) -> None:
    """Wait for network idle for non-Oracle pages."""
    from playwright.async_api import TimeoutError as PWTimeout
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except PWTimeout:
        pass

async def wait_for_any_idle(page: Page, is_oracle: bool, timeout_ms: int = 30000) -> None:
    """Route to the appropriate idle wait based on context."""
    if is_oracle:
        await wait_for_fusion_idle(page, timeout_ms)
    else:
        await wait_for_generic_idle(page, timeout_ms)

