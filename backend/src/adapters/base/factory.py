"""
Adapter factory — resolve and construct adapters via the registry.
"""

from __future__ import annotations

import logging
from typing import Optional

from policy_engine import PolicyEngine

from src.adapters.base.adapter_config import AdapterConfig
from src.adapters.base.adapter_exception import AdapterConfigurationError
from src.adapters.base.base_adapter import BaseToolAdapter
from src.adapters.base.registry import AdapterRegistry
from src.adapters.common.authentication import Authenticator
from src.adapters.common.metadata_collector import MetadataCollector
from src.adapters.common.scope_validator import ScopeValidator

logger = logging.getLogger(__name__)


class AdapterFactory:
    """
    Factory that instantiates registered adapters with dependency injection.
    """

    def __init__(
        self,
        *,
        policy_engine: Optional[PolicyEngine] = None,
        scope_validator: Optional[ScopeValidator] = None,
        metadata_collector: Optional[MetadataCollector] = None,
        registry: Optional[type[AdapterRegistry]] = None,
    ) -> None:
        self._policy_engine = policy_engine or PolicyEngine()
        self._scope_validator = scope_validator or ScopeValidator()
        self._metadata_collector = metadata_collector or MetadataCollector()
        self._registry = registry or AdapterRegistry

    def create(
        self,
        tool_name: str,
        config: AdapterConfig,
        *,
        authenticator: Optional[Authenticator] = None,
    ) -> BaseToolAdapter:
        """
        Construct an adapter for ``tool_name``.

        Args:
            tool_name: Registered tool key.
            config: Adapter configuration (``tool_name`` must match).
            authenticator: Optional auth strategy override.
        """

        if config.tool_name.strip().lower() != tool_name.strip().lower():
            raise AdapterConfigurationError(
                "config.tool_name must match requested tool_name",
                tool_name=tool_name,
                details={
                    "config_tool_name": config.tool_name,
                    "requested": tool_name,
                },
            )

        adapter_cls = self._registry.get(tool_name)
        adapter = adapter_cls(
            config,
            policy_engine=self._policy_engine,
            scope_validator=self._scope_validator,
            authenticator=authenticator,
            metadata_collector=self._metadata_collector,
        )
        logger.info(
            "Factory created adapter tool=%s class=%s",
            tool_name,
            adapter_cls.__name__,
        )
        return adapter

    def available_tools(self) -> tuple[str, ...]:
        """List tools currently registered."""

        return self._registry.list()
