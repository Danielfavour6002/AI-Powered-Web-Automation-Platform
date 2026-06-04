"""Run context and parameter substitution engine for test execution."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from playwright.async_api import Page
    from core.models import ClientProfile

from core.config import Config

class TokenResolver:
    """Resolves dynamic {{client.*}} and {{run.*}} tokens within string expressions."""

    def __init__(self, client: Optional[ClientProfile] = None, run_params: Optional[Dict[str, Any]] = None) -> None:
        self.client = client
        self.run_params = run_params or {}

    def resolve(self, text: Optional[str]) -> Optional[str]:
        """Substitute all {{token}} matches in the input string."""
        if not text:
            return text

        def replacer(match: re.Match) -> str:
            token = match.group(1).strip()
            
            # Resolve client.* tokens
            if token.startswith("client."):
                field_name = token[7:]
                if self.client and hasattr(self.client, field_name):
                    val = getattr(self.client, field_name)
                    if val is not None:
                        return str(val)
                return ""
            
            # Resolve run.* tokens
            if token.startswith("run."):
                field_name = token[4:]
                return str(self.run_params.get(field_name, ""))

            return match.group(0)

        return re.sub(r"\{\{([^}]+)\}\}", replacer, text)


@dataclass
class RunContext:
    """Asynchronous context passed throughout a test run execution."""
    page: Page
    config: Config
    password: str
    run_dir: Path
    run_id: str
    test_id: str
    is_oracle: bool
    reporter: Any
    client: Optional[ClientProfile] = None
    run_params: Dict[str, Any] = field(default_factory=dict)
    screenshots_dir: Path = field(init=False)
    resolver: TokenResolver = field(init=False)

    def __post_init__(self) -> None:
        self.screenshots_dir = self.run_dir / "screenshots"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.resolver = TokenResolver(self.client, self.run_params)

    def resolve(self, val: Optional[str]) -> Optional[str]:
        """Convenience method to resolve tokens using the context's resolver."""
        return self.resolver.resolve(val)

