"""Asynchronous AI-Guided Browser Driving Agent for QA Platform."""

import asyncio
import os
import json
import sys
import time
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List

from core.database import get_test, get_steps_for_test, update_run
from core.config import Config
from core.models import ClientProfile, Step, ActionType
from core.logging import get_logger
from core.security import sanitize_step
from fusion.login_page import LoginPage
from fusion.wait import wait_for_any_idle

def _sanitize_selector(selector: str) -> str:
    """Escape problematic characters in CSS selectors.
    Handles IDs that contain ':' by converting to an attribute selector.
    Only modifies selectors that start with '#'.
    """
    # If selector is an ID selector (starts with '#')
    if selector.startswith('#'):
        clean = selector[1:]  # remove leading '#'
        if ':' in clean:
            # Use attribute selector to match the exact id value
            return f"[id='{clean}']"
        # No colon, safe to use as is (remove leading '#')
        return f"#{clean}"
    # Non-ID selectors are returned unchanged
    return selector
    """Escape problematic characters in CSS selectors.
    Currently handles ':' by converting to an attribute selector.
    """
    if ':' in selector:
        return f"[id='{selector}']"
    return selector

logger = get_logger()

# In-memory streaming queues and resume events for pause/resume control
agent_log_queues: Dict[str, asyncio.Queue] = {}
agent_resume_events: Dict[str, asyncio.Event] = {}
agent_status: Dict[str, str] = {}  # "running", "stalled", "paused", "done", "failed"


async def push_agent_log(run_id: str, data: Dict[str, Any], _main_loop=None) -> None:
    """Push a real-time progress update to the run's SSE queue.
    
    When called from within the main (uvicorn) event loop: puts directly.
    When called from a background thread: bridges via call_soon_threadsafe.
    """
    if run_id not in agent_log_queues:
        agent_log_queues[run_id] = asyncio.Queue()
    queue = agent_log_queues[run_id]
    
    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None
    
    if running_loop is not None:
        # We're inside an event loop — put directly
        await queue.put(data)
    elif _main_loop is not None:
        # We're in a thread — bridge to the main loop
        _main_loop.call_soon_threadsafe(queue.put_nowait, data)
    else:
        # Best effort
        try:
            queue.put_nowait(data)
        except Exception:
            pass


def get_agent_queue(run_id: str) -> asyncio.Queue:
    """Retrieve or create the SSE queue for a specific run."""
    if run_id not in agent_log_queues:
        agent_log_queues[run_id] = asyncio.Queue()
    return agent_log_queues[run_id]


async def signal_resume_agent(run_id: str) -> None:
    """Signal a paused/stalled agent to resume execution."""
    if run_id in agent_resume_events:
        agent_resume_events[run_id].set()
        agent_status[run_id] = "running"
        await push_agent_log(run_id, {"type": "status", "status": "running", "message": "User resumed agent execution"})


async def run_autonomous_agent(run_id: str, test_id: str, api_key: str, output_root: Path,
                               override_config: Optional[Config] = None, override_password: Optional[str] = None):
    """
    Executes a test autonomously step-by-step using a custom LLM driving loop in async Playwright.
    Updates live status via Server-Sent Events and features 30-sec stall checks.
    """
    from playwright.async_api import async_playwright, expect
    from litellm import completion
    import core.database as db
    
    config = override_config
    db_path = Path(config.db_path)
    
    agent_status[run_id] = "running"
    agent_resume_events[run_id] = asyncio.Event()
    
    # 1. Load test and steps
    test = await db.get_test(db_path, test_id)
    steps = await db.get_steps_for_test(db_path, test_id)
    
    if not steps:
        await update_run(db_path, run_id, status="failed")
        await push_agent_log(run_id, {"type": "error", "message": "No steps found to execute"})
        return
        
    await update_run(db_path, run_id, status="running")
    await push_agent_log(run_id, {"type": "log", "message": f"Initializing AI-Guided Replay for '{test.name}'"})
    
    # Resolve target URL and client details
    target_url = test.url
    client_profile: Optional[ClientProfile] = None
    
    # Check if a client profile is linked (we retrieve it from the run database record)
    run_rec = await db.get_run(db_path, run_id)
    if run_rec.client_id:
        try:
            client_profile = await db.get_client(db_path, run_rec.client_id)
            target_url = client_profile.base_url
        except Exception:
            pass
            
    # Setup worker paths
    dt_str = datetime_str = time.strftime("%Y%m%d_%H%M%S")
    run_dir = output_root / (config.consultant or "unknown") / (config.fusion_pod or "unknown") / f"run_agent_{dt_str}"
    run_dir.mkdir(parents=True, exist_ok=True)
    screenshots_dir = run_dir / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    
    await db.update_run(db_path, run_id, run_dir=str(run_dir), step_count=len(steps))
    
    # Parse LLM config
    provider = "openai"
    model = "gpt-4o"
    temperature = 0.5
    
    active_prov = await db.get_active_llm_provider(db_path)
    if active_prov:
        provider = active_prov.name
        model = active_prov.model_name
        temperature = active_prov.temperature
        
    # Configure API Keys in LiteLLM environment
    if provider == "openai":
        os.environ["OPENAI_API_KEY"] = api_key
    elif provider == "gemini":
        os.environ["GEMINI_API_KEY"] = api_key
    elif provider == "anthropic":
        os.environ["ANTHROPIC_API_KEY"] = api_key
        
    async with async_playwright() as p:
        launch_args = ["--disable-web-security", "--no-sandbox"]
        launch_args.append("--start-maximized")
        
        browser = await p.chromium.launch(
            headless=False,  # Make it headed so the consultant can view it locally
            args=launch_args
        )
        playwright_context = await browser.new_context(
            no_viewport=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
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
                  <span id="step-label">AI Agent Replay</span>
                  <span class="badge badge-executing" id="status-badge">EXECUTING</span>
                </div>
                <div class="action-row">
                  <div class="icon" id="action-icon">🤖</div>
                  <div class="action-info">
                    <div class="action-type" id="action-title">Initializing</div>
                    <p class="description" id="step-desc">Preparing autonomous test context...</p>
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
        page = await playwright_context.new_page()
        
        # Determine final navigation URL: prioritize seeded_reports_url if set
        seeded_url = config.seeded_reports_url.strip() if hasattr(config, "seeded_reports_url") else ""
        if seeded_url:
            logger.info(f"Using seeded reports URL from config: {seeded_url}")
            target_url = seeded_url
        # Log navigation attempt
        await push_agent_log(run_id, {"type": "log", "message": f"Browser opened. Navigating to base URL: {target_url}"})
        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)  # 60s timeout
        except Exception as nav_err:
            logger.error(f"Navigation to {target_url} failed: {nav_err}")
            await push_agent_log(run_id, {"type": "error", "message": f"Failed to navigate to {target_url}: {nav_err}"})
            # Attempt fallback to test.url if different
            if target_url != test.url:
                try:
                    await page.goto(test.url, wait_until="domcontentloaded", timeout=60000)
                    await push_agent_log(run_id, {"type": "log", "message": f"Fallback navigation to original test URL succeeded: {test.url}"})
                except Exception as fallback_err:
                    logger.error(f"Fallback navigation also failed: {fallback_err}")
                    await push_agent_log(run_id, {"type": "error", "message": f"Fallback navigation failed: {fallback_err}"})
                    raise
                
        # Oracle Login Helper
        if client_profile and override_password:
            logger.info("Performing auto-login inside autonomous driver")
            await push_agent_log(run_id, {"type": "log", "message": "Pre-authenticating credentials..."})
            login_page = LoginPage(page, screenshots_dir=screenshots_dir, is_oracle=True)
            await login_page.full_login(target_url, client_profile.username, override_password)
            
        step_idx = 0
        overall_status = "passed"
        
        while step_idx < len(steps):
            step = steps[step_idx]
            await push_agent_log(run_id, {"type": "step_start", "sequence": step.sequence, "description": step.description})
            
            # Update visual overlay
            try:
                import json
                await page.evaluate(
                    f"window.updateQAPOverlay({step.sequence}, {json.dumps(step.action.value)}, {json.dumps(step.description)}, 'executing')"
                )
            except Exception:
                pass
            
            # Keep track of interaction states
            interaction_success = False
            retries = 0
            stall_counter = 0
            
            while not interaction_success and retries < 3:
                # Get current simplified DOM interactive elements
                elements = await page.evaluate('''() => {
                    const items = [];
                    document.querySelectorAll('input, button, select, a, [role="button"], span, div').forEach((el, index) => {
                        const style = window.getComputedStyle(el);
                        if (el.offsetWidth > 0 && el.offsetHeight > 0 && style.display !== 'none' && style.visibility !== 'hidden') {
                            const isClickable = el.tagName === 'BUTTON' || el.tagName === 'A' || el.onclick || el.getAttribute('role') === 'button';
                            const isInput = el.tagName === 'INPUT' || el.tagName === 'SELECT' || el.tagName === 'TEXTAREA';
                            const hasText = el.innerText && el.innerText.trim().length > 0 && el.innerText.trim().length < 100;
                            
                            if (isClickable || isInput || (hasText && items.length < 50)) {
                                items.push({
                                    id: el.id || '',
                                    tag: el.tagName.toLowerCase(),
                                    type: el.type || '',
                                    name: el.name || '',
                                    placeholder: el.placeholder || '',
                                    text: el.innerText ? el.innerText.trim() : '',
                                    selector: el.id ? `#${el.id}` : (el.name ? `[name="${el.name}"]` : '')
                                });
                            }
                        }
                    });
                    return items.slice(0, 80);
                }''')
                
                # Take current page screenshot
                ss_name = f"step_{step.sequence:02d}_ret_{retries}.png"
                ss_path = screenshots_dir / ss_name
                await page.screenshot(path=ss_path)
                
                # Construct System Prompt instructing the LLM on page interactions
                system_prompt = (
                    "You are an expert AI Test Automation Agent driving a browser to complete a step.\n"
                    f"Goal: '{step.description}'\n"
                    f"Action Required: {step.action.value}\n"
                    f"Value (if any): '{step.value or ''}'\n\n"
                    "Here are the interactive elements found on the current page:\n"
                )
                for index, el in enumerate(elements):
                    text_desc = f", text: '{el['text']}'" if el['text'] else ""
                    id_desc = f", id: '{el['id']}'" if el['id'] else ""
                    placeholder_desc = f", placeholder: '{el['placeholder']}'" if el['placeholder'] else ""
                    system_prompt += f"- Index {index}: tag: <{el['tag']}>{id_desc}{text_desc}{placeholder_desc}\n"
                    
                system_prompt += (
                    "\nChoose the single best Playwright action to perform. You can return JSON in the following format:\n"
                    "{\n"
                    "  \"action\": \"click\" | \"fill\" | \"select\" | \"navigate\" | \"done\",\n"
                    "  \"selector\": \"a valid CSS selector or locator path\",\n"
                    "  \"value\": \"string to type (required for fill)\",\n"
                    "  \"thought\": \"Brief plain English reasoning of what you are doing next\"\n"
                    "}\n"
                    "Return ONLY valid JSON and nothing else."
                )
                
                try:
                    await push_agent_log(run_id, {"type": "log", "message": f"Analyzing page state for Step {step.sequence}: '{step.description}'"})
                    
                    # Request LiteLLM completion with 429 retry
                    content = None
                    retry_delays = [10, 30, 60]
                    last_llm_err = None
                    for attempt, r_delay in enumerate(retry_delays, start=1):
                        try:
                            response = completion(
                                model=model,
                                messages=[
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": "Analyze the elements and return your next action JSON block."}
                                ],
                                temperature=temperature,
                                api_key=api_key
                            )
                            content = response.choices[0].message.content.strip()
                            break
                        except Exception as llm_err:
                            last_llm_err = llm_err
                            err_str = str(llm_err).lower()
                            if ("429" in err_str or "quota" in err_str or "rate" in err_str) and attempt < len(retry_delays):
                                await push_agent_log(run_id, {"type": "log", "message": f"[LLM] Rate limited. Retrying in {r_delay}s... (attempt {attempt})"})
                                await asyncio.sleep(r_delay)
                                continue
                            raise  # non-retryable
                    if content is None:
                        raise RuntimeError(f"LLM failed after retries: {last_llm_err}")
                    
                    if content.startswith("```"):
                        content = content.split("\n", 1)[-1]
                    if content.endswith("```"):
                        content = content.rsplit("```", 1)[0]
                        
                    action_json = json.loads(content.strip())
                    thought = action_json.get("thought", "Driving next interaction")
                    ai_action = action_json.get("action", "click")
                    ai_selector = action_json.get("selector", "")
                    safe_selector = _sanitize_selector(ai_selector)
                    ai_value = action_json.get("value", step.value)
                    
                    await push_agent_log(run_id, {
                        "type": "log",
                        "message": f"AI Thought: {thought}",
                        "action": ai_action,
                        "selector": ai_selector,
                        "screenshot": f"/static/output/{run_dir.relative_to(output_root).as_posix()}/screenshots/{ss_name}"
                    })
                    
                    # Perform action using Playwright
                    if ai_action == "done":
                        interaction_success = True
                        break
                        
                    elif ai_action == "navigate":
                        if step.action != ActionType.NAVIGATE:
                            raise ValueError("AI attempted to navigate to a new page, which is not permitted for this action step.")
                        await page.goto(ai_value, wait_until="domcontentloaded")
                        await wait_for_any_idle(page, config.is_oracle_fusion)
                        interaction_success = True
                        
                    elif ai_action == "click":
                        loc = page.locator(safe_selector).first
                        await loc.wait_for(state="attached", timeout=10000)
                        await loc.click(timeout=5000)
                        await wait_for_any_idle(page, config.is_oracle_fusion)
                        interaction_success = True
                        
                    elif ai_action == "fill":
                        loc = page.locator(safe_selector).first
                        await loc.wait_for(state="attached", timeout=10000)
                        await loc.fill(ai_value, timeout=5000)
                        interaction_success = True
                        
                    elif ai_action == "select":
                        await page.locator(safe_selector).first.select_option(ai_value)
                        interaction_success = True
                        
                except Exception as ex:
                    # Check for fatal API key or authentication issues
                    ex_str = str(ex).lower()
                    is_auth_error = any(k in ex_str for k in ["authentication", "api key not valid", "unauthorized", "api_key_invalid", "permission", "invalid api key"])
                    if is_auth_error:
                        retries = 3
                        await push_agent_log(run_id, {"type": "log", "message": f"Fatal authentication error: {str(ex)[:200]}"})
                        break
                        
                    # Check for fatal network, DNS, or browser closed errors to fail-fast immediately
                    is_fatal_error = any(k in ex_str for k in [
                        "target page, context or browser has been closed",
                        "execution context was destroyed",
                        "net::err_name_not_resolved",
                        "net::err_connection_refused",
                        "net::err_connection_timed_out",
                        "net::err_name_resolution_failed"
                    ])
                    if is_fatal_error:
                        retries = 3
                        await push_agent_log(run_id, {"type": "log", "message": f"Fatal browser or network error: {str(ex)[:200]}"})
                        break
                    
                    retries += 1
                    logger.warning(f"Agent retry {retries} for step {step.sequence} due to: {ex}")
                    await push_agent_log(run_id, {"type": "log", "message": f"Interaction failed. Retrying... ({retries}/3). Error: {str(ex)[:100]}"})
                    await asyncio.sleep(2)
                    
                    # 30-sec Stall safety check
                    stall_counter += 10
                    if stall_counter >= 30:
                        agent_status[run_id] = "stalled"
                        await push_agent_log(run_id, {
                            "type": "status", 
                            "status": "stalled",
                            "message": "AI-guided browser agent is stuck or stalling. Pausing for user guidance.",
                            "screenshot": f"/static/output/{run_dir.relative_to(output_root).as_posix()}/screenshots/{ss_name}"
                        })
                        
                        # Pause execution and wait for user resume signal
                        agent_resume_events[run_id].clear()
                        await agent_resume_events[run_id].wait()
                        stall_counter = 0
                        retries = 0
            
            if interaction_success:
                try:
                    import json
                    await page.evaluate(
                        f"window.updateQAPOverlay({step.sequence}, {json.dumps(step.action.value)}, {json.dumps(step.description)}, 'passed')"
                    )
                    await page.wait_for_timeout(500)
                except Exception:
                    pass
                # Record successful step result in database
                await db.create_result(
                    db_path,
                    run_id=run_id,
                    step_id=step.id,
                    sequence=step.sequence,
                    action=step.action.value,
                    status="passed",
                    description=step.description,
                    selector=step.selector,
                    value=step.value,
                    actual_value="Completed autonomously by AI",
                    screenshot_path=str(ss_path)
                )
                await push_agent_log(run_id, {"type": "step_success", "sequence": step.sequence})
                step_idx += 1
            else:
                overall_status = "failed"
                try:
                    import json
                    await page.evaluate(
                        f"window.updateQAPOverlay({step.sequence}, {json.dumps(step.action.value)}, {json.dumps(step.description)}, 'failed')"
                    )
                    await page.wait_for_timeout(1500)
                except Exception:
                    pass
                await db.create_result(
                    db_path,
                    run_id=run_id,
                    step_id=step.id,
                    sequence=step.sequence,
                    action=step.action.value,
                    status="failed",
                    description=step.description,
                    selector=step.selector,
                    value=step.value,
                    error_message=f"Autonomous AI agent failed to execute: {step.description}"
                )
                await push_agent_log(run_id, {"type": "step_fail", "sequence": step.sequence, "message": "Failed to resolve step actions"})
                break
                
        await browser.close()
        await update_run(db_path, run_id, status=overall_status)
        await push_agent_log(run_id, {"type": "done", "status": overall_status, "message": f"Autonomous AI driving complete with status: {overall_status}"})
        agent_status[run_id] = "done" if overall_status == "passed" else "failed"


def start_agent_background(run_id: str, test_id: str, api_key: str, output_root: Path,
                           override_config: Optional[Config] = None, override_password: Optional[str] = None) -> None:
    """Start the AI-Guided driver in a background thread with its own ProactorEventLoop.
    
    Using asyncio.create_task() inside uvicorn's loop fails on Windows because
    uvicorn uses a SelectorEventLoop which cannot spawn subprocesses (Playwright).
    Running in a dedicated thread with a ProactorEventLoop sidesteps this limitation
    while keeping SSE streaming functional via call_soon_threadsafe.
    """
    # Capture uvicorn's event loop so we can bridge queue writes back to it
    try:
        main_loop = asyncio.get_event_loop()
    except RuntimeError:
        main_loop = None

    # Pre-create the queue in the main loop so SSE can read it immediately
    if run_id not in agent_log_queues:
        agent_log_queues[run_id] = asyncio.Queue()

    def _thread_runner():
        if sys.platform == "win32":
            loop = asyncio.ProactorEventLoop()
        else:
            loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def _run():
            # Wrap push_agent_log so it bridges to the main loop
            async def _push(run_id, data, _main_loop=None):
                if main_loop and main_loop.is_running():
                    main_loop.call_soon_threadsafe(
                        agent_log_queues[run_id].put_nowait, data
                    )
                else:
                    try:
                        agent_log_queues[run_id].put_nowait(data)
                    except Exception:
                        pass

            # Monkey-patch push_agent_log for this coroutine's scope
            import engine.agent as _self
            _orig = _self.push_agent_log
            _self.push_agent_log = _push
            try:
                await run_autonomous_agent(
                    run_id=run_id,
                    test_id=test_id,
                    api_key=api_key,
                    output_root=output_root,
                    override_config=override_config,
                    override_password=override_password,
                )
            finally:
                _self.push_agent_log = _orig

        try:
            loop.run_until_complete(_run())
        except Exception as e:
            logger.error(f"Agent background thread error: {e}")
        finally:
            loop.close()

    t = threading.Thread(target=_thread_runner, daemon=True, name=f"agent-{run_id[:8]}")
    t.start()
