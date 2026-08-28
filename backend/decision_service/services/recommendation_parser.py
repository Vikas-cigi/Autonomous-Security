"""Parse structured AI responses into DecisionRecommendation."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from models.enums import RecommendedAction
from decision_service.domain.enums import DecisionSource, SecurityDecisionType
from decision_service.domain.mapping import (
    to_canonical_priority,
    to_recommended_action,
)
from decision_service.domain.models import (
    AIResponseEnvelope,
    DecisionContext,
    DecisionRecommendation,
)


_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


class DecisionRecommendationParser:
    """Extract DecisionRecommendation from AI text; fail soft to None."""

    ACTION_ALIASES: Dict[str, RecommendedAction] = {
        "apply_patch": RecommendedAction.APPLY_PATCH,
        "patch": RecommendedAction.APPLY_PATCH,
        "change_configuration": RecommendedAction.CHANGE_CONFIGURATION,
        "manual_review": RecommendedAction.MANUAL_REVIEW,
        "verify_only": RecommendedAction.VERIFY_ONLY,
        "run_simulation": RecommendedAction.RUN_SIMULATION,
        "isolate_asset": RecommendedAction.ISOLATE_ASSET,
        "other": RecommendedAction.OTHER,
    }

    def parse(
        self,
        ai_response: AIResponseEnvelope,
        context: DecisionContext,
        *,
        preferred_action: Optional[RecommendedAction] = None,
    ) -> Optional[DecisionRecommendation]:
        payload = self._extract_json(ai_response.text)
        if not payload:
            return None

        decision_type = self._parse_decision_type(payload.get("decision_type"))
        if decision_type is None:
            return None

        confidence = self._parse_confidence(payload.get("confidence"), context)
        action_override = self._parse_action(payload.get("recommended_action"))
        recommended = to_recommended_action(
            decision_type,
            override=preferred_action or action_override,
        )
        priority = to_canonical_priority(context.risk_priority, context.risk_level)

        business = str(
            payload.get("business_justification")
            or payload.get("business_justification".upper())
            or f"AI-assisted decision for risk={context.enterprise_risk_score:.2f}."
        )[:4000]
        technical = str(
            payload.get("technical_justification")
            or f"AI-assisted decision with trust={context.trust_score:.2f}."
        )[:4000]
        next_step = str(
            payload.get("next_step")
            or payload.get("recommended_next_step")
            or "Review AI recommendation and proceed per policy."
        )[:2000]

        return DecisionRecommendation(
            decision_type=decision_type,
            confidence=confidence,
            recommended_action=recommended,
            priority=priority,
            next_step=next_step,
            business_justification=business,
            technical_justification=technical,
            source=DecisionSource.AI,
            raw_ai_text=ai_response.text[:16000],
        )

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        if not text or not text.strip():
            return None
        stripped = text.strip()
        try:
            data = json.loads(stripped)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
        match = _JSON_BLOCK.search(stripped)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _parse_decision_type(value: Any) -> Optional[SecurityDecisionType]:
        if value is None:
            return None
        token = str(value).strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "remediate": SecurityDecisionType.REMEDIATE,
            "fix": SecurityDecisionType.REMEDIATE,
            "ignore": SecurityDecisionType.IGNORE,
            "suppress": SecurityDecisionType.IGNORE,
            "no_action": SecurityDecisionType.IGNORE,
            "escalate": SecurityDecisionType.ESCALATE,
            "investigate": SecurityDecisionType.INVESTIGATE,
            "monitor": SecurityDecisionType.MONITOR,
        }
        return aliases.get(token)

    @staticmethod
    def _parse_confidence(value: Any, context: DecisionContext) -> float:
        try:
            conf = float(value)
            if conf > 1.0 and conf <= 100.0:
                conf = conf / 100.0
            return round(max(0.0, min(1.0, conf)), 4)
        except (TypeError, ValueError):
            return round(
                max(0.05, min(0.99, 0.5 * (context.trust_score / 100.0) + 0.5 * 0.5)),
                4,
            )

    def _parse_action(self, value: Any) -> Optional[RecommendedAction]:
        if value is None:
            return None
        token = str(value).strip().lower().replace("-", "_").replace(" ", "_")
        if token in self.ACTION_ALIASES:
            return self.ACTION_ALIASES[token]
        try:
            return RecommendedAction(token)
        except ValueError:
            return None
