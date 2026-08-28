"""Execution metadata collection for adapters."""

from __future__ import annotations

import hashlib
import logging
import os
import platform
import socket
from datetime import datetime
from typing import Any, Dict, Optional, Sequence

from models.common import utc_now
from src.adapters.common.execution_context import AdapterExecutionContext

logger = logging.getLogger(__name__)


class MetadataCollector:
    """
    Captures host, OS, timing, arguments hash, actor, and correlation data.

    Never embeds raw scanner findings — only execution telemetry.
    """

    def collect(
        self,
        *,
        context: AdapterExecutionContext,
        tool_name: str,
        tool_version: str,
        arguments: Sequence[str],
        started_at: datetime,
        completed_at: Optional[datetime] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build a metadata dictionary suitable for ``RawResult.metadata``."""

        finished = completed_at or utc_now()
        hostname = socket.gethostname()
        try:
            host_ip = socket.gethostbyname(hostname)
        except OSError:
            host_ip = "unknown"

        args_list = list(arguments)
        payload: Dict[str, Any] = {
            "correlation_id": str(context.correlation_id),
            "execution_id": str(context.execution_id),
            "tenant_id": str(context.tenant_id),
            "asset_id": str(context.asset_id),
            "user_id": str(context.user.actor_id),
            "user_display_name": context.user.display_name,
            "roles": list(context.roles),
            "tool_name": tool_name,
            "tool_version": tool_version,
            "arguments": args_list,
            "arguments_hash": self.hash_arguments(args_list),
            "host": hostname,
            "ip": host_ip,
            "os": platform.platform(),
            "python_version": platform.python_version(),
            "pid": os.getpid(),
            "started_at": started_at.isoformat(),
            "completed_at": finished.isoformat(),
            "timestamp": utc_now().isoformat(),
            "environment": context.environment,
            "action_class": context.action_class.value,
            "scope": context.scope.value,
        }
        if extra:
            payload["extra"] = extra
        logger.debug(
            "Collected metadata tool=%s correlation_id=%s",
            tool_name,
            context.correlation_id,
        )
        return payload

    @staticmethod
    def hash_arguments(arguments: Sequence[str]) -> str:
        """SHA-256 over the canonical argument vector."""

        material = "\0".join(arguments).encode("utf-8")
        return hashlib.sha256(material).hexdigest()

    @staticmethod
    def hash_bytes(data: bytes) -> str:
        """SHA-256 hex digest for arbitrary byte payloads."""

        return hashlib.sha256(data).hexdigest()
