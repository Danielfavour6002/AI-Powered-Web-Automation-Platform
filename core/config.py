"""Configuration management for QA Platform."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import keyring
from dotenv import load_dotenv

from core.exceptions import ConfigError

@dataclass(frozen=True)
class Config:
    """Application configuration settings."""
    fusion_url: str
    fusion_user: str
    fusion_pod: str
    consultant: str
    db_path: Path
    output_root: Path
    host: str
    port: int

    @property
    def is_oracle_fusion(self) -> bool:
        """Returns True if the target URL is an Oracle Fusion instance."""
        url = self.fusion_url.lower()
        return "oraclecloud.com" in url or "oraclepdemos.com" in url


def load_config(env_path: Path) -> Config:
    """
    Load configuration from environment variables and dotenv file.
    
    Args:
        env_path: Path to the .env file.
        
    Returns:
        Config: The application configuration object.
    """
    load_dotenv(env_path)
    
    fusion_url = os.getenv("FUSION_URL")
    if not fusion_url:
        raise ConfigError("FUSION_URL environment variable is required.")
        
    fusion_user = os.getenv("FUSION_USER")
    if not fusion_user:
        raise ConfigError("FUSION_USER environment variable is required.")
        
    fusion_pod = os.getenv("FUSION_POD", "LOCAL")
    
    consultant = os.getenv("CONSULTANT")
    if not consultant:
        consultant = os.getenv("USERNAME", "Unknown")
        
    db_path_str = os.getenv("DB_PATH", "data/qap.db")
    db_path = Path(db_path_str)
    
    output_root_str = os.getenv("OUTPUT_ROOT", "output")
    output_root = Path(output_root_str)
    
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8001"))
    
    return Config(
        fusion_url=fusion_url,
        fusion_user=fusion_user,
        fusion_pod=fusion_pod,
        consultant=consultant,
        db_path=db_path,
        output_root=output_root,
        host=host,
        port=port
    )

def resolve_password(config: Config, cli_password: Optional[str] = None, prompt: bool = False) -> str:
    """
    Resolve the password for Oracle Fusion based on priority.
    Priority: cli_password -> prompt (getpass) -> keyring service -> FUSION_PASS env var.
    
    Args:
        config: The application configuration.
        cli_password: Password provided via CLI argument.
        prompt: Whether to prompt the user interactively.
        
    Returns:
        str: The resolved password.
        
    Raises:
        RuntimeError: If password cannot be resolved.
    """
    import getpass
    
    if cli_password:
        return cli_password
        
    if prompt:
        return getpass.getpass("Enter Fusion Password: ")
        
    # Check keyring
    service_name = f"qap/{config.fusion_pod}"
    keyring_pass = keyring.get_password(service_name, config.fusion_user)
    if keyring_pass:
        return keyring_pass
        
    # Check env var
    env_pass = os.getenv("FUSION_PASS")
    if env_pass:
        return env_pass
        
    # Return empty string instead of crashing if not found
    return ""
