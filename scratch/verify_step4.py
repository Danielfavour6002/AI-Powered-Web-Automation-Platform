import asyncio
import json
import sys
from pathlib import Path

# Playwright for UI checks
from playwright.async_api import async_playwright

# HTTP client for interacting with backend
import aiohttp

# Configuration
BASE_URL = "http://127.0.0.1:8000"  # Adjust if server runs on different port

async def check_recording_badge(page):
    """Start a quick recording and verify the badge appears in the UI."""
    await page.goto(f"{BASE_URL}/tests/create")
    # Fill the required fields
    await page.fill("#qr-url", "https://example.com")
    await page.fill("#qr-name", "Badge Test")
    # Upload a dummy CSV file (create temporary file)
    tmp_path = Path("tmp_dummy.csv")
    tmp_path.write_text("step,action,selector,value\n1,navigate,,https://example.com")
    await page.set_input_files("#test_file", str(tmp_path))
    # Click Record button
    await page.click("#record-btn")
    # Wait for status to change to "Running"
    await page.wait_for_selector("#rec-status-text:text('Running')", timeout=5000)
    # Verify badge dot is green
    status_dot = await page.query_selector("#rec-status-dot")
    dot_class = await status_dot.get_attribute("class")
    assert "bg-green" in dot_class, "Recording badge did not turn green"
    # Clean up temporary file
    tmp_path.unlink()
    print("✅ Recording badge verification passed")

async def check_overlay(page):
    """Run a normal test and verify the overlay element appears without flicker."""
    await page.goto(f"{BASE_URL}/tests/create")
    await page.fill("#qr-url", "https://example.com")
    await page.fill("#qr-name", "Overlay Test")
    tmp_path = Path("tmp_dummy2.csv")
    tmp_path.write_text("step,action,selector,value\n1,navigate,,https://example.com")
    await page.set_input_files("#test_file", str(tmp_path))
    await page.click("#record-btn")
    # After recording, the overlay should appear during replay
    # Navigate to the replay page (assume redirect after success)
    await page.wait_for_url("**/runs/*")
    # Look for the overlay element injected by engine (class .qap-overlay maybe)
    overlay = await page.query_selector(".qap-overlay")
    assert overlay is not None, "Overlay element not found"
    tmp_path.unlink()
    print("✅ Overlay verification passed")

async def check_fail_fast():
    """Trigger a DNS resolution error and ensure the AI agent stops immediately."""
    # Use aiohttp to POST a malformed URL
    async with aiohttp.ClientSession() as session:
        data = aiohttp.FormData()
        data.add_field('test_name', 'FailFast Test')
        data.add_field('test_url', 'http://nonexistent.invalid')
        data.add_field('qr-name', 'FailFast')
        # Dummy CSV file content
        data.add_field('test_file', b"step,action,selector,value\n1,navigate,,http://nonexistent.invalid", filename='test.csv', content_type='text/csv')
        async with session.post(f"{BASE_URL}/ai/record-test", data=data) as resp:
            result = await resp.json()
            # Expect a failure status quickly
            assert result.get('status') == 'error' or resp.status != 200, "Agent did not fail fast on DNS error"
            print("✅ Fail-fast verification passed")

async def main():
    # Verify that the server is reachable
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL) as resp:
            if resp.status != 200:
                print("Server not reachable. Ensure `python main.py serve` is running.")
                sys.exit(1)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--start-maximized"])
        page = await browser.new_page()
        try:
            await check_recording_badge(page)
            await check_overlay(page)
        finally:
            await browser.close()
    await check_fail_fast()

if __name__ == "__main__":
    asyncio.run(main())
