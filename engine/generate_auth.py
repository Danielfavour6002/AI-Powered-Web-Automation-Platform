import sys
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

def main(output_path: str, target_url: str = None, env_id: str = None):
    # Setup path so we can import core modules
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from core.config import load_config, resolve_password
    from core.logging import get_logger
    from fusion.login_page import LoginPage
    import asyncio
    
    logger = get_logger()
    config = load_config(Path(".env"))
    
    if env_id:
        from core.database import get_environment
        db_path = Path(config.db_path)
        env = asyncio.run(get_environment(db_path, env_id))
        login_url = target_url if target_url else env.url
        fusion_user = env.username
        password = os.environ.get(env.password_env_var) or env.password_env_var
    else:
        login_url = target_url if target_url else config.fusion_url
        fusion_user = config.fusion_user
        password = resolve_password(config)
    
    from core.display import get_screen_resolution
    
    width, height = get_screen_resolution()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--no-sandbox",
                "--start-maximized"
            ]
        )
        context = browser.new_context(
            viewport={"width": width, "height": height}
        )
        page = context.new_page()
        
        logger.info(f"Generating auth state for {fusion_user} on {login_url}...")
        login_page = LoginPage(page, is_oracle=True)
        try:
            login_page.full_login(login_url, fusion_user, password)
            # Wait a moment for cookies to settle
            page.wait_for_timeout(2000)
            
            state_path = Path(output_path)
            state_path.parent.mkdir(parents=True, exist_ok=True)
            context.storage_state(path=str(state_path))
            logger.info(f"Auth state successfully saved to {state_path}")
        except Exception as e:
            logger.error(f"Failed to generate auth state: {e}")
            try:
                page.screenshot(path="generate_auth_error.png")
            except Exception as e2:
                logger.error(f"Failed to save debug screenshot: {e2}")
            sys.exit(1)
        finally:
            browser.close()

if __name__ == "__main__":
    out_path = sys.argv[1] if len(sys.argv) > 1 else "engine/.auth_state.json"
    t_url = sys.argv[2] if len(sys.argv) > 2 else None
    e_id = sys.argv[3] if len(sys.argv) > 3 else None
    main(out_path, t_url, e_id)
