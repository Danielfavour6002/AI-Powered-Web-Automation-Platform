"""Oracle Fusion Login Page."""

from fusion.base_page import BasePage
from fusion.locators import LOGIN, HOME_LANDMARKS
from core.logging import get_logger

logger = get_logger()

class LoginPage(BasePage):
    """Oracle Fusion login interactions."""
    
    def assert_login_form_visible(self) -> None:
        """Check username, password, and submit are visible."""
        self.resolve_locator(LOGIN["username"]).wait_for(state="visible", timeout=10000)
        self.resolve_locator(LOGIN["password"]).wait_for(state="visible", timeout=10000)
        self.resolve_locator(LOGIN["submit"]).wait_for(state="visible", timeout=10000)
        logger.info("Login form is visible")

    def enter_username(self, user: str) -> None:
        """Enter username."""
        loc = self.resolve_locator(LOGIN["username"])
        loc.fill(user)
        logger.debug("Username entered")

    def enter_password(self, pwd: str) -> None:
        """Enter password securely."""
        loc = self.resolve_locator(LOGIN["password"])
        loc.fill(pwd)
        logger.debug("Password entered [REDACTED]")

    def click_submit(self) -> None:
        """Click submit and wait for idle."""
        loc = self.resolve_locator(LOGIN["submit"])
        loc.click()
        self.wait_for_idle(timeout_ms=45000)
        
    def assert_logged_in(self, timeout_ms: int = 60000) -> None:
        """Verify successful login."""
        # Wait for url to change from login
        self.page.wait_for_url(lambda url: "idcs" not in url and "signin" not in url.lower(), timeout=timeout_ms)
        
        # Check landmarks
        for landmark in HOME_LANDMARKS:
            if self.page.locator(landmark).count() > 0:
                logger.info("Successfully logged in")
                return
                
        raise AssertionError(f"Not logged in. Current URL: {self.page.url}")

    def full_login(self, url: str, user: str, password: str) -> None:
        """Perform full login flow."""
        self.navigate(url)
        self.screenshot("login_01_navigated")
        
        # Check if environment bypassed login (e.g. demo SSO or active session)
        for landmark in HOME_LANDMARKS:
            if self.page.locator(landmark).first.is_visible():
                logger.info("Login bypassed: Already on Home Page")
                return
                
        self.assert_login_form_visible()
        self.screenshot("login_02_form_visible")
        
        self.enter_username(user)
        self.screenshot("login_03_user_entered")
        
        self.enter_password(password)
        self.screenshot("login_04_pwd_entered")
        
        self.click_submit()
        self.screenshot("login_05_submitted")
        
        self.assert_logged_in()
        self.screenshot("login_06_logged_in")
