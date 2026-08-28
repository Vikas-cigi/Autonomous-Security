"""
Xolaris Security Tool Adapter Framework.

Adapters produce ``RawResult`` only. Normalization to ``SecurityFindingObject``
is performed exclusively by the Normalization Service.
"""

from src.adapters import bootstrap as _bootstrap  # noqa: F401  — register adapters
from src.adapters.base.adapter_config import AdapterConfig
from src.adapters.base.adapter_exception import (
    AdapterAuthenticationError,
    AdapterError,
    AdapterExecutionError,
    AdapterParserError,
    AdapterPolicyViolationError,
    AdapterScopeViolationError,
    AdapterTimeoutError,
)
from src.adapters.base.base_adapter import BaseToolAdapter
from src.adapters.base.factory import AdapterFactory
from src.adapters.base.raw_result import RawResult, RawResultStatus
from src.adapters.base.registry import AdapterRegistry

__all__ = [
    "AdapterAuthenticationError",
    "AdapterConfig",
    "AdapterError",
    "AdapterExecutionError",
    "AdapterFactory",
    "AdapterParserError",
    "AdapterPolicyViolationError",
    "AdapterRegistry",
    "AdapterScopeViolationError",
    "AdapterTimeoutError",
    "BaseToolAdapter",
    "RawResult",
    "RawResultStatus",
]

__version__ = "1.0.0"
