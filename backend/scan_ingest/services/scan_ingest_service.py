"""Facade coordinating ScanOrchestrator + optional FindingPipelineService."""

from __future__ import annotations

import logging
from typing import Any, Optional

from scan_ingest.domain.models import ScanRequest, ScanResult
from scan_ingest.services.finding_pipeline import FindingPipelineService
from scan_ingest.services.scan_orchestrator import ScanOrchestrator

logger = logging.getLogger(__name__)


class ScanIngestService:
    """Public application facade for scan → ingest → optional pipeline."""

    def __init__(
        self,
        orchestrator: ScanOrchestrator,
        *,
        pipeline: Optional[FindingPipelineService] = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._pipeline = pipeline

    def scan(self, request: ScanRequest) -> ScanResult:
        """Synchronous scan + ingest (no pipeline). Prefer ``scan_async``."""

        return self._orchestrator.run(request)

    async def scan_async(self, request: ScanRequest) -> ScanResult:
        result = self._orchestrator.run(request)
        if not request.run_pipeline or self._pipeline is None:
            return result
        if not result.findings:
            return result

        pipeline_results = await self._pipeline.run_for_findings(
            result.findings,
            tenant_id=request.tenant_id,
            owner=request.actor,
            asset_id=result.asset_id,
            invoke_ai=request.invoke_ai_decision,
            only_created=True,
        )
        result.pipeline = pipeline_results
        return result
