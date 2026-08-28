"""Adapter framework base package."""

from src.adapters.base.adapter_config import AdapterConfig
from src.adapters.base.adapter_exception import (
    AdapterAuthenticationError,
    AdapterConfigurationError,
    AdapterError,
    AdapterExecutionError,
    AdapterNotFoundError,
    AdapterParserError,
    AdapterPolicyViolationError,
    AdapterScopeViolationError,
    AdapterTimeoutError,
)
from src.adapters.base.base_adapter import BaseToolAdapter, CommandResult
from src.adapters.base.factory import AdapterFactory
from src.adapters.base.raw_result import RawResult, RawResultStatus
from src.adapters.base.registry import AdapterRegistry

__all__ = [
    "AdapterAuthenticationError",
    "AdapterConfig",
    "AdapterConfigurationError",
    "AdapterError",
    "AdapterExecutionError",
    "AdapterFactory",
    "AdapterNotFoundError",
    "AdapterParserError",
    "AdapterPolicyViolationError",
    "AdapterRegistry",
    "AdapterScopeViolationError",
    "AdapterTimeoutError",
    "BaseToolAdapter",
    "CommandResult",
    "RawResult",
    "RawResultStatus",
]
