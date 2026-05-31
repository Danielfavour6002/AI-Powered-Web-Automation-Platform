"""Session expiration handling."""
from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page

from core.config import Config
from fusion.login_page import LoginPage
from core.logging import get_logger

logger = get_logger()

def check_and_handle_reauth(page: Page, config: Config, password: str, screenshots_dir: Path | None = None) -> bool:
    """Detect if session expired and re-authenticate if necessary."""
    url = page.url
    if "idcs" in url or "signin" in url.lower():
        logger.warning("Session expired — re-authenticating")
        login_page = LoginPage(page, screenshots_dir=screenshots_dir, is_oracle=True)
        login_page.full_login(config.fusion_url, config.fusion_user, password)
        return True
    return False
