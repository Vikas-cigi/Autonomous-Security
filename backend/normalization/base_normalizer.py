"""
Abstract adapter contract for tool-specific normalizers.
"""

from __future__ import annotations

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID, uuid4

from models.common import MetadataBag
from models.enums import (
    EvidenceSource,
    EvidenceValidationStatus,
    HashAlgorithm,
    SourceTool,
)
from models.evidence import ContentHash, EvidenceLineage, EvidenceObject
from models.security_finding import SecurityFindingObject
from normalization.confidence import ConfidenceScorer
from normalization.context import NormalizationContext, NormalizationIssue
from normalization.exceptions import MalformedInputError, NormalizationItemError

logger = logging.getLogger(__name__)


class BaseNormalizer(ABC):
    """
    Adapter that converts one security tool's raw JSON into canonical findings.

    SOLID:
        - Single Responsibility: one tool dialect per concrete class.
        - Open/Closed: new tools subclass this without changing the service.
        - Liskov: all adapters honor ``normalize``.
        - Dependency Inversion: NormalizationService depends on this ABC.
    """

    adapter_version: str = "1.0.0"

    def __init__(self, confidence_scorer: Optional[ConfidenceScorer] = None) -> None:
        self._confidence = confidence_scorer or ConfidenceScorer()

    @property
    @abstractmethod
    def tool_key(self) -> str:
        """Registry key, e.g. ``nuclei``."""

    @property
    @abstractmethod
    def source_tool(self) -> SourceTool:
        """Canonical ``SourceTool`` enum value."""

    @abstractmethod
    def extract_items(self, raw_payload: Any) -> Sequence[Dict[str, Any]]:
        """
        Validate payload shape and return iterable finding dicts.

        Raises:
            MalformedInputError: When the payload schema is invalid.
        """

    @abstractmethod
    def normalize_item(
        self,
        item: Dict[str, Any],
        context: NormalizationContext,
    ) -> SecurityFindingObject:
        """Convert one raw item into a canonical finding (pre-confidence)."""

    def normalize(
        self,
        raw_payload: Any,
        context: NormalizationContext,
    ) -> tuple[List[SecurityFindingObject], List[NormalizationIssue]]:
        """
        Normalize a full raw payload into canonical findings.

        Malformed batch envelopes fail fast. Per-item failures are logged and
        collected as ``NormalizationIssue`` without aborting the batch.
        """

        try:
            items = list(self.extract_items(raw_payload))
        except MalformedInputError:
            raise
        except Exception as exc:  # noqa: BLE001 - boundary translation
            logger.exception(
                "Normalization schema failure tool=%s error=%s",
                self.tool_key,
                exc,
            )
            raise MalformedInputError(
                f"Malformed {self.tool_key} payload: {exc}",
                tool=self.tool_key,
                details=str(exc),
            ) from exc

        findings: List[SecurityFindingObject] = []
        issues: List[NormalizationIssue] = []

        for index, item in enumerate(items):
            if not isinstance(item, dict):
                issue = NormalizationIssue(
                    index=index,
                    error="item is not a JSON object",
                    raw_excerpt={"type": type(item).__name__},
                )
                issues.append(issue)
                logger.error(
                    "Normalization rejected non-object item tool=%s index=%s",
                    self.tool_key,
                    index,
                )
                continue

            try:
                finding = self.normalize_item(item, context)
                finding = self._apply_confidence(finding, item)
                # Re-validate canonical model (rejects malformed mappings).
                findings.append(
                    SecurityFindingObject.model_validate(finding.model_dump())
                )
            except Exception as exc:  # noqa: BLE001 - per-item isolation
                logger.error(
                    "Normalization item failed tool=%s index=%s error=%s",
                    self.tool_key,
                    index,
                    exc,
                    exc_info=True,
                )
                issues.append(
                    NormalizationIssue(
                        index=index,
                        error=str(exc),
                        raw_excerpt=self._safe_excerpt(item),
                    )
                )

        return findings, issues

    def build_evidence(
        self,
        *,
        context: NormalizationContext,
        summary: str,
        item: Dict[str, Any],
        confidence: float = 0.8,
    ) -> EvidenceObject:
        """Create canonical evidence referencing the raw artifact id."""

        digest = hashlib.sha256(
            json.dumps(item, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()

        return EvidenceObject(
            id=uuid4(),
            raw_artifact_id=context.raw_artifact_id,
            summary=summary[:4000],
            source=EvidenceSource.SCANNER,
            confidence=max(0.0, min(1.0, confidence)),
            hash=ContentHash(algorithm=HashAlgorithm.SHA256, value=digest),
            lineage=EvidenceLineage(
                transformation="normalize",
                transformer=f"forti-ai.normalization.{self.tool_key}",
                source_tool=self.source_tool,
                adapter_version=self.adapter_version,
            ),
            validation_status=EvidenceValidationStatus.PARTIALLY_VALIDATED,
        )

    def base_metadata(
        self,
        context: NormalizationContext,
        *,
        rule_id: Optional[str] = None,
        template_id: Optional[str] = None,
        extra_labels: Optional[Dict[str, str]] = None,
    ) -> MetadataBag:
        """Build controlled metadata (never a raw scanner dump)."""

        labels = dict(context.default_asset_labels)
        if context.scan_id:
            labels["scan_id"] = context.scan_id
        if rule_id:
            labels["rule_id"] = rule_id[:512]
        if template_id:
            labels["template_id"] = template_id[:512]
        if extra_labels:
            labels.update({k: str(v)[:512] for k, v in extra_labels.items()})
        return MetadataBag(
            labels=labels,
            tags={"source_tool": self.tool_key, "adapter": self.adapter_version},
        )

    def require_fields(
        self,
        item: Dict[str, Any],
        fields: Sequence[str],
    ) -> None:
        """Raise ``NormalizationItemError`` when required fields are missing."""

        missing = [name for name in fields if name not in item or item[name] in (None, "")]
        if missing:
            raise NormalizationItemError(
                f"Missing required fields: {', '.join(missing)}",
                tool=self.tool_key,
                details={"missing": missing},
            )

    def _apply_confidence(
        self,
        finding: SecurityFindingObject,
        item: Dict[str, Any],
    ) -> SecurityFindingObject:
        """Stamp confidence_score using the shared scorer."""

        has_cve = bool(finding.cve_ids) or bool(item.get("cve") or item.get("VulnerabilityID"))
        has_template = bool(
            finding.metadata.labels.get("rule_id")
            or finding.metadata.labels.get("template_id")
        )
        score = self._confidence.score(
            finding,
            tool=self.tool_key,
            has_cve=has_cve,
            has_template_id=has_template,
        )
        return finding.model_copy(update={"confidence_score": score})

    @staticmethod
    def _safe_excerpt(item: Dict[str, Any], limit: int = 8) -> Dict[str, Any]:
        """Return a small key excerpt for diagnostics (not full raw payload)."""

        excerpt: Dict[str, Any] = {}
        for index, (key, value) in enumerate(item.items()):
            if index >= limit:
                break
            if isinstance(value, (str, int, float, bool)) or value is None:
                excerpt[str(key)] = value if not isinstance(value, str) else value[:200]
            else:
                excerpt[str(key)] = type(value).__name__
        return excerpt
