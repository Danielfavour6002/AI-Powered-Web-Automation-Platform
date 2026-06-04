"""Configuration management for QA Platform."""

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.exceptions import ConfigError

@dataclass
class Config:
    """Application configuration settings."""
    db_path: Path
    output_root: Path
    host: str
    port: int
    log_level: str = "INFO"
    theme: str = "system"
    browser: str = "chromium"
    recording_timeout: int = 300
    concurrent_runs: int = 2
    screenshot_quality: int = 80
    screenshot_format: str = "PNG"
    video_width: int = 1280
    video_height: int = 720
    video_fps: int = 25
    report_format: str = "excel"
    seeded_reports_url: str = ""
    # New field for the seeded reports page URL
    enable_screenshots: bool = True
    enable_videos: bool = True
    enable_traces: bool = True
    
    # Kept for backward compatibility
    fusion_url: str = ""
    fusion_user: str = ""
    fusion_pod: str = ""
    consultant: str = ""

    @property
    def is_oracle_fusion(self) -> bool:
        """Returns True if the target URL is an Oracle Fusion instance."""
        url = self.fusion_url.lower()
        return "oraclecloud.com" in url or "oraclepdemos.com" in url


def load_config(env_path: Path) -> Config:
    """
    Load configuration from the ``app_config`` SQLite table, falling back to a ``.env`` file.
    All configuration values are read into local variables first, then a single ``Config`` instance is created.
    """
    # 1️⃣ Load .env if present – used for DB path override and any other env vars
    env_vals: dict[str, str] = {}
    if env_path.exists():
        from dotenv import dotenv_values
        env_vals = dotenv_values(env_path)

    # 2️⃣ Load values from the SQLite DB (if it exists)
    db_path_str = env_vals.get("DB_PATH", "data/qap.db")
    configs: dict[str, str] = {}
    try:
        conn = sqlite3.connect(db_path_str)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='app_config'")
        if cursor.fetchone():
            cursor.execute("SELECT key, value FROM app_config")
            for key, value in cursor.fetchall():
                configs[key] = value
        conn.close()
    except Exception:
        pass

    # 3️⃣ Overlay .env values that were not present in the DB
    for k, v in env_vals.items():
        if k not in configs and v is not None:
            configs[k] = v

    # 4️⃣ Helper to fetch a string with a default
    def get(key: str, default: str = "") -> str:
        return configs.get(key, default)

    # 5️⃣ Gather all configuration pieces
    db_path = Path(get("DB_PATH", "data/qap.db"))
    output_root = Path(get("OUTPUT_ROOT", "output"))
    host = get("HOST", "127.0.0.1")
    port = int(get("PORT", "8001"))
    log_level = get("LOG_LEVEL", "INFO")
    theme = get("THEME", "system")
    browser = get("BROWSER", "chromium")
    recording_timeout = int(get("RECORDING_TIMEOUT", "300"))
    concurrent_runs = int(get("CONCURRENT_RUNS", "2"))
    screenshot_quality = int(get("SCREENSHOT_QUALITY", "80"))
    screenshot_format = get("SCREENSHOT_FORMAT", "PNG")
    video_width = int(get("VIDEO_WIDTH", "1280"))
    video_height = int(get("VIDEO_HEIGHT", "720"))
    video_fps = int(get("VIDEO_FPS", "25"))
    report_format = get("REPORT_FORMAT", "excel")
    enable_screenshots = get("ENABLE_SCREENSHOTS", "true").lower() == "true"
    enable_videos = get("ENABLE_VIDEOS", "true").lower() == "true"
    enable_traces = get("ENABLE_TRACES", "true").lower() == "true"
    # Backward‑compatibility fields (may be empty)
    fusion_url = get("FUSION_URL", "")
    fusion_user = get("FUSION_USER", "")
    fusion_pod = get("FUSION_POD", "")
    consultant = get("CONSULTANT", "")
    # New field – URL of the seeded reports screen
    seeded_reports_url = get("SEEDED_REPORTS_URL", "")

    config = Config(
        db_path=db_path,
        output_root=output_root,
        host=host,
        port=port,
        log_level=log_level,
        theme=theme,
        browser=browser,
        recording_timeout=recording_timeout,
        concurrent_runs=concurrent_runs,
        screenshot_quality=screenshot_quality,
        screenshot_format=screenshot_format,
        video_width=video_width,
        video_height=video_height,
        video_fps=video_fps,
        report_format=report_format,
        enable_screenshots=enable_screenshots,
        enable_videos=enable_videos,
        enable_traces=enable_traces,
        fusion_url=fusion_url,
        fusion_user=fusion_user,
        fusion_pod=fusion_pod,
        consultant=consultant,
        seeded_reports_url=seeded_reports_url,
    )
    return config


def resolve_password(config: Config) -> str:
    """
    Resolve the password from either environment variables or .env file.
    Provides backward compatibility for older scripts.
    """
    password = os.environ.get("FUSION_PASSWORD", "")
    if not password:
        try:
            from dotenv import dotenv_values
            env_vals = dotenv_values(".env")
            password = env_vals.get("FUSION_PASSWORD", "")
        except Exception:
            pass
    return password

