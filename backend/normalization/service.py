"""
Normalization Service — orchestrates tool adapters into canonical findings.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Mapping, Optional

from models.security_finding import SecurityFindingObject
from normalization.adapters.checkov_normalizer import CheckovNormalizer
from normalization.adapters.grype_normalizer import GrypeNormalizer
from normalization.adapters.nuclei_normalizer import NucleiNormalizer
from normalization.adapters.prowler_normalizer import ProwlerNormalizer
from normalization.adapters.trivy_normalizer import TrivyNormalizer
from normalization.base_normalizer import BaseNormalizer
from normalization.confidence import ConfidenceScorer
from normalization.context import NormalizationContext, NormalizationResult
from normalization.deduplicator import FindingDeduplicator
from normalization.exceptions import MalformedInputError, UnknownToolError

logger = logging.getLogger(__name__)


class NormalizationService:
    """
    Converts raw security-tool JSON into ``SecurityFindingObject`` instances.

    Flow::

        raw tool output → tool adapter (BaseNormalizer) → validate →
        confidence → deduplicate → canonical findings

    Returns only canonical models (plus diagnostic issues on the result
    envelope). Does not call AI services.
    """

    def __init__(
        self,
        normalizers: Optional[Mapping[str, BaseNormalizer]] = None,
        *,
        deduplicator: Optional[FindingDeduplicator] = None,
        confidence_scorer: Optional[ConfidenceScorer] = None,
    ) -> None:
        scorer = confidence_scorer or ConfidenceScorer()
        self._normalizers: Dict[str, BaseNormalizer] = {
            key.lower(): value
            for key, value in (
                normalizers or self.default_normalizers(scorer)
            ).items()
        }
        self._deduplicator = deduplicator or FindingDeduplicator()
        logger.debug(
            "NormalizationService initialized tools=%s",
            sorted(self._normalizers.keys()),
        )

    @staticmethod
    def default_normalizers(
        confidence_scorer: Optional[ConfidenceScorer] = None,
    ) -> Dict[str, BaseNormalizer]:
        """Return the built-in adapter registry."""

        scorer = confidence_scorer or ConfidenceScorer()
        adapters: List[BaseNormalizer] = [
            NucleiNormalizer(confidence_scorer=scorer),
            ProwlerNormalizer(confidence_scorer=scorer),
            CheckovNormalizer(confidence_scorer=scorer),
            TrivyNormalizer(confidence_scorer=scorer),
            GrypeNormalizer(confidence_scorer=scorer),
        ]
        return {adapter.tool_key: adapter for adapter in adapters}

    @property
    def registered_tools(self) -> tuple[str, ...]:
        """Sorted tool keys available for normalization."""

        return tuple(sorted(self._normalizers.keys()))

    def register(self, normalizer: BaseNormalizer) -> None:
        """Register or replace a tool adapter (Open/Closed extension point)."""

        self._normalizers[normalizer.tool_key.lower()] = normalizer
        logger.info(
            "Registered normalizer tool=%s class=%s",
            normalizer.tool_key,
            type(normalizer).__name__,
        )

    def get_normalizer(self, tool: str) -> BaseNormalizer:
        """Resolve a tool adapter by name."""

        key = (tool or "").strip().lower()
        normalizer = self._normalizers.get(key)
        if normalizer is None:
            raise UnknownToolError(
                f"No normalizer registered for tool '{tool}'",
                tool=key or None,
                details={"registered": list(self.registered_tools)},
            )
        return normalizer

    def normalize(
        self,
        tool: str,
        raw_payload: Any,
        context: NormalizationContext,
    ) -> NormalizationResult:
        """
        Normalize raw tool output into canonical findings.

        Args:
            tool: Adapter key (``nuclei``, ``prowler``, ``checkov``, ``trivy``,
                ``grype``).
            raw_payload: Parsed JSON (dict/list) or Nuclei JSON/JSONL string.
            context: Tenant/asset binding for emitted findings.

        Returns:
            NormalizationResult with canonical ``findings`` only (plus issues).

        Raises:
            UnknownToolError: Unknown tool key.
            MalformedInputError: Payload envelope failed schema validation.
        """

        normalizer = self.get_normalizer(tool)
        logger.info(
            "Normalization start tool=%s tenant_id=%s asset_id=%s",
            normalizer.tool_key,
            context.tenant_id,
            context.asset_id,
        )

        try:
            findings, issues = normalizer.normalize(raw_payload, context)
        except MalformedInputError:
            logger.error(
                "Normalization rejected malformed payload tool=%s",
                normalizer.tool_key,
            )
            raise

        unique, removed = self._deduplicator.deduplicate(findings)
        result = NormalizationResult(
            tool=normalizer.tool_key,
            findings=unique,
            issues=issues,
            duplicates_removed=removed,
        )
        logger.info(
            "Normalization complete tool=%s findings=%s issues=%s duplicates_removed=%s",
            result.tool,
            len(result.findings),
            len(result.issues),
            result.duplicates_removed,
        )
        return result

    def normalize_many(
        self,
        batches: Iterable[tuple[str, Any, NormalizationContext]],
    ) -> List[SecurityFindingObject]:
        """
        Normalize multiple tool batches and return a flat canonical list.

        Per-batch envelope errors propagate. Item-level issues are logged via
        each ``normalize`` call and omitted from the returned list.
        """

        combined: List[SecurityFindingObject] = []
        for tool, payload, context in batches:
            result = self.normalize(tool, payload, context)
            combined.extend(result.findings)
        unique, _ = self._deduplicator.deduplicate(combined)
        return unique
