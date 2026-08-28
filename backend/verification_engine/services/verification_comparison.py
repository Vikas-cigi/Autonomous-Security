"""Before/after evidence and risk-snapshot comparison (no risk recalculation)."""

from __future__ import annotations

from typing import List, Optional

from verification_engine.domain.inputs import RiskSnapshotInput, VerificationRequest
from verification_engine.domain.models import (
    VerificationComparison,
    VerificationEvidence,
)


class VerificationComparisonService:
    """
    Compare pre/post evidence and confirm risk reduction from caller-provided scores.

    Never recalculates risk. Never invokes scanners.
    """

    def compare(
        self,
        request: VerificationRequest,
        evidence: List[VerificationEvidence],
    ) -> VerificationComparison:
        pre = [e for e in evidence if e.phase == "pre"]
        post = [e for e in evidence if e.phase == "post"]
        resolved = sum(1 for e in post if e.indicates_resolved is True)
        unresolved = sum(1 for e in post if e.indicates_resolved is False)

        rescan_present = request.rescan.finding_still_present
        pre_risk: Optional[float] = None
        post_risk: Optional[float] = None
        reduction: Optional[float] = None

        if request.risk is not None:
            pre_risk, post_risk, reduction = self._risk_reduction(request.risk)

        parts = [
            f"Compared {len(pre)} pre and {len(post)} post evidence items.",
            f"Resolved signals={resolved}, unresolved signals={unresolved}.",
        ]
        if rescan_present is not None:
            parts.append(
                f"Rescan finding_still_present={rescan_present}."
            )
        if pre_risk is not None and post_risk is not None:
            parts.append(
                f"Risk snapshot {pre_risk:.2f} → {post_risk:.2f} "
                f"(reduction_ratio={reduction:.3f})."
            )
        elif pre_risk is not None:
            parts.append(f"Pre-risk snapshot only: {pre_risk:.2f}.")

        return VerificationComparison(
            pre_evidence_count=len(pre),
            post_evidence_count=len(post),
            resolved_signals=resolved,
            unresolved_signals=unresolved,
            rescan_finding_present=rescan_present,
            pre_risk_score=pre_risk,
            post_risk_score=post_risk,
            risk_reduction_ratio=reduction,
            explanation=" ".join(parts),
        )

    @staticmethod
    def _risk_reduction(
        risk: RiskSnapshotInput,
    ) -> tuple[float, Optional[float], Optional[float]]:
        pre = risk.pre_risk_score
        post = risk.post_risk_score
        if post is None:
            return pre, None, None
        if pre <= 0:
            ratio = 1.0 if post <= 0 else 0.0
        else:
            ratio = max(0.0, min(1.0, (pre - post) / pre))
        return pre, post, ratio
