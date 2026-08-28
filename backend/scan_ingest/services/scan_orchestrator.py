"""ScanOrchestrator — adapter → normalize → evidence ingest."""

from __future__ import annotations

import logging
import time
from typing import Any, List, Optional
from uuid import UUID, uuid4

from models.common import utc_now
from models.enums import ActionClass, PolicyScope
from normalization.context import NormalizationContext
from normalization.service import NormalizationService
from policy_engine import PolicyEngine
from scan_ingest.domain.enums import ScanMode, ScanStatus
from scan_ingest.domain.models import (
    IngestedFindingSummary,
    ScanRequest,
    ScanResult,
)
from scan_ingest.exceptions import ScanAdapterError, ScanValidationError
from scan_ingest.sample_payloads import sample_payload_for_tool
from scan_ingest.services.target_parser import (
    asset_external_id_for_target,
    short_asset_name,
)
from src.adapters.base.factory import AdapterFactory
from src.adapters.base.raw_result import RawResult, RawResultStatus
from src.adapters.checkov.config import CheckovAdapterConfig
from src.adapters.common.execution_context import AdapterExecutionContext
from src.adapters.grype.config import GrypeAdapterConfig
from src.adapters.nuclei.config import NucleiAdapterConfig
from src.adapters.prowler.config import ProwlerAdapterConfig
from src.adapters.trivy.config import TrivyAdapterConfig

logger = logging.getLogger(__name__)

_CONFIGS = {
    "nuclei": NucleiAdapterConfig,
    "trivy": TrivyAdapterConfig,
    "prowler": ProwlerAdapterConfig,
    "checkov": CheckovAdapterConfig,
    "grype": GrypeAdapterConfig,
}


class ScanOrchestrator:
    """
    Glue: resolve/create asset → run scanner (or simulate) → normalize → ingest.

    Does not recalculate trust/risk or call AI. Optional pipeline is a separate
    ``FindingPipelineService`` invoked by the facade when requested.
    """

    def __init__(
        self,
        *,
        asset_services: Any,
        evidence_services: Any,
        normalization: Optional[NormalizationService] = None,
        adapter_factory: Optional[AdapterFactory] = None,
        policy_engine: Optional[PolicyEngine] = None,
    ) -> None:
        self._assets = asset_services
        self._evidence = evidence_services
        self._normalization = normalization or NormalizationService()
        # Import registers builtin adapters.
        import src.adapters  # noqa: F401

        self._policy = policy_engine or PolicyEngine()
        self._factory = adapter_factory or AdapterFactory(policy_engine=self._policy)

    def run(self, request: ScanRequest) -> ScanResult:
        started = time.perf_counter()
        started_at = utc_now()
        scan_id = request.scan_id or f"scan-{uuid4()}"
        errors: List[str] = []
        warnings: List[str] = []

        if not request.target:
            raise ScanValidationError("target is required")

        asset_id = self._resolve_asset(request)
        raw_artifact_id = uuid4()

        try:
            raw = self._obtain_raw_result(request, asset_id=asset_id, scan_id=scan_id)
        except Exception as exc:  # noqa: BLE001 — boundary
            logger.exception("Scan adapter failed scan_id=%s", scan_id)
            return ScanResult(
                scan_id=scan_id,
                status=ScanStatus.FAILED,
                mode=request.mode,
                tool_name=request.tool_name,
                tenant_id=request.tenant_id,
                asset_id=asset_id,
                target=request.target,
                raw_artifact_id=raw_artifact_id,
                errors=[str(exc)],
                started_at=started_at,
                completed_at=utc_now(),
                execution_time_ms=round((time.perf_counter() - started) * 1000, 2),
            )

        if raw.status == RawResultStatus.POLICY_DENIED:
            return ScanResult(
                scan_id=scan_id,
                status=ScanStatus.POLICY_DENIED,
                mode=request.mode,
                tool_name=request.tool_name,
                tenant_id=request.tenant_id,
                asset_id=asset_id,
                target=request.target,
                adapter_status=raw.status.value,
                raw_artifact_id=raw_artifact_id,
                errors=list(raw.errors) or ["Policy denied scan execution"],
                started_at=started_at,
                completed_at=utc_now(),
                execution_time_ms=round((time.perf_counter() - started) * 1000, 2),
            )

        if raw.status not in {RawResultStatus.SUCCEEDED, RawResultStatus.FAILED}:
            errors.extend(raw.errors or [f"Adapter status={raw.status.value}"])

        payload = raw.raw_output if raw.raw_output is not None else raw.stdout
        # Live nuclei may return tool_name nuclei but empty payload on soft fail.
        normalize_tool = request.tool_name
        supported_normalizers = {"nuclei", "trivy", "prowler", "checkov", "grype"}
        if normalize_tool not in supported_normalizers:
            normalize_tool = "nuclei"
            warnings.append(
                f"Unknown tool '{request.tool_name}' for normalization; using nuclei."
            )

        norm_ctx = NormalizationContext(
            tenant_id=request.tenant_id,
            asset_id=asset_id,
            raw_artifact_id=raw_artifact_id,
            scan_id=scan_id,
            default_asset_labels={"target": request.target[:512]},
        )

        try:
            norm = self._normalization.normalize(normalize_tool, payload, norm_ctx)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Normalization failed scan_id=%s", scan_id)
            return ScanResult(
                scan_id=scan_id,
                status=ScanStatus.FAILED,
                mode=request.mode,
                tool_name=request.tool_name,
                tenant_id=request.tenant_id,
                asset_id=asset_id,
                target=request.target,
                adapter_status=raw.status.value,
                raw_artifact_id=raw_artifact_id,
                errors=[f"Normalization failed: {exc}"],
                started_at=started_at,
                completed_at=utc_now(),
                execution_time_ms=round((time.perf_counter() - started) * 1000, 2),
                metadata={"adapter_warnings": raw.warnings},
            )

        summaries: List[IngestedFindingSummary] = []
        created = 0
        merged = 0
        actor_label = request.actor.display_name or str(request.actor.actor_id)

        for finding in norm.findings:
            try:
                result = self._evidence.deduplication.ingest(
                    finding, actor=f"scan-orchestrator:{actor_label}"
                )
                if result.created:
                    created += 1
                else:
                    merged += 1
                summaries.append(
                    IngestedFindingSummary(
                        finding_id=result.finding.id,
                        title=result.finding.title,
                        severity=result.finding.severity.value
                        if hasattr(result.finding.severity, "value")
                        else str(result.finding.severity),
                        created=result.created,
                        fingerprint=result.fingerprint,
                        merged_into_id=result.merged_into_id,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Ingest failed finding=%s", finding.id)
                errors.append(f"Ingest failed for {finding.id}: {exc}")

        if errors and not summaries:
            status = ScanStatus.FAILED
        elif errors or norm.issues:
            status = ScanStatus.PARTIAL
        else:
            status = ScanStatus.SUCCEEDED

        return ScanResult(
            scan_id=scan_id,
            status=status,
            mode=request.mode,
            tool_name=request.tool_name,
            tenant_id=request.tenant_id,
            asset_id=asset_id,
            target=request.target,
            adapter_status=raw.status.value,
            raw_artifact_id=raw_artifact_id,
            findings_normalized=len(norm.findings),
            findings_created=created,
            findings_merged=merged,
            normalization_issues=len(norm.issues),
            findings=summaries,
            errors=errors,
            warnings=warnings + list(raw.warnings or []),
            started_at=started_at,
            completed_at=utc_now(),
            execution_time_ms=round((time.perf_counter() - started) * 1000, 2),
            metadata={
                "norm_issues": [i.error for i in norm.issues[:10]],
                "mode": request.mode.value,
            },
        )

    def _resolve_asset(self, request: ScanRequest) -> UUID:
        if request.asset_id is not None:
            try:
                asset = self._assets.assets.get(request.asset_id, request.tenant_id)
                return asset.id
            except Exception as exc:  # noqa: BLE001
                raise ScanValidationError(
                    f"asset_id not found: {request.asset_id}",
                    details={"error": str(exc)},
                ) from exc

        from asset_inventory.domain.enums import AssetType
        from asset_inventory.domain.models import Asset

        external_id = asset_external_id_for_target(request.target)
        name = request.asset_name or short_asset_name(request.target)
        asset = Asset(
            tenant_id=request.tenant_id,
            name=name,
            asset_type=AssetType.OTHER,
            external_id=external_id,
            hostname=short_asset_name(request.target),
            tags={"source": "scan_ingest", "target": request.target[:200]},
        )
        saved = self._assets.assets.register_asset(
            asset, actor="scan-orchestrator"
        )
        return saved.id

    def _obtain_raw_result(
        self,
        request: ScanRequest,
        *,
        asset_id: UUID,
        scan_id: str,
    ) -> RawResult:
        if request.mode == ScanMode.SIMULATE:
            return self._simulate_raw(request, asset_id=asset_id, scan_id=scan_id)

        config_cls = _CONFIGS.get(request.tool_name)
        if config_cls is None:
            raise ScanAdapterError(
                f"Unsupported live tool '{request.tool_name}'. "
                f"Supported: {sorted(_CONFIGS)}"
            )

        ctx = AdapterExecutionContext(
            tenant_id=request.tenant_id,
            asset_id=asset_id,
            user=request.actor,
            roles=list(request.roles) or ["secops"],
            scope=PolicyScope.TENANT,
            action_class=ActionClass.SIMULATE,
            targets=[request.target],
            allowed_targets=[request.target],
            tags=list(request.tags) + ["scan_ingest"],
            attributes={
                **request.attributes,
                "scan_id": scan_id,
                "simulation": True,
            },
        )
        adapter = self._factory.create(request.tool_name, config_cls())
        try:
            return adapter.run(ctx)
        except Exception as exc:  # noqa: BLE001
            raise ScanAdapterError(
                f"Live adapter '{request.tool_name}' failed: {exc}",
                details={"scan_id": scan_id, "target": request.target},
            ) from exc

    def _simulate_raw(
        self,
        request: ScanRequest,
        *,
        asset_id: UUID,
        scan_id: str,
    ) -> RawResult:
        now = utc_now()
        payload = sample_payload_for_tool(request.tool_name, request.target)
        return RawResult(
            tenant_id=request.tenant_id,
            tool_name=request.tool_name,
            tool_version="simulate-1.0.0",
            execution_time_ms=1.0,
            started_at=now,
            completed_at=now,
            status=RawResultStatus.SUCCEEDED,
            exit_code=0,
            stdout="",
            raw_output=payload,
            metadata={"mode": "simulate", "scan_id": scan_id},
            asset={"asset_id": str(asset_id), "target": request.target},
            tags=["simulate", "scan_ingest"],
        )
