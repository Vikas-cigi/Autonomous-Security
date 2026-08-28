"""Prepare (do not send) approval notifications."""

from __future__ import annotations

from typing import List

from models.common import new_id, utc_now

from approval_engine.domain.enums import NotificationKind, NotificationStatus
from approval_engine.domain.models import ApprovalNotification, ApprovalRequest


class NotificationPreparationService:
    """
    Build notification payloads for downstream delivery systems.

    Never sends email/Slack/etc. — preparation only.
    """

    def prepare_request_notifications(
        self, approval: ApprovalRequest
    ) -> List[ApprovalNotification]:
        notes: List[ApprovalNotification] = []
        for recipient in approval.assigned_approvers:
            notes.append(
                ApprovalNotification(
                    id=new_id(),
                    approval_id=approval.id,
                    kind=NotificationKind.REQUESTED,
                    recipient=recipient,
                    subject=f"Approval required: plan {approval.plan_id}",
                    body=(
                        f"Approval {approval.id} is {approval.state.value}.\n"
                        f"{approval.summary}\n"
                        f"Expires: {approval.timeline.expires_at}"
                    ),
                    status=NotificationStatus.PREPARED,
                    created_at=utc_now(),
                )
            )
        return notes

    def prepare_decision_notifications(
        self, approval: ApprovalRequest
    ) -> List[ApprovalNotification]:
        recipient = approval.requester or "requester@tenant.local"
        return [
            ApprovalNotification(
                id=new_id(),
                approval_id=approval.id,
                kind=NotificationKind.DECIDED,
                recipient=recipient,
                subject=f"Approval {approval.state.value}: plan {approval.plan_id}",
                body=approval.summary,
                status=NotificationStatus.PREPARED,
                created_at=utc_now(),
            )
        ]

    def prepare_escalation_notifications(
        self, approval: ApprovalRequest, recipients: List[str]
    ) -> List[ApprovalNotification]:
        return [
            ApprovalNotification(
                id=new_id(),
                approval_id=approval.id,
                kind=NotificationKind.ESCALATED,
                recipient=r,
                subject=f"Escalated approval: plan {approval.plan_id}",
                body=approval.workflow.escalation_reason or approval.summary,
                status=NotificationStatus.PREPARED,
                created_at=utc_now(),
            )
            for r in recipients
        ]
