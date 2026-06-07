"""Core execution engine for replaying tests asynchronously."""

import asyncio
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from core.config import Config
from core.models import Test, Step, ActionType, ClientProfile
from core.logging import configure_logging, get_logger
from core.exceptions import StepFailedError
from engine.reporter import Reporter
from engine.context import RunContext
from fusion.login_page import LoginPage
from fusion.reauth import check_and_handle_reauth
from fusion.wait import wait_for_any_idle

logger = get_logger()
_cancelled_runs = set()


def cancel_active_run(run_id: str) -> bool:
    """Mark a run as cancelled so the execution loop can abort gracefully."""
    _cancelled_runs.add(run_id)
    return True


async def run_test(run_id: str, test_id: str, config: Config, 
                   password: str, db_path: Path, 
                   output_root: Path, headless: bool = True,
                   slow_mo: int = 100, client_profile: Optional[ClientProfile] = None,
                   run_params: Optional[Dict[str, Any]] = None) -> str:
    """
    Execute a test by replaying its steps asynchronously.
    
    Args:
        run_id: Unique identifier for this execution run.
        test_id: Unique identifier of the test to execute.
        config: Application configuration.
        password: Resolved client password.
        db_path: Path to the SQLite database.
        output_root: Root directory for reports/screenshots/videos.
        headless: Run browser in headless mode.
        slow_mo: Milliseconds to slow down Playwright actions.
        client_profile: ClientProfile entity containing custom variables.
        run_params: Dictionary of run-specific variables.
        
    Returns:
        str: Final status of the run ('passed', 'failed', or 'error').
    """
    import sys
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    import core.database as db
    
    try:
        # 1. Load test + steps
        test = await db.get_test(db_path, test_id)
        steps = await db.get_steps_for_test(db_path, test_id)
        
        # 2. Create run_dir
        dt_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        uid = uuid.uuid4().hex[:8]
        consultant_dir = config.consultant or "unknown"
        pod_dir = config.fusion_pod or "unknown"
        
        if client_profile:
            consultant_dir = client_profile.consultant_initials or consultant_dir
            pod_dir = client_profile.pod_identifier or pod_dir
            
        run_dir = output_root / consultant_dir / pod_dir / f"run_{dt_str}_{uid}"
        run_dir.mkdir(parents=True, exist_ok=True)
        
        # 3. Configure logging
        configure_logging(run_dir)
        
        # 4. Create Reporter
        reporter = Reporter(run_id, run_dir, db_path, consultant_dir, pod_dir, test.name, test.id)
        await reporter.start_run()
        
        await db.update_run(db_path, run_id, run_dir=str(run_dir), step_count=len(steps))
        
        overall_status = "passed"
        error_msg = None
        
        from core.display import get_screen_resolution
        width, height = get_screen_resolution()
        
        # 5. Launch Playwright
        from playwright.async_api import async_playwright, expect, TimeoutError as PWTimeout
        async with async_playwright() as p:
            # Determine browser type from global configuration
            browser_type = getattr(p, config.browser or "chromium")
            
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--no-sandbox",
                "--disable-features=IsolateOrigins,site-per-process"
            ]
            if not headless:
                launch_args.append("--start-maximized")
            
            browser = await browser_type.launch(
                headless=headless, 
                slow_mo=slow_mo,
                args=launch_args
            )
            video_dir = run_dir / "video"
            
            # Setup custom headers
            extra_headers = {
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
            
            # Parse custom client headers/cookies
            custom_cookies = []
            if client_profile:
                if client_profile.extra_headers:
                    try:
                        import json
                        headers_dict = json.loads(client_profile.extra_headers)
                        extra_headers.update(headers_dict)
                    except Exception as he:
                        logger.warning(f"Failed to parse extra headers: {he}")
                if client_profile.extra_cookies:
                    try:
                        import json
                        custom_cookies = json.loads(client_profile.extra_cookies)
                    except Exception as ce:
                        logger.warning(f"Failed to parse extra cookies: {ce}")
            
            context_opts = {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "extra_http_headers": extra_headers
            }
            if not headless:
                context_opts["no_viewport"] = True
            else:
                context_opts["viewport"] = {"width": width, "height": height}
            
            # If video is requested in global configuration
            if config.enable_videos and config.video_width > 0:
                context_opts["record_video_dir"] = video_dir
                context_opts["record_video_size"] = {"width": config.video_width, "height": config.video_height}
                
            playwright_context = await browser.new_context(**context_opts)
            await playwright_context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Inject on-screen visual overlay
            overlay_script = """
            (function() {
              function injectOverlay() {
                if (document.getElementById('qap-replay-overlay-root')) return;

                const container = document.createElement('div');
                container.id = 'qap-replay-overlay-root';
                container.style.position = 'fixed';
                container.style.bottom = '20px';
                container.style.right = '20px';
                container.style.zIndex = '2147483647';
                container.style.pointerEvents = 'none';
                
                const shadow = container.attachShadow({mode: 'open'});
                shadow.innerHTML = `
                  <style>
                    .card {
                      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                      background: rgba(10, 14, 35, 0.88);
                      backdrop-filter: blur(12px) saturate(180%);
                      -webkit-backdrop-filter: blur(12px) saturate(180%);
                      border: 1px solid rgba(168, 85, 247, 0.35);
                      box-shadow: 0 12px 40px -4px rgba(0, 0, 0, 0.5), 0 8px 16px -8px rgba(0, 0, 0, 0.5), 0 0 15px rgba(168, 85, 247, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.1);
                      border-radius: 14px;
                      padding: 18px;
                      color: #f8fafc;
                      width: 340px;
                      box-sizing: border-box;
                      transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
                      pointer-events: auto;
                    }
                    .header {
                      display: flex;
                      justify-content: space-between;
                      align-items: center;
                      margin-bottom: 12px;
                      font-size: 11px;
                      text-transform: uppercase;
                      letter-spacing: 0.08em;
                      color: #94a3b8;
                      font-weight: 700;
                    }
                    .badge {
                      padding: 3px 10px;
                      border-radius: 9999px;
                      font-weight: 700;
                      font-size: 10px;
                      border: 1px solid transparent;
                    }
                    .badge-executing {
                      background: rgba(168, 85, 247, 0.12);
                      color: #c084fc;
                      border-color: rgba(168, 85, 247, 0.3);
                      animation: pulse 1.8s infinite;
                    }
                    .badge-success {
                      background: rgba(16, 185, 129, 0.12);
                      color: #34d399;
                      border-color: rgba(16, 185, 129, 0.3);
                    }
                    .badge-failed {
                      background: rgba(244, 63, 94, 0.12);
                      color: #f87171;
                      border-color: rgba(244, 63, 94, 0.3);
                    }
                    .action-row {
                      display: flex;
                      align-items: center;
                      gap: 12px;
                    }
                    .icon {
                      font-size: 22px;
                      display: flex;
                      align-items: center;
                      justify-content: center;
                      width: 40px;
                      height: 40px;
                      background: rgba(168, 85, 247, 0.15);
                      border: 1px solid rgba(168, 85, 247, 0.25);
                      border-radius: 10px;
                      flex-shrink: 0;
                      box-shadow: 0 4px 10px rgba(168, 85, 247, 0.1);
                    }
                    .action-info {
                      flex: 1;
                      min-width: 0;
                    }
                    .action-type {
                      font-weight: 700;
                      font-size: 14px;
                      color: #ffffff;
                      margin-bottom: 2px;
                      text-transform: uppercase;
                      letter-spacing: 0.02em;
                    }
                    .description {
                      font-size: 12.5px;
                      color: #cbd5e1;
                      line-height: 1.4;
                      margin: 0;
                      white-space: nowrap;
                      overflow: hidden;
                      text-overflow: ellipsis;
                    }
                    @keyframes pulse {
                      0%, 100% { opacity: 1; }
                      50% { opacity: 0.6; }
                    }
                  </style>
                  <div class="card" id="qap-card">
                    <div class="header">
                      <span id="step-label">QA Platform Replay</span>
                      <span class="badge badge-executing" id="status-badge">EXECUTING</span>
                    </div>
                    <div class="action-row">
                      <div class="icon" id="action-icon">🤖</div>
                      <div class="action-info">
                        <div class="action-type" id="action-title">Initializing</div>
                        <p class="description" id="step-desc">Preparing test context...</p>
                      </div>
                    </div>
                  </div>
                `;
                document.body.appendChild(container);
                updateFromStorage(shadow);
              }

              function updateFromStorage(shadow) {
                const dataStr = sessionStorage.getItem('qap_replay_step');
                if (!dataStr) return;
                try {
                  const data = JSON.parse(dataStr);
                  const card = shadow.getElementById('qap-card');
                  const stepLabel = shadow.getElementById('step-label');
                  const statusBadge = shadow.getElementById('status-badge');
                  const actionIcon = shadow.getElementById('action-icon');
                  const actionTitle = shadow.getElementById('action-title');
                  const stepDesc = shadow.getElementById('step-desc');
                  
                  stepLabel.textContent = `Step ${data.sequence}`;
                  stepDesc.textContent = data.description || '';
                  actionTitle.textContent = data.action.toUpperCase();
                  
                  statusBadge.className = 'badge';
                  if (data.status === 'passed') {
                    statusBadge.classList.add('badge-success');
                    statusBadge.textContent = 'SUCCESS';
                  } else if (data.status === 'failed') {
                    statusBadge.classList.add('badge-failed');
                    statusBadge.textContent = 'FAILED';
                  } else {
                    statusBadge.classList.add('badge-executing');
                    statusBadge.textContent = 'EXECUTING';
                  }
                  
                  const icons = {
                    'navigate': '🌐',
                    'click': '🖱️',
                    'fill': '✍️',
                    'select': '🔽',
                    'check': '✅',
                    'uncheck': '🔲',
                    'press': '⌨️',
                    'wait': '⏳',
                    'assert_visible': '👁️',
                    'assert_text': '📝',
                    'screenshot': '📸'
                  };
                  actionIcon.textContent = icons[data.action.toLowerCase()] || '🤖';
                } catch(e) {}
              }

              window.updateQAPOverlay = function(sequence, action, description, status) {
                const data = { sequence, action, description, status };
                sessionStorage.setItem('qap_replay_step', JSON.stringify(data));
                
                const root = document.getElementById('qap-replay-overlay-root');
                if (root && root.shadowRoot) {
                  updateFromStorage(root.shadowRoot);
                }
              };

              if (document.body) {
                injectOverlay();
              } else {
                document.addEventListener('DOMContentLoaded', injectOverlay);
              }
            })();
            """
            await playwright_context.add_init_script(overlay_script)
            if custom_cookies:
                await playwright_context.add_cookies(custom_cookies)
                
            if config.enable_traces:
                await playwright_context.tracing.start(screenshots=True, snapshots=True, sources=True)

            page = await playwright_context.new_page()
            
            # 6. Initialize RunContext & Token Substitution Resolver
            run_context = RunContext(
                page=page,
                config=config,
                password=password,
                run_dir=run_dir,
                run_id=run_id,
                test_id=test_id,
                is_oracle=config.is_oracle_fusion,
                reporter=reporter,
                client=client_profile,
                run_params=run_params or {}
            )
            
            try:
                screenshots_dir = run_context.screenshots_dir
                
                # Oracle Auto-Login Helper
                # Always attempt auto-login for Oracle tests — even if the
                # first recorded step is an IDCS/OAuth redirect (which means
                # the user wasn't logged in during recording).  We log in
                # first so those recorded redirect steps can be safely skipped.
                is_oracle = run_context.is_oracle
                did_auto_login = False
                if is_oracle:
                    login_page = LoginPage(page, screenshots_dir=screenshots_dir, is_oracle=True)
                    target_url = client_profile.base_url if client_profile else config.fusion_url
                    username = client_profile.username if client_profile else config.fusion_user
                    logger.info(f"Performing automatic Oracle login to: {target_url}")
                    try:
                        await login_page.full_login(target_url, username, password)
                        did_auto_login = True
                        logger.info("Auto-login succeeded")
                    except Exception as login_err:
                        # Fail fast — if we can't log in there is no point
                        # replaying the recorded steps; they will all fail.
                        raise StepFailedError(
                            "login",
                            f"Auto-login failed — unable to authenticate. "
                            f"Check credentials in Settings or re-generate the auth state. "
                            f"Detail: {login_err}"
                        )
                
                # 7. Execute steps sequentially
                for step in steps:
                    if run_id in _cancelled_runs:
                        logger.warning(f"Run {run_id} cancelled by user request.")
                        overall_status = "error"
                        error_msg = "Run cancelled by user"
                        break
                        
                    start_t = time.time()
                    ss_path = None
                    
                    # Intercept and dynamically substitute dynamic tokens
                    resolved_selector = run_context.resolve(step.selector)
                    resolved_value = run_context.resolve(step.value)
                    
                    try:
                        import json
                        try:
                            await page.evaluate(
                                f"window.updateQAPOverlay({step.sequence}, {json.dumps(step.action.value)}, {json.dumps(step.description)}, 'executing')"
                            )
                        except Exception:
                            pass
                        # a. Check Oracle re-authentication
                        if is_oracle and did_auto_login:
                            await check_and_handle_reauth(page, config, password, screenshots_dir)
                            
                        # b. Execute action
                        logger.debug(f"Executing step {step.sequence}: {step.action.value} | Selector: {resolved_selector}")
                        
                        def _get_locator(sel):
                            if sel.startswith("page.") or sel.startswith("expect("):
                                res = eval(sel, {"page": page, "expect": expect})
                                return res.first if hasattr(res, "first") else res
                            return page.locator(sel).first
                            
                        if step.action == ActionType.NAVIGATE:
                            url = resolved_selector or resolved_value
                            if is_oracle and did_auto_login and (
                                "oauth2" in url.lower()
                                or "idcs" in url.lower()
                                or "/signin" in url.lower()
                            ):
                                logger.info(f"Skipping recorded login/OAuth redirect: {url}")
                                dur_ms = int((time.time() - start_t) * 1000)
                                await reporter.record_step_result(step, "passed", "Auto-skipped login/OAuth redirect", None, dur_ms)
                                continue
                            await page.goto(url, wait_until="domcontentloaded")
                            await wait_for_any_idle(page, is_oracle)
                            
                            # ── Detect Oracle auth-state failure ───────────────────
                            # If the page lands on /signin after auto-login it means the
                            # auth state was invalid or expired.  Fail fast with a clear
                            # message rather than letting the next step time-out silently.
                            if is_oracle and did_auto_login:
                                current_url = page.url.lower()
                                page_text = ""
                                try:
                                    page_text = (await page.inner_text("body")).lower()
                                except Exception:
                                    pass
                                if (
                                    "/signin" in current_url
                                    or "idcs" in current_url
                                    or "cannot bookmark and access the /signin" in page_text
                                    or "you cannot bookmark" in page_text
                                ):
                                    raise StepFailedError(
                                        step.id,
                                        f"Oracle session expired or auth state is invalid — "
                                        f"redirected to login at {page.url}. "
                                        "Re-generate auth state or check credentials in Settings."
                                    )
                            # Inject centering CSS for IDCS sign-in page, including iframes
                            if is_oracle and ("/signin" in page.url.lower() or "idcs" in page.url.lower()):
                                try:
                                    await page.evaluate("""
(() => {
  const apply = (doc) => {
    doc.documentElement.style.display = 'flex';
    doc.documentElement.style.justifyContent = 'center';
    doc.documentElement.style.alignItems = 'center';
    doc.documentElement.style.height = '100vh';
    doc.documentElement.style.margin = '0';
    if (doc.body) {
      doc.body.style.display = 'flex';
      doc.body.style.justifyContent = 'center';
      doc.body.style.alignItems = 'center';
      doc.body.style.height = '100vh';
      doc.body.style.margin = '0';
    }
  };
  // Apply to main document
  apply(document);
  // Apply to same-origin iframes
  document.querySelectorAll('iframe').forEach(frame => {
    try { apply(frame.contentDocument); } catch (e) {}
  });
  // Retry a few times in case later scripts override
  let attempts = 3;
  const retry = () => {
    if (attempts-- <= 0) return;
    apply(document);
    document.querySelectorAll('iframe').forEach(frame => {
      try { apply(frame.contentDocument); } catch (e) {}
    });
    setTimeout(retry, 1000);
  };
  setTimeout(retry, 1000);
})();
""")
                                except Exception:
                                    pass
                            
                        elif step.action == ActionType.CLICK:
                            loc = _get_locator(resolved_selector)
                            await loc.wait_for(state="attached", timeout=30000)
                            try:
                                await loc.click(timeout=5000)
                            except Exception as e:
                                logger.warning(f"Standard click failed: {str(e)[:100]}. Falling back to JS click.")
                                await loc.evaluate("el => el.click()")
                            await wait_for_any_idle(page, is_oracle)
                            
                        elif step.action == ActionType.FILL:
                            loc = _get_locator(resolved_selector)
                            await loc.wait_for(state="attached", timeout=30000)
                            try:
                                await loc.click(timeout=5000)
                            except:
                                pass
                                
                            val = password if (getattr(step, 'is_sensitive', False) or '[REDACTED]' in str(resolved_value)) else resolved_value
                            await loc.fill(val, timeout=10000)
                            
                        elif step.action == ActionType.SELECT:
                            await _get_locator(resolved_selector).select_option(resolved_value)
                            
                        elif step.action == ActionType.CHECK:
                            loc = _get_locator(resolved_selector)
                            await loc.wait_for(state="attached", timeout=30000)
                            try:
                                await loc.check(timeout=5000)
                            except Exception as e:
                                logger.warning(f"Standard check failed: {str(e)[:100]}. Falling back to JS click.")
                                await loc.evaluate("el => { el.checked = true; el.dispatchEvent(new Event('change')); el.click(); }")
                                
                        elif step.action == ActionType.UNCHECK:
                            loc = _get_locator(resolved_selector)
                            await loc.wait_for(state="attached", timeout=30000)
                            try:
                                await loc.uncheck(timeout=5000)
                            except Exception as e:
                                logger.warning(f"Standard uncheck failed: {str(e)[:100]}. Falling back to JS click.")
                                await loc.evaluate("el => { el.checked = false; el.dispatchEvent(new Event('change')); el.click(); }")
                                
                        elif step.action == ActionType.PRESS:
                            await _get_locator(resolved_selector).press(resolved_value)
                            
                        elif step.action == ActionType.WAIT:
                            await _get_locator(resolved_selector).wait_for(state="visible")
                            
                        elif step.action == ActionType.ASSERT_VISIBLE:
                            if resolved_selector.startswith("expect("):
                                await eval(resolved_selector, {"page": page, "expect": expect})
                            else:
                                await expect(_get_locator(resolved_selector)).to_be_visible()
                                
                        elif step.action == ActionType.ASSERT_TEXT:
                            if resolved_selector.startswith("expect("):
                                await eval(resolved_selector, {"page": page, "expect": expect})
                            else:
                                await expect(_get_locator(resolved_selector)).to_have_text(resolved_value)
                                
                        elif step.action == ActionType.SCREENSHOT:
                            pass
                            
                        # c. Take screenshot using screenshot quality from config
                        ss_path = None
                        if config.enable_screenshots:
                            ss_name = f"{step.sequence:03d}_{step.action.value}.png"
                            ss_full_path = screenshots_dir / ss_name
                            await page.screenshot(path=ss_full_path, type=(config.screenshot_format.lower() if config.screenshot_format else "png"))
                            ss_path = ss_full_path
                        
                        dur_ms = int((time.time() - start_t) * 1000)
                        
                        # Update visual overlay
                        try:
                            import json
                            await page.evaluate(
                                f"window.updateQAPOverlay({step.sequence}, {json.dumps(step.action.value)}, {json.dumps(step.description)}, 'passed')"
                            )
                            if not headless:
                                await page.wait_for_timeout(500)
                        except Exception:
                            pass
                        
                        # d. Record step execution success
                        await reporter.record_step_result(step, "passed", "Success", ss_path, dur_ms)
                        
                    except Exception as e:
                        overall_status = "failed"
                        error_msg = str(e)
                        
                        # Update visual overlay
                        try:
                            import json
                            await page.evaluate(
                                f"window.updateQAPOverlay({step.sequence}, {json.dumps(step.action.value)}, {json.dumps(step.description)}, 'failed')"
                            )
                            if not headless:
                                await page.wait_for_timeout(1500)
                        except Exception:
                            pass
                        
                        # Capture fail-safe screenshots
                        if config.enable_screenshots:
                            try:
                                ss_name = f"{step.sequence:03d}_failed.png"
                                ss_full_path = screenshots_dir / ss_name
                                await page.screenshot(path=ss_full_path, full_page=True)
                                ss_path = ss_full_path
                            except Exception:
                                pass
                            
                        dur_ms = int((time.time() - start_t) * 1000)
                        await reporter.record_step_result(step, "failed", "Failed", ss_path, dur_ms, error_msg)
                        
                        # Mark rest as skipped
                        curr_idx = steps.index(step)
                        for remaining in steps[curr_idx+1:]:
                            await reporter.record_step_result(remaining, "skipped", "Skipped due to prior failure", None, 0)
                        
                        break
                        
            except Exception as fatal_e:
                logger.error(f"Fatal error during async test execution: {fatal_e}")
                overall_status = "error"
                error_msg = f"Fatal execution error: {str(fatal_e)}"
                
            finally:
                _cancelled_runs.discard(run_id)
                logger.info("Saving session trace and video recording captures...")
                
                # Stop tracing
                trace_path = run_dir / "trace.zip"
                if config.enable_traces:
                    try:
                        await playwright_context.tracing.stop(path=trace_path)
                    except Exception:
                        pass
                    
                await playwright_context.close()
                await browser.close()
                
                # Scan for video captures
                video_file = None
                if video_dir.exists():
                    v_files = list(video_dir.glob("*.webm"))
                    if v_files:
                        video_file = v_files[0]
                        
                await db.update_run(
                    db_path, run_id, 
                    video_path=str(video_file) if video_file else None,
                    trace_path=str(trace_path)
                )
                
                await reporter.end_run(overall_status, error_msg)
                
        return overall_status
        
    except Exception as startup_err:
        logger.error(f"Runner failed to initialize: {startup_err}")
        await db.update_run(db_path, run_id, status="error", error_message=str(startup_err))
        return "error"
