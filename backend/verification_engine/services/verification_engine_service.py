"""VerificationEngineService — facade for post-execution verification."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from models.common import new_id, utc_now

from verification_engine.domain.enums import (
    AuditAction,
    VerificationEventType,
    VerificationStatus,
)
from verification_engine.domain.inputs import VerificationRequest
from verification_engine.domain.models import (
    ALGORITHM_VERSION,
    VerificationEvent,
    VerificationResult,
    VerificationTimeline,
)
from verification_engine.interfaces.verification_evidence_repository import (
    VerificationEvidenceRepository,
)
from verification_engine.interfaces.verification_repository import VerificationRepository
from verification_engine.query.filters import VerificationSearchFilter
from verification_engine.query.pagination import Page, PageRequest
from verification_engine.services.verification_audit import VerificationAuditService
from verification_engine.services.verification_check_runner import VerificationCheckRunner
from verification_engine.services.verification_comparison import (
    VerificationComparisonService,
)
from verification_engine.services.verification_evidence import VerificationEvidenceService
from verification_engine.services.verification_history_service import (
    VerificationHistoryService,
)
from verification_engine.services.verification_reporting import (
    VerificationReportingService,
)
from verification_engine.services.verification_validation import (
    VerificationValidationService,
)
from verification_engine.services.verification_workflow import VerificationWorkflowService


class VerificationEngineService:
    """
    Validate remediation effectiveness after Execution Engine.

    Pipeline: Execution → **Verification Engine** → Reporting & Analytics.

    Never executes remediation, recalculates risk/trust, invokes AI,
    modifies plans, or performs approval.
    """

    def __init__(
        self,
        verification_repository: VerificationRepository,
        *,
        evidence_repository: Optional[VerificationEvidenceRepository] = None,
        validation: Optional[VerificationValidationService] = None,
        workflow: Optional[VerificationWorkflowService] = None,
        comparison: Optional[VerificationComparisonService] = None,
        evidence: Optional[VerificationEvidenceService] = None,
        checks: Optional[VerificationCheckRunner] = None,
        reporting: Optional[VerificationReportingService] = None,
        audit: Optional[VerificationAuditService] = None,
        history: Optional[VerificationHistoryService] = None,
    ) -> None:
        self._repo = verification_repository
        self._evidence_repo = evidence_repository
        self._validation = validation or VerificationValidationService()
        self._workflow = workflow or VerificationWorkflowService()
        self._comparison = comparison or VerificationComparisonService()
        self._evidence = evidence or VerificationEvidenceService(evidence_repository)
        self._checks = checks or VerificationCheckRunner()
        self._reporting = reporting or VerificationReportingService()
        self._audit = audit or VerificationAuditService()
        self._history = history or VerificationHistoryService(verification_repository)

    def verify(
        self,
        request: VerificationRequest,
        *,
        persist: bool = True,
        actor: Optional[str] = None,
        verification_id: Optional[UUID] = None,
        run: bool = True,
    ) -> VerificationResult:
        self._validation.validate_request(request)
        result = self.create(request, verification_id=verification_id)
        if persist:
            result = self._repo.save(
                result,
                actor=actor or request.actor or request.operator,
                change_summary="Verification created",
            )
            self._audit.record(
                action=AuditAction.VERIFICATION_CREATED,
                message="Verification created from execution handoff",
                verification_id=result.id,
                execution_id=result.execution_id,
                finding_id=result.finding_id,
                plan_id=result.plan_id,
                tenant_id=result.tenant_id,
                actor=actor or request.actor,
                status=result.status.value,
            )
        if run:
            result = self.start(
                result.id,
                result.tenant_id,
                request=request,
                persist=persist,
                actor=actor or request.actor or request.operator,
            )
        return result

    def create(
        self,
        request: VerificationRequest,
        *,
        verification_id: Optional[UUID] = None,
    ) -> VerificationResult:
        vid = verification_id or new_id()
        now = request.evaluated_at or utc_now()
        plan = self._workflow.build_plan(request)
        return VerificationResult(
            id=vid,
            tenant_id=request.decision.tenant_id,
            execution_id=request.execution.execution_id,
            plan_id=request.plan.plan_id,
            finding_id=request.finding.finding_id,
            decision_id=request.decision.decision_id,
            asset_id=request.asset.asset_id if request.asset else None,
            status=VerificationStatus.PENDING,
            plan=plan,
            timeline=VerificationTimeline(queued_at=now),
            events=[
                VerificationEvent(
                    verification_id=vid,
                    event_type=VerificationEventType.CREATED,
                    message="Verification queued",
                    details={"execution_id": str(request.execution.execution_id)},
                )
            ],
            operator=request.operator,
            algorithm_version=ALGORITHM_VERSION,
            last_evaluated_at=now,
        )

    def start(
        self,
        verification_id: UUID,
        tenant_id: UUID,
        *,
        request: VerificationRequest,
        persist: bool = True,
        actor: Optional[str] = None,
    ) -> VerificationResult:
        result = self._repo.get(verification_id, tenant_id) if persist else None
        if result is None:
            # ephemeral path: recreate from request with given id
            result = self.create(request, verification_id=verification_id)

        self._validation.ensure_runnable(result)
        started = utc_now()
        result.status = VerificationStatus.RUNNING
        result.first_started_at = result.first_started_at or started
        result.timeline.started_at = started
        result.events.append(
            VerificationEvent(
                verification_id=result.id,
                event_type=VerificationEventType.STARTED,
                message="Verification started",
            )
        )
        if persist:
            result = self._repo.save(
                result,
                actor=actor,
                change_summary="Verification started",
            )
            self._audit.record(
                action=AuditAction.VERIFICATION_STARTED,
                message="Verification started",
                verification_id=result.id,
                execution_id=result.execution_id,
                finding_id=result.finding_id,
                plan_id=result.plan_id,
                tenant_id=result.tenant_id,
                actor=actor,
                status=result.status.value,
            )

        return self._evaluate(
            result,
            request=request,
            persist=persist,
            actor=actor,
            started_at=started,
        )

    def replay(
        self,
        verification_id: UUID,
        tenant_id: UUID,
        request: VerificationRequest,
        *,
        persist: bool = True,
        actor: Optional[str] = None,
    ) -> VerificationResult:
        """Re-run verification against a new evidence/rescan snapshot (versioned)."""
        self._validation.validate_request(request)
        existing = self._repo.get(verification_id, tenant_id)
        result = self.create(request, verification_id=existing.id)
        result.current_version = existing.current_version
        result.first_started_at = existing.first_started_at
        result.events.append(
            VerificationEvent(
                verification_id=result.id,
                event_type=VerificationEventType.REPLAYED,
                message="Verification replay initiated",
            )
        )
        self._audit.record(
            action=AuditAction.REPLAYED,
            message="Verification replay",
            verification_id=result.id,
            execution_id=result.execution_id,
            finding_id=result.finding_id,
            plan_id=result.plan_id,
            tenant_id=result.tenant_id,
            actor=actor,
            status=result.status.value,
        )
        result.status = VerificationStatus.RUNNING
        started = utc_now()
        result.timeline.started_at = started
        if persist:
            result = self._repo.save(
                result, actor=actor, change_summary="Verification replay started"
            )
        return self._evaluate(
            result,
            request=request,
            persist=persist,
            actor=actor,
            started_at=started,
        )

    def cancel(
        self,
        verification_id: UUID,
        tenant_id: UUID,
        *,
        persist: bool = True,
        actor: Optional[str] = None,
        reason: str = "Cancelled by operator",
    ) -> VerificationResult:
        result = self._repo.get(verification_id, tenant_id)
        self._validation.ensure_cancellable(result)
        now = utc_now()
        result.status = VerificationStatus.CANCELLED
        result.timeline.cancelled_at = now
        result.timeline.completed_at = now
        result.events.append(
            VerificationEvent(
                verification_id=result.id,
                event_type=VerificationEventType.CANCELLED,
                message=reason,
            )
        )
        if persist:
            result = self._repo.save(
                result, actor=actor, change_summary=reason
            )
            self._audit.record(
                action=AuditAction.VERIFICATION_CANCELLED,
                message=reason,
                verification_id=result.id,
                execution_id=result.execution_id,
                finding_id=result.finding_id,
                plan_id=result.plan_id,
                tenant_id=result.tenant_id,
                actor=actor,
                status=result.status.value,
            )
        return result

    def get(self, verification_id: UUID, tenant_id: UUID) -> VerificationResult:
        return self._repo.get(verification_id, tenant_id)

    def search(
        self,
        filters: VerificationSearchFilter,
        page: Optional[PageRequest] = None,
    ) -> Page[VerificationResult]:
        return self._repo.search(filters, page or PageRequest())

    def list_versions(self, verification_id: UUID, tenant_id: UUID):
        return self._history.list_versions(verification_id, tenant_id)

    def _evaluate(
        self,
        result: VerificationResult,
        *,
        request: VerificationRequest,
        persist: bool,
        actor: Optional[str],
        started_at,
    ) -> VerificationResult:
        evidence = self._evidence.collect(request)
        result.evidence = evidence
        if persist and self._evidence_repo is not None:
            result.evidence = self._evidence.persist(
                verification_id=result.id,
                tenant_id=result.tenant_id,
                evidence=evidence,
            )
            self._audit.record(
                action=AuditAction.EVIDENCE_RECORDED,
                message=f"Recorded {len(result.evidence)} evidence items",
                verification_id=result.id,
                execution_id=result.execution_id,
                finding_id=result.finding_id,
                plan_id=result.plan_id,
                tenant_id=result.tenant_id,
                actor=actor,
                status=result.status.value,
                details={"count": len(result.evidence)},
            )

        comparison = self._comparison.compare(request, result.evidence)
        result.comparison = comparison
        result.events.append(
            VerificationEvent(
                verification_id=result.id,
                event_type=VerificationEventType.COMPARISON_COMPLETED,
                message=comparison.explanation[:2000],
            )
        )

        checks = self._checks.run_all(
            request=request,
            plan=result.plan,
            evidence=result.evidence,
            comparison=comparison,
        )
        result.checks = checks
        for c in checks:
            evt = (
                VerificationEventType.CHECK_PASSED
                if c.passed
                else VerificationEventType.CHECK_FAILED
            )
            if c.status.value != "skipped":
                result.events.append(
                    VerificationEvent(
                        verification_id=result.id,
                        event_type=evt,
                        message=f"{c.name}: {c.details}"[:2000],
                        details={"check_type": c.check_type.value, "passed": str(c.passed)},
                    )
                )
            self._audit.record(
                action=AuditAction.CHECK_RECORDED,
                message=c.details[:4000],
                verification_id=result.id,
                execution_id=result.execution_id,
                finding_id=result.finding_id,
                plan_id=result.plan_id,
                tenant_id=result.tenant_id,
                actor=actor,
                status=c.status.value,
                details={"check_type": c.check_type.value, "passed": c.passed},
            )

        if request.rescan.performed:
            result.events.append(
                VerificationEvent(
                    verification_id=result.id,
                    event_type=VerificationEventType.RESCAN_COMPLETED,
                    message=request.rescan.summary or "Rescan completed",
                    details={
                        "finding_still_present": str(
                            request.rescan.finding_still_present
                        )
                    },
                )
            )

        status, closure, disposition, rationale = self._workflow.resolve_outcome(
            request=request, checks=checks
        )
        result.status = status
        result.closure_recommendation = closure
        result.finding = self._reporting.build_finding(
            finding_id=request.finding.finding_id,
            prior_status=request.finding.status,
            disposition=disposition,
            rationale=rationale,
        )
        completed = utc_now()
        result.timeline.completed_at = completed
        duration_ms = max(
            0, int((completed - started_at).total_seconds() * 1000)
        )
        result.metrics = self._reporting.build_metrics(
            checks,
            duration_ms=duration_ms,
            evidence_compared=len(result.evidence),
        )
        result.summary = self._reporting.build_summary(
            status=status,
            closure=closure,
            rationale=rationale,
            checks=checks,
        )
        result = self._reporting.attach_outputs(result)

        if status == VerificationStatus.ESCALATED:
            result.events.append(
                VerificationEvent(
                    verification_id=result.id,
                    event_type=VerificationEventType.ESCALATED,
                    message=rationale,
                )
            )
            audit_action = AuditAction.ESCALATED
        elif status == VerificationStatus.REOPENED:
            result.events.append(
                VerificationEvent(
                    verification_id=result.id,
                    event_type=VerificationEventType.REOPENED,
                    message=rationale,
                )
            )
            audit_action = AuditAction.REOPENED
        elif status in {VerificationStatus.VERIFIED, VerificationStatus.COMPLETED}:
            result.events.append(
                VerificationEvent(
                    verification_id=result.id,
                    event_type=VerificationEventType.COMPLETED,
                    message=rationale,
                )
            )
            audit_action = AuditAction.VERIFICATION_COMPLETED
        else:
            result.events.append(
                VerificationEvent(
                    verification_id=result.id,
                    event_type=VerificationEventType.FAILED,
                    message=rationale,
                )
            )
            audit_action = AuditAction.VERIFICATION_FAILED

        result.last_evaluated_at = completed
        if persist:
            result = self._repo.save(
                result,
                actor=actor,
                change_summary=f"Verification finished: {status.value}",
            )
            self._audit.record(
                action=audit_action,
                message=rationale,
                verification_id=result.id,
                execution_id=result.execution_id,
                finding_id=result.finding_id,
                plan_id=result.plan_id,
                tenant_id=result.tenant_id,
                actor=actor,
                status=result.status.value,
                details={
                    "closure_recommendation": closure.value,
                    "disposition": disposition.value,
                },
            )
        return result
