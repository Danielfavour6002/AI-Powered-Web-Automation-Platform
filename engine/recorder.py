"""Playwright codegen wrapper for recording."""

import asyncio
from pathlib import Path
from typing import Optional
from core.exceptions import RecordingError
from core.logging import get_logger

logger = get_logger()

class Recorder:
    """Manages the playwright codegen subprocess."""
    
    def __init__(self) -> None:
        import subprocess
        self.process: Optional[subprocess.Popen] = None
        self.output_file: Optional[Path] = None
        self.is_recording: bool = False
        self._lock = asyncio.Lock()

    async def start_recording(self, url: str, output_file: Path, env_id: str = None) -> None:
        """Start the codegen process."""
        async with self._lock:
            if self.is_recording:
                # Attempt to stop any existing recording before starting a new one
                try:
                    await self.stop_recording()
                except Exception as e:
                    logger.warning(f"Failed to stop previous recorder cleanly: {e}")
            self.output_file = output_file
            
            logger.info(f"Recording started for {url}")
            
            try:
                import sys
                import subprocess
                from core.config import load_config
                from core.display import get_screen_resolution
                import signal
                
                config = load_config(Path(".env"))
                width, height = get_screen_resolution()
                
                user_data_dir = Path("engine/.recorder_user_data")
                user_data_dir.mkdir(parents=True, exist_ok=True)
                
                cmd = [
                    sys.executable, "-m", "playwright", "codegen",
                    "--target", "python",
                    url,
                    "--output", str(output_file),
                    "--viewport-size", f"{width},{height}",
                    f"--user-data-dir={user_data_dir}"
                ]
                
                if config.is_oracle_fusion:
                    state_file = Path("engine/.auth_state.json")
                    logger.info(f"Pre-authenticating for recording on {url}...")
                    auth_cmd = [sys.executable, "-m", "engine.generate_auth", str(state_file), url]
                    if env_id:
                        auth_cmd.append(env_id)
                    subprocess.run(auth_cmd, check=False)
                    if state_file.exists():
                        cmd.insert(4, f"--load-storage={state_file}")
                
                # Match the test runner's dimensions and the user's laptop screen perfectly
                import os
                ext_path = Path(__file__).resolve().parent / "recorder_extension"
                ext_path_str = str(ext_path)
                existing_args = os.environ.get("PLAYWRIGHT_CHROMIUM_LAUNCH_ARGS", "")
                ext_args = f"--disable-extensions-except={ext_path_str} --load-extension={ext_path_str}"
                os.environ["PLAYWRIGHT_CHROMIUM_LAUNCH_ARGS"] = f"{existing_args} {ext_args}".strip()
                
                self.process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
                )
                # Start background monitor for error patterns
                async def _monitor():
                    try:
                        # Combine stdout and stderr lines
                        while True:
                            line = await asyncio.get_event_loop().run_in_executor(None, self.process.stdout.readline)
                            if not line:
                                break
                            decoded = line.decode(errors='ignore')
                            # Simple pattern detection for Playwright locator errors
                            if "Locator.wait_for" in decoded or "Locator.fill" in decoded:
                                logger.error(f"Recorder error detected, terminating: {decoded.strip()}")
                                try:
                                    if sys.platform == "win32":
                                        self.process.send_signal(signal.CTRL_BREAK_EVENT)
                                    else:
                                        self.process.terminate()
                                except Exception:
                                    pass
                                break
                    except Exception as e:
                        logger.debug(f"Recorder monitor exception: {e}")
                # Fire and forget monitor task
                asyncio.create_task(_monitor())
            except Exception as e:
                import traceback
                logger.error(f"Failed to start codegen: {traceback.format_exc()}")
                raise RecordingError(f"Failed to start playwright codegen: {repr(e)}")
                
            self.is_recording = True

    async def stop_recording(self) -> Path:
        """Stop the codegen process and return output file path."""
        async with self._lock:
            if not self.is_recording or not self.process:
                raise RecordingError("No recording in progress")
                
            import sys
            import signal
            
            try:
                if sys.platform == "win32":
                    self.process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    self.process.terminate()
            except Exception:
                pass
                
            try:
                loop = asyncio.get_running_loop()
                await asyncio.wait_for(loop.run_in_executor(None, self.process.wait), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Recorder process didn't exit in time, killing it")
                try:
                    self.process.kill()
                except Exception:
                    pass
                    
            self.is_recording = False
            self.process = None
            
            if not self.output_file or not self.output_file.exists():
                raise RecordingError("Output file does not exist after stop")
                
            return self.output_file

    async def is_alive(self) -> bool:
        """Check if process is currently running."""
        async with self._lock:
            if not self.is_recording or self.process is None:
                return False
            return self.process.poll() is None

_recorder: Optional[Recorder] = None

def get_recorder() -> Recorder:
    """Get the singleton recorder instance."""
    global _recorder
    if _recorder is None:
        _recorder = Recorder()
    return _recorder
