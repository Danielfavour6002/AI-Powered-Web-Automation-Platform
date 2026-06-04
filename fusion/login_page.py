"""Oracle Fusion Login Page (Asynchronous)."""

from fusion.base_page import BasePage
from fusion.locators import LOGIN, HOME_LANDMARKS
from core.logging import get_logger

logger = get_logger()

class LoginPage(BasePage):
    """Oracle Fusion login interactions (Asynchronous)."""
    
    async def assert_login_form_visible(self) -> None:
        """Check that the username field is visible (password may be hidden on IDCS two-step)."""
        loc_user = await self.resolve_locator(LOGIN["username"])
        await loc_user.wait_for(state="visible", timeout=15000)
        logger.info("Login form (username field) is visible")

    async def enter_username(self, user: str) -> None:
        """Enter username."""
        loc = await self.resolve_locator(LOGIN["username"])
        await loc.fill(user)
        logger.debug("Username entered")

    async def enter_password(self, pwd: str) -> None:
        """Enter password securely."""
        loc = await self.resolve_locator(LOGIN["password"])
        await loc.fill(pwd)
        logger.debug("Password entered [REDACTED]")

    async def click_submit(self) -> None:
        """Click submit and wait for idle."""
        loc = await self.resolve_locator(LOGIN["submit"])
        await loc.click()
        await self.wait_for_idle(timeout_ms=45000)
        
    async def assert_logged_in(self, timeout_ms: int = 60000) -> None:
        """Verify successful login — check home landmarks first, then URL."""
        # Fast path: if a home landmark is already visible, we're in
        for landmark in HOME_LANDMARKS:
            try:
                if await self.page.locator(landmark).first.is_visible():
                    logger.info("Successfully logged in (landmark detected)")
                    return
            except Exception:
                pass
        
        # Slow path: wait for URL to leave login/idcs pages
        try:
            await self.page.wait_for_url(
                lambda url: "idcs" not in url and "signin" not in url.lower(),
                timeout=timeout_ms
            )
        except Exception:
            pass  # URL may already be past login, check landmarks one more time
        
        # Final landmark check
        for landmark in HOME_LANDMARKS:
            try:
                if await self.page.locator(landmark).first.is_visible():
                    logger.info("Successfully logged in")
                    return
            except Exception:
                pass
        
        raise AssertionError(f"Not logged in after login flow. Current URL: {self.page.url}")

    async def full_login(self, url: str, user: str, password: str) -> None:
        """Perform full login flow, supporting both single-page and IDCS two-step login."""
        await self.navigate(url)
        await self.screenshot("login_01_navigated")
        
        # Check if environment bypassed login (e.g. demo SSO or active session)
        for landmark in HOME_LANDMARKS:
            if await self.page.locator(landmark).first.is_visible():
                logger.info("Login bypassed: Already on Home Page")
                return
                
        await self.assert_login_form_visible()
        await self.screenshot("login_02_form_visible")
        
        await self.enter_username(user)
        await self.screenshot("login_03_user_entered")
        
        # ── IDCS two-step: click "Next" if it appears after username entry ────
        # Oracle IDCS shows username first, then "Next" to reveal password field.
        # Standard environments show username + password on the same page.
        next_clicked = False
        try:
            next_loc = await self.resolve_locator(LOGIN["next_btn"], timeout_ms=4000)
            if await next_loc.is_visible():
                logger.info("IDCS two-step login detected — clicking Next")
                await next_loc.click(timeout=5000)
                await self.wait_for_idle(timeout_ms=10000)
                next_clicked = True
                await self.screenshot("login_03b_next_clicked")
        except Exception:
            pass  # No Next button — single-page login, continue normally
        
        # Now wait for password field (it should be visible after Next click,
        # or was always visible on single-page environments)
        try:
            loc_pwd = await self.resolve_locator(LOGIN["password"], timeout_ms=10000)
            await loc_pwd.wait_for(state="visible", timeout=10000)
        except Exception:
            logger.warning("Password field not visible after username entry — attempting to proceed")
        
        await self.enter_password(password)
        await self.screenshot("login_04_pwd_entered")
        
        await self.click_submit()
        await self.screenshot("login_05_submitted")
        
        await self.assert_logged_in()
        await self.screenshot("login_06_logged_in")


