"""Authentication helpers for tool adapters."""

from __future__ import annotations

import logging
import os
from typing import Mapping, Optional, Protocol

from src.adapters.base.adapter_config import AdapterConfig
from src.adapters.base.adapter_exception import AdapterAuthenticationError
from src.adapters.common.execution_context import AdapterExecutionContext

logger = logging.getLogger(__name__)


class Authenticator(Protocol):
    """Protocol for pluggable authentication strategies."""

    def authenticate(
        self,
        config: AdapterConfig,
        context: AdapterExecutionContext,
    ) -> None:
        """Validate credentials; raise on failure."""


class EnvironmentTokenAuthenticator:
    """
    Validates that required credential material is present.

    Supports explicit ``api_token`` on config or an environment variable
    named ``{TOOL}_API_TOKEN`` / ``{TOOL}_ACCESS_KEY``.
    """

    def __init__(self, *, required: bool = False, env_keys: Optional[list[str]] = None) -> None:
        self._required = required
        self._env_keys = env_keys or []

    def authenticate(
        self,
        config: AdapterConfig,
        context: AdapterExecutionContext,
    ) -> None:
        if config.api_token:
            logger.debug(
                "Adapter auth ok via config token tool=%s tenant=%s",
                config.tool_name,
                context.tenant_id,
            )
            return

        for key in self._env_keys:
            if os.environ.get(key):
                logger.debug(
                    "Adapter auth ok via env %s tool=%s",
                    key,
                    config.tool_name,
                )
                return

        if not self._required:
            logger.debug(
                "Adapter auth skipped (optional) tool=%s",
                config.tool_name,
            )
            return

        raise AdapterAuthenticationError(
            f"Missing credentials for tool '{config.tool_name}'",
            tool_name=config.tool_name,
            details={"env_keys": self._env_keys},
        )


class NoopAuthenticator:
    """Authenticator for local CLI tools that need no cloud credentials."""

    def authenticate(
        self,
        config: AdapterConfig,
        context: AdapterExecutionContext,
    ) -> None:
        logger.debug(
            "NoopAuthenticator accepted tool=%s actor=%s",
            config.tool_name,
            context.user.actor_id,
        )


def merge_credential_env(
    base: Mapping[str, str],
    config: AdapterConfig,
    *,
    token_env_name: str,
) -> dict[str, str]:
    """Merge process env with optional token injection for subprocesses."""

    merged = dict(os.environ)
    merged.update(base)
    merged.update(config.environment)
    if config.api_token:
        merged[token_env_name] = config.api_token
    return merged
