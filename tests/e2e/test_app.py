import os
import socket
import threading
import time
import unittest
from pathlib import Path

import uvicorn
from playwright.sync_api import sync_playwright

from web.app import create_app

TEST_HOST = "127.0.0.1"
TEST_PORT = 8001
BASE_URL = f"http://{TEST_HOST}:{TEST_PORT}"


def wait_for_server(host: str, port: int, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            try:
                sock.connect((host, port))
                return
            except OSError:
                time.sleep(0.2)
    raise RuntimeError(f"Server did not respond on {host}:{port} within {timeout} seconds")


class UvicornServerThread(threading.Thread):
    def __init__(self, app, host: str, port: int):
        super().__init__(daemon=True)
        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level="warning",
            loop="asyncio",
            lifespan="on"
        )
        self.server = uvicorn.Server(config)

    def run(self) -> None:
        self.server.run()

    def stop(self) -> None:
        self.server.should_exit = True


class QAPlatformE2ETest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ["FUSION_URL"] = "https://example.com"
        os.environ["FUSION_USER"] = "test.user"
        os.environ["FUSION_POD"] = "LOCAL"
        os.environ["CONSULTANT"] = "CI"
        os.environ["DB_PATH"] = "data/qap_test.db"
        os.environ["OUTPUT_ROOT"] = "output_test"
        os.environ["HOST"] = TEST_HOST
        os.environ["PORT"] = str(TEST_PORT)

        Path("data").mkdir(parents=True, exist_ok=True)
        test_db = Path(os.environ["DB_PATH"])
        if test_db.exists():
            test_db.unlink()

        cls.app = create_app()
        cls.server_thread = UvicornServerThread(cls.app, TEST_HOST, TEST_PORT)
        cls.server_thread.start()
        wait_for_server(TEST_HOST, TEST_PORT)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server_thread.stop()
        cls.server_thread.join(timeout=5)

    def test_home_and_tests_pages_render(self) -> None:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(BASE_URL, wait_until="networkidle", timeout=10000)
            self.assertIn("QA Dashboard", page.title())
            self.assertTrue(page.is_visible("text=View All Tests"))

            page.goto(f"{BASE_URL}/tests", wait_until="networkidle", timeout=10000)
            self.assertTrue(page.is_visible("text=New Test"))

            page.goto(f"{BASE_URL}/tests/create", wait_until="networkidle", timeout=10000)
            self.assertTrue(page.is_visible("#cr-name"))
            self.assertTrue(page.is_visible("#cr-url"))
            browser.close()

    def test_can_create_test_via_api_and_see_it_in_list(self) -> None:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(f"{BASE_URL}/tests/create", wait_until="networkidle", timeout=10000)

            payload = page.evaluate(
                """async () => {
                    const res = await fetch('/api/tests', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            name: 'E2E Smoke Test',
                            url: 'https://example.com',
                            mode: 'recorded'
                        })
                    });
                    return res.json();
                }"""
            )

            self.assertEqual(payload["data"]["name"], "E2E Smoke Test")
            page.goto(f"{BASE_URL}/tests", wait_until="networkidle", timeout=10000)
            self.assertTrue(page.is_visible("text=E2E Smoke Test"))
            browser.close()


if __name__ == "__main__":
    unittest.main()
