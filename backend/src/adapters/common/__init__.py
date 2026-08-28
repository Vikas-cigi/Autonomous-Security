"""
Common adapter utilities.
"""

from src.adapters.common.authentication import (
    EnvironmentTokenAuthenticator,
    NoopAuthenticator,
    merge_credential_env,
)
from src.adapters.common.execution_context import AdapterExecutionContext, EngagementWindow
from src.adapters.common.metadata_collector import MetadataCollector
from src.adapters.common.retry import retry_call
from src.adapters.common.scope_validator import ScopeValidator

__all__ = [
    "AdapterExecutionContext",
    "EngagementWindow",
    "EnvironmentTokenAuthenticator",
    "MetadataCollector",
    "NoopAuthenticator",
    "ScopeValidator",
    "merge_credential_env",
    "retry_call",
]
