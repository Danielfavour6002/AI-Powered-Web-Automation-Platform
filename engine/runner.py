"""Core execution engine for replaying tests."""

import asyncio
import time
import uuid
import shutil
from datetime import datetime
from pathlib import Path
from typing import List
from threading import Lock

# playwright imported lazily inside run_test() to avoid Lambda size issues

from core.config import Config
from core.models import Test, Step, ActionType
from core.logging import configure_logging, get_logger
from core.exceptions import StepFailedError
from engine.reporter import Reporter
from fusion.login_page import LoginPage
from fusion.reauth import check_and_handle_reauth
from fusion.wait import wait_for_any_idle

def run_sync(coro):
    import threading
    result = None
    exc = None
    def target():
        nonlocal result, exc
        try:
            result = asyncio.run(coro)
        except Exception as e:
            exc = e
    t = threading.Thread(target=target)
    t.start()
    t.join()
    if exc:
        raise exc
    return result

# Sync DB calls for the runner
def _get_test_sync(db_path: Path, test_id: str) -> Test:
    import core.database as db
    return run_sync(db.get_test(db_path, test_id))

def _get_steps_sync(db_path: Path, test_id: str) -> List[Step]:
    import core.database as db
    return run_sync(db.get_steps_for_test(db_path, test_id))

def _update_run_sync(db_path: Path, run_id: str, **kwargs) -> None:
    import core.database as db
    run_sync(db.update_run(db_path, run_id, **kwargs))

_run_lock = Lock()
logger = get_logger()
_cancelled_runs = set()

def cancel_active_run(run_id: str) -> bool:
    """Mark a run as cancelled so the background thread can abort gracefully."""
    _cancelled_runs.add(run_id)
    return True

def run_test(run_id: str, test_id: str, config: Config, 
             password: str, db_path: Path, 
             output_root: Path, headless: bool = True,
             slow_mo: int = 100) -> str:
    """Execute a test by replaying its steps."""
    import sys
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
    if not _run_lock.acquire(blocking=False):
        return "error"
        
    try:
        # 1. Load test + steps
        test = _get_test_sync(db_path, test_id)
        steps = _get_steps_sync(db_path, test_id)
        
        # 2. Create run_dir
        dt_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        uid = uuid.uuid4().hex[:8]
        consultant_dir = config.consultant or "unknown"
        pod_dir = config.fusion_pod or "unknown"
        run_dir = output_root / consultant_dir / pod_dir / f"run_{dt_str}_{uid}"
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # 3. Configure logging
        configure_logging(run_dir)
        
        # 4. Create Reporter
        reporter = Reporter(run_id, run_dir, db_path, config.consultant, config.fusion_pod, test.name, test.id)
        run_sync(reporter.start_run())
        
        _update_run_sync(db_path, run_id, run_dir=str(run_dir), step_count=len(steps))
        
        overall_status = "passed"
        error_msg = None
        
        from core.display import get_screen_resolution
        width, height = get_screen_resolution()
        
        # 5. Launch Playwright
        from playwright.sync_api import sync_playwright, expect, TimeoutError as PWTimeout
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=headless, 
                slow_mo=slow_mo,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-web-security",
                    "--no-sandbox",
                    "--disable-features=IsolateOrigins,site-per-process"
                ]
            )
            video_dir = run_dir / "video"
            context = browser.new_context(
                viewport={"width": width, "height": height}, 
                record_video_dir=video_dir,
                record_video_size={"width": width, "height": height},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"',
                    "sec-fetch-dest": "document",
                    "sec-fetch-mode": "navigate",
                    "sec-fetch-site": "none",
                    "sec-fetch-user": "?1",
                    "upgrade-insecure-requests": "1"
                }
            )
            context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            context.tracing.start(screenshots=True, snapshots=True, sources=True)
            page = context.new_page()
            
            try:
                screenshots_dir = run_dir / "screenshots"
                screenshots_dir.mkdir(parents=True, exist_ok=True)
                
                # 6. Oracle login
                is_oracle = config.is_oracle_fusion
                if is_oracle and steps:
                    first_url = (steps[0].selector or steps[0].value) if steps[0].action == ActionType.NAVIGATE else ""
                    if first_url and "idcs" not in first_url.lower():
                        logger.info("Performing automatic Oracle login")
                        login_page = LoginPage(page, screenshots_dir=screenshots_dir, is_oracle=True)
                        login_page.full_login(config.fusion_url, config.fusion_user, password)
                
                # 7. Execute steps
                for step in steps:
                    if run_id in _cancelled_runs:
                        logger.warning(f"Run {run_id} was cancelled by user.")
                        overall_status = "error"
                        error_msg = "Run cancelled by user"
                        break
                        
                    start_t = time.time()
                    ss_path = None
                    try:
                        # a. Check reauth
                        if is_oracle:
                            check_and_handle_reauth(page, config, password, screenshots_dir)
                            
                        # b. Execute action
                        logger.debug(f"Executing step {step.sequence}: {step.action.value} {step.selector}")
                        
                        def _get_locator(sel):
                            if sel.startswith("page.") or sel.startswith("expect("):
                                res = eval(sel, {"page": page, "expect": expect})
                                return res.first if hasattr(res, "first") else res
                            return page.locator(sel).first
                            
                        if step.action == ActionType.NAVIGATE:
                            url = step.selector or step.value
                            if is_oracle and ("oauth2" in url.lower() or "idcs" in url.lower()):
                                logger.info(f"Skipping recorded OAuth redirect: {url}")
                                dur_ms = int((time.time() - start_t) * 1000)
                                run_sync(reporter.record_step_result(step, "passed", "Auto-skipped OAuth redirect", None, dur_ms))
                                continue
                            page.goto(url, wait_until="domcontentloaded")
                            wait_for_any_idle(page, is_oracle)
                        elif step.action == ActionType.CLICK:
                            loc = _get_locator(step.selector)
                            loc.wait_for(state="attached", timeout=30000)
                            try:
                                loc.click(timeout=5000)
                            except Exception as e:
                                logger.warning(f"Standard click failed: {str(e)[:100]}. Falling back to JS click.")
                                loc.evaluate("el => el.click()")
                            wait_for_any_idle(page, is_oracle)
                        elif step.action == ActionType.FILL:
                            loc = _get_locator(step.selector)
                            loc.wait_for(state="attached", timeout=30000)
                            try:
                                loc.click(timeout=5000)
                            except:
                                pass # ignore if click fails, just try to fill
                                
                            val = password if (getattr(step, 'is_sensitive', False) or '[REDACTED]' in str(step.value)) else step.value
                            loc.fill(val, timeout=10000)
                        elif step.action == ActionType.SELECT:
                            _get_locator(step.selector).select_option(step.value)
                        elif step.action == ActionType.CHECK:
                            loc = _get_locator(step.selector)
                            loc.wait_for(state="attached", timeout=30000)
                            try:
                                loc.check(timeout=5000)
                            except Exception as e:
                                logger.warning(f"Standard check failed: {str(e)[:100]}. Falling back to JS click.")
                                loc.evaluate("el => { el.checked = true; el.dispatchEvent(new Event('change')); el.click(); }")
                        elif step.action == ActionType.UNCHECK:
                            loc = _get_locator(step.selector)
                            loc.wait_for(state="attached", timeout=30000)
                            try:
                                loc.uncheck(timeout=5000)
                            except Exception as e:
                                logger.warning(f"Standard uncheck failed: {str(e)[:100]}. Falling back to JS click.")
                                loc.evaluate("el => { el.checked = false; el.dispatchEvent(new Event('change')); el.click(); }")
                        elif step.action == ActionType.PRESS:
                            _get_locator(step.selector).press(step.value)
                        elif step.action == ActionType.WAIT:
                            _get_locator(step.selector).wait_for(state="visible")
                        elif step.action == ActionType.ASSERT_VISIBLE:
                            # If it's a direct AST string, it might have expect in it already, or not.
                            if step.selector.startswith("expect("):
                                eval(step.selector, {"page": page, "expect": expect})
                            else:
                                expect(_get_locator(step.selector)).to_be_visible()
                        elif step.action == ActionType.ASSERT_TEXT:
                            if step.selector.startswith("expect("):
                                eval(step.selector, {"page": page, "expect": expect})
                            else:
                                expect(_get_locator(step.selector)).to_have_text(step.value)

                        elif step.action == ActionType.SCREENSHOT:
                            pass # Screenshot taken below
                            
                        # c. Take screenshot
                        ss_name = f"{step.sequence:03d}_{step.action.value}.png"
                        ss_full_path = screenshots_dir / ss_name
                        page.screenshot(path=ss_full_path)
                        ss_path = ss_full_path
                        
                        dur_ms = int((time.time() - start_t) * 1000)
                        
                        # d. Record success
                        run_sync(reporter.record_step_result(step, "passed", "Success", ss_path, dur_ms))
                        
                    except Exception as e:
                        overall_status = "failed"
                        error_msg = str(e)
                        
                        # Try to capture failure screenshot
                        try:
                            ss_name = f"{step.sequence:03d}_failed.png"
                            ss_full_path = screenshots_dir / ss_name
                            page.screenshot(path=ss_full_path, full_page=True)
                            ss_path = ss_full_path
                        except Exception:
                            pass
                            
                        dur_ms = int((time.time() - start_t) * 1000)
                        run_sync(reporter.record_step_result(step, "failed", "Failed", ss_path, dur_ms, error_msg))
                        
                        # Mark rest as skipped
                        curr_idx = steps.index(step)
                        for remaining in steps[curr_idx+1:]:
                            run_sync(reporter.record_step_result(remaining, "skipped", "Skipped due to prior failure", None, 0))
                        
                        break
                        
            except Exception as fatal_e:
                logger.error(f"Fatal error during test run: {fatal_e}")
                overall_status = "error"
                error_msg = f"Fatal execution error: {str(fatal_e)}"
                
            finally:
                _cancelled_runs.discard(run_id)
                # 8. Cleanup
                logger.info("Saving trace and video... (this may take a few seconds)")
                trace_path = run_dir / "trace.zip"
                context.tracing.stop(path=trace_path)
                context.close()
                browser.close()
                
                # Get video path
                video_file = None
                if video_dir.exists():
                    v_files = list(video_dir.glob("*.webm"))
                    if v_files:
                        video_file = v_files[0]
                        
                _update_run_sync(
                    db_path, run_id, 
                    video_path=str(video_file) if video_file else None,
                    trace_path=str(trace_path)
                )
                
                run_sync(reporter.end_run(overall_status, error_msg))
                
        return overall_status
        
    finally:
        _run_lock.release()
