"""Scope validation for adapter executions."""

from __future__ import annotations

import logging
from typing import Iterable, Set

from src.adapters.base.adapter_exception import AdapterScopeViolationError
from src.adapters.common.execution_context import AdapterExecutionContext

logger = logging.getLogger(__name__)


class ScopeValidator:
    """
    Validates tenant, asset, targets, allowed actions, and engagement window.

    Fail closed: any violation raises ``AdapterScopeViolationError``.
    """

    def validate(self, context: AdapterExecutionContext, *, tool_name: str) -> None:
        """Run the full scope checklist."""

        self._validate_identities(context, tool_name)
        self._validate_engagement_window(context, tool_name)
        self._validate_targets(context, tool_name)
        logger.info(
            "Scope validation passed tool=%s tenant=%s asset=%s targets=%s",
            tool_name,
            context.tenant_id,
            context.asset_id,
            len(context.targets),
        )

    def _validate_identities(
        self,
        context: AdapterExecutionContext,
        tool_name: str,
    ) -> None:
        if context.tenant_id is None or context.asset_id is None:
            raise AdapterScopeViolationError(
                "tenant_id and asset_id are required",
                tool_name=tool_name,
            )
        if context.user is None:
            raise AdapterScopeViolationError(
                "acting user is required",
                tool_name=tool_name,
            )

    def _validate_engagement_window(
        self,
        context: AdapterExecutionContext,
        tool_name: str,
    ) -> None:
        window = context.engagement_window
        if window is None:
            return
        if not window.contains():
            raise AdapterScopeViolationError(
                "Current time is outside the engagement window",
                tool_name=tool_name,
                details={
                    "starts_at": window.starts_at.isoformat(),
                    "ends_at": window.ends_at.isoformat(),
                },
            )

    def _validate_targets(
        self,
        context: AdapterExecutionContext,
        tool_name: str,
    ) -> None:
        if not context.targets:
            raise AdapterScopeViolationError(
                "At least one scan target is required",
                tool_name=tool_name,
            )

        if context.allowed_targets:
            allowed: Set[str] = {item.strip() for item in context.allowed_targets}
            requested: Set[str] = {item.strip() for item in context.targets}
            unauthorized = sorted(requested - allowed)
            if unauthorized:
                raise AdapterScopeViolationError(
                    "Requested targets are not in the allowed target set",
                    tool_name=tool_name,
                    details={"unauthorized_targets": unauthorized},
                )

        for target in context.targets:
            if not target or not target.strip():
                raise AdapterScopeViolationError(
                    "Empty target is not allowed",
                    tool_name=tool_name,
                )


def ensure_subset(requested: Iterable[str], allowed: Iterable[str]) -> None:
    """Utility assert that requested ⊆ allowed."""

    missing = sorted(set(requested) - set(allowed))
    if missing:
        raise AdapterScopeViolationError(
            "Requested values exceed allowed set",
            details={"unauthorized": missing},
        )
