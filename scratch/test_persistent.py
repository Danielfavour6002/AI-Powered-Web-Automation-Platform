import asyncio
import time
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
    user_data_dir = Path("engine/.test_user_data")
    if not user_data_dir.exists():
        user_data_dir.mkdir(parents=True, exist_ok=True)

    print("Step 1: Launching persistent context and setting a persistent cookie...")
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            str(user_data_dir),
            headless=True
        )
        page = await context.new_page()
        await page.goto("https://example.com")
        # Add a dummy persistent cookie (expires in 1 hour)
        await context.add_cookies([{
            "name": "qap_test_cookie",
            "value": "session_active_12345",
            "domain": "example.com",
            "path": "/",
            "expires": int(time.time()) + 3600
        }])
        cookies = await context.cookies()
        print(f"Cookies after setting: {[c['name'] for c in cookies]}")
        await context.close()

    print("\nStep 2: Re-launching persistent context and verifying cookie exists...")
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            str(user_data_dir),
            headless=True
        )
        cookies = await context.cookies()
        cookie_names = [c['name'] for c in cookies]
        print(f"Cookies on re-launch: {cookie_names}")
        assert "qap_test_cookie" in cookie_names, "Cookie was not persisted!"
        print("✅ Success: Persistent state was successfully persisted in user_data_dir!")
        await context.close()

if __name__ == "__main__":
    asyncio.run(main())
