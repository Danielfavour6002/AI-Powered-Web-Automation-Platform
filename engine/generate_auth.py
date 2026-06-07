"""
Auth state generator for Oracle Fusion pre-authentication.

Launches a headed Chromium browser, performs the full login flow using
async Playwright + LoginPage, then saves the storage state (cookies +
localStorage) to a JSON file so that recorder sessions can skip the
login screens entirely.

Usage (standalone):
    python -m engine.generate_auth [output_path] [target_url] [env_id]
"""

import sys
import os
import asyncio
from pathlib import Path


async def _async_main(output_path: str, target_url: str = None, env_id: str = None) -> None:
    """Async entry-point: launches browser, logs in, saves storage state."""
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from core.config import load_config, resolve_password
    from core.logging import get_logger
    from core.display import get_screen_resolution
    from fusion.login_page import LoginPage
    from playwright.async_api import async_playwright

    logger = get_logger()
    config = load_config(Path(".env"))

    # ── Resolve credentials ────────────────────────────────────────────────────
    if env_id:
        from core.database import get_environment
        db_path = Path(config.db_path)
        env = await get_environment(db_path, env_id)
        login_url = target_url if target_url else env.url
        fusion_user = env.username
        password = os.environ.get(env.password_env_var) or env.password_env_var
    else:
        login_url = target_url if target_url else config.fusion_url
        fusion_user = config.fusion_user
        password = resolve_password(config)

    width, height = get_screen_resolution()

    user_data_dir = Path("engine/.recorder_user_data")
    user_data_dir.mkdir(parents=True, exist_ok=True)

    # ── Launch async Playwright ────────────────────────────────────────────────
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            str(user_data_dir),
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--no-sandbox",
                "--start-maximized",
            ],
            viewport={"width": width, "height": height}
        )
        page = context.pages[0] if context.pages else await context.new_page()

        logger.info(f"Generating auth state for {fusion_user} on {login_url}...")
        login_page = LoginPage(page, is_oracle=True)

        try:
            # full_login is async – must be awaited
            await login_page.full_login(login_url, fusion_user, password)

            # Let cookies settle before snapshotting
            await page.wait_for_timeout(2000)

            state_path = Path(output_path)
            state_path.parent.mkdir(parents=True, exist_ok=True)
            await context.storage_state(path=str(state_path))
            logger.info(f"Auth state successfully saved to {state_path}")

        except Exception as e:
            logger.error(f"Failed to generate auth state: {e}")
            try:
                await page.screenshot(path="generate_auth_error.png")
            except Exception as e2:
                logger.error(f"Failed to save debug screenshot: {e2}")
            sys.exit(1)
        finally:
            await context.close()


def main(output_path: str, target_url: str = None, env_id: str = None) -> None:
    """Synchronous wrapper so the module can be called via subprocess."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(_async_main(output_path, target_url, env_id))


if __name__ == "__main__":
    out_path = sys.argv[1] if len(sys.argv) > 1 else "engine/.auth_state.json"
    t_url = sys.argv[2] if len(sys.argv) > 2 else None
    e_id = sys.argv[3] if len(sys.argv) > 3 else None
    main(out_path, t_url, e_id)
