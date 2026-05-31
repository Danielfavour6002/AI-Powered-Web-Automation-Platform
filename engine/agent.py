import asyncio
import os
from pathlib import Path
from typing import Optional

from core.database import get_test, get_steps_for_test, update_run
from core.config import load_config
from core.logging import configure_logging, get_logger

logger = get_logger()

async def run_autonomous_agent(run_id: str, test_id: str, api_key: str, output_root: Path, override_config=None, override_password=None):
    """Executes a test autonomously using the browser-use Agent."""
    # Lazy imports: loaded only when the agent is invoked so the module
    # can be imported at startup even if browser_use is unavailable.
    from browser_use import Agent
    from langchain_openai import ChatOpenAI

    # Patch ChatOpenAI to provide a 'provider' attribute which browser-use 0.12+ expects
    if not hasattr(ChatOpenAI, 'provider'):
        ChatOpenAI.provider = property(lambda self: 'openai')

    import sys
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    env_path = Path(".env")
    config = override_config if override_config else load_config(env_path)
    db_path = Path(config.db_path)

    try:
        # Load test and steps
        test = await get_test(db_path, test_id)
        steps = await get_steps_for_test(db_path, test_id)

        if not steps:
            await update_run(db_path, run_id, status="failed")
            logger.error(f"No steps found for test {test_id}")
            return

        # Determine target URL
        target_url = test.url
        if override_password and config.fusion_url:
            if "oracle" in target_url.lower() or "fa." in target_url.lower() or "oraclecloud" in target_url.lower():
                target_url = config.fusion_url

        task_parts = [f"Your goal is to complete the test scenario: {test.name}"]
        task_parts.append(f"Target URL: {target_url}")

        if override_password and config.fusion_user:
            task_parts.append(f"CRITICAL: If presented with a login screen, use Username: '{config.fusion_user}' and Password: '{override_password}'.")

        task_parts.append("Perform the following steps sequentially:")
        for step in steps:
            task_parts.append(f"{step.sequence}. {step.description}")

        task_string = "\n".join(task_parts)

        # Configure LLM
        os.environ["OPENAI_API_KEY"] = api_key
        llm = ChatOpenAI(model="gpt-4o")

        logger.info(f"Starting autonomous agent for run {run_id}")
        await update_run(db_path, run_id, status="running")

        agent = Agent(
            task=task_string,
            llm=llm
        )

        # Execute the agent
        history = await agent.run()

        if history.is_done():
            overall_status = "passed"
        else:
            overall_status = "failed"

        final_result = history.final_result() if hasattr(history, 'final_result') else "Agent finished execution."
        logger.info(f"Agent finished with status {overall_status}. Result: {final_result}")

        await update_run(db_path, run_id, status=overall_status)

    except Exception as e:
        logger.error(f"Autonomous agent failed: {e}")
        await update_run(db_path, run_id, status="failed")

def start_agent_background(run_id: str, test_id: str, api_key: str, output_root: Path, override_config=None, override_password=None):
    """Start the agent in a background thread with its own asyncio loop."""
    import threading
    def target():
        asyncio.run(run_autonomous_agent(run_id, test_id, api_key, output_root, override_config, override_password))
    t = threading.Thread(target=target)
    t.start()
