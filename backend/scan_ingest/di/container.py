"""Dependency injection for Scan / Ingest."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from asset_inventory import AssetInventoryContainer
from evidence_repository import EvidenceRepositoryContainer
from normalization.service import NormalizationService
from policy_engine import PolicyEngine
from scan_ingest.services.finding_pipeline import FindingPipelineService
from scan_ingest.services.scan_ingest_service import ScanIngestService
from scan_ingest.services.scan_orchestrator import ScanOrchestrator
from src.adapters.base.factory import AdapterFactory


@dataclass
class ScanIngestSession:
    """Holds open sessions + services; use as a context manager."""

    engine: ScanIngestService
    orchestrator: ScanOrchestrator
    pipeline: Optional[FindingPipelineService]
    _asset_cm: object
    _evidence_cm: object
    _trust_cm: Optional[object] = None
    _risk_cm: Optional[object] = None
    _decision_cm: Optional[object] = None
    _planner_cm: Optional[object] = None

    def __enter__(self) -> "ScanIngestSession":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        for cm in (
            self._planner_cm,
            self._decision_cm,
            self._risk_cm,
            self._trust_cm,
            self._evidence_cm,
            self._asset_cm,
        ):
            if cm is None:
                continue
            try:
                cm.__exit__(exc_type, exc, tb)
            except Exception:  # noqa: BLE001
                pass


class ScanIngestContainer:
    """Composition root for Scan / Ingest + optional finding pipeline."""

    def __init__(
        self,
        asset_container: AssetInventoryContainer,
        evidence_container: EvidenceRepositoryContainer,
        *,
        trust_container: Optional[object] = None,
        risk_container: Optional[object] = None,
        decision_container: Optional[object] = None,
        planner_container: Optional[object] = None,
    ) -> None:
        self.asset_container = asset_container
        self.evidence_container = evidence_container
        self.trust_container = trust_container
        self.risk_container = risk_container
        self.decision_container = decision_container
        self.planner_container = planner_container

    @classmethod
    def from_url(
        cls,
        database_url: str,
        *,
        echo: bool = False,
        create_tables: bool = False,
        trust_container: Optional[object] = None,
        risk_container: Optional[object] = None,
        decision_container: Optional[object] = None,
        planner_container: Optional[object] = None,
    ) -> "ScanIngestContainer":
        return cls(
            AssetInventoryContainer.from_url(
                database_url, echo=echo, create_tables=create_tables
            ),
            EvidenceRepositoryContainer.from_url(
                database_url, echo=echo, create_tables=create_tables
            ),
            trust_container=trust_container,
            risk_container=risk_container,
            decision_container=decision_container,
            planner_container=planner_container,
        )

    def session_scope(self, *, enable_pipeline: bool = True) -> ScanIngestSession:
        asset_cm = self.asset_container.session()
        evidence_cm = self.evidence_container.session()
        asset_session = asset_cm.__enter__()
        evidence_session = evidence_cm.__enter__()

        asset_svc = self.asset_container.build(asset_session)
        evidence_svc = self.evidence_container.build(evidence_session)

        policy = PolicyEngine()
        orchestrator = ScanOrchestrator(
            asset_services=asset_svc,
            evidence_services=evidence_svc,
            normalization=NormalizationService(),
            adapter_factory=AdapterFactory(policy_engine=policy),
            policy_engine=policy,
        )

        pipeline: Optional[FindingPipelineService] = None
        trust_cm = risk_cm = decision_cm = planner_cm = None

        if (
            enable_pipeline
            and self.trust_container is not None
            and self.risk_container is not None
            and self.decision_container is not None
            and self.planner_container is not None
        ):
            trust_cm = self.trust_container.session()
            risk_cm = self.risk_container.session()
            decision_cm = self.decision_container.session()
            planner_cm = self.planner_container.session()
            trust_session = trust_cm.__enter__()
            risk_session = risk_cm.__enter__()
            decision_session = decision_cm.__enter__()
            planner_session = planner_cm.__enter__()

            trust_svc = self.trust_container.build(trust_session)
            risk_svc = self.risk_container.build(risk_session)
            decision_svc = self.decision_container.build(decision_session)
            planner_svc = self.planner_container.build(planner_session)

            pipeline = FindingPipelineService(
                trust_scoring=trust_svc.scoring,
                risk_engine=risk_svc.risk_engine,
                decision_service=decision_svc.decision,
                planner=planner_svc.planner,
                evidence_repository=evidence_svc.repository,
            )

        engine = ScanIngestService(orchestrator, pipeline=pipeline)
        return ScanIngestSession(
            engine=engine,
            orchestrator=orchestrator,
            pipeline=pipeline,
            _asset_cm=asset_cm,
            _evidence_cm=evidence_cm,
            _trust_cm=trust_cm,
            _risk_cm=risk_cm,
            _decision_cm=decision_cm,
            _planner_cm=planner_cm,
        )
