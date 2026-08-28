"""AIValidationService — structured output / JSON schema validation."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Set

from ai_harness.domain.enums import ValidationSeverity
from ai_harness.domain.models import (
    AIRequest,
    AIValidationIssue,
    AIValidationResult,
)

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


class AIValidationService:
    """
    Validate AI text against expect_json / required keys / optional JSON Schema.

    Supports a pragmatic JSON Schema subset: type=object, required, properties
    with type in {string, number, integer, boolean, object, array}.
    No cybersecurity business rules.
    """

    def validate(self, request: AIRequest, text: str) -> AIValidationResult:
        if not request.expect_json and not request.json_schema and not request.required_json_keys:
            return AIValidationResult(valid=True, issues=[], parsed_payload=None)

        issues: List[AIValidationIssue] = []
        payload = self._extract_json(text)
        if payload is None:
            issues.append(
                AIValidationIssue(
                    code="json_parse_error",
                    severity=ValidationSeverity.ERROR,
                    message="Response is not valid JSON object.",
                )
            )
            return AIValidationResult(
                valid=False,
                issues=issues,
                schema_name=request.schema_name,
            )

        for key in request.required_json_keys:
            if key not in payload:
                issues.append(
                    AIValidationIssue(
                        code="missing_required_key",
                        severity=ValidationSeverity.ERROR,
                        message=f"Missing required key '{key}'.",
                        path=key,
                    )
                )

        if request.json_schema:
            issues.extend(self._validate_schema(payload, request.json_schema, path="$"))

        valid = not any(i.severity == ValidationSeverity.ERROR for i in issues)
        return AIValidationResult(
            valid=valid,
            issues=issues,
            parsed_payload=payload if valid or payload is not None else None,
            schema_name=request.schema_name,
        )

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        if not text or not text.strip():
            return None
        stripped = text.strip()
        try:
            data = json.loads(stripped)
            return data if isinstance(data, dict) else None
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

    def _validate_schema(
        self,
        value: Any,
        schema: Dict[str, Any],
        *,
        path: str,
    ) -> List[AIValidationIssue]:
        issues: List[AIValidationIssue] = []
        expected_type = schema.get("type")
        if expected_type == "object":
            if not isinstance(value, dict):
                issues.append(
                    AIValidationIssue(
                        code="type_mismatch",
                        severity=ValidationSeverity.ERROR,
                        message=f"Expected object at {path}",
                        path=path,
                    )
                )
                return issues
            required: Set[str] = set(schema.get("required") or [])
            for key in required:
                if key not in value:
                    issues.append(
                        AIValidationIssue(
                            code="schema_required",
                            severity=ValidationSeverity.ERROR,
                            message=f"Schema requires '{key}' at {path}",
                            path=f"{path}.{key}",
                        )
                    )
            properties = schema.get("properties") or {}
            for key, subschema in properties.items():
                if key in value and isinstance(subschema, dict):
                    issues.extend(
                        self._validate_schema(
                            value[key],
                            subschema,
                            path=f"{path}.{key}",
                        )
                    )
        elif expected_type == "array":
            if not isinstance(value, list):
                issues.append(
                    AIValidationIssue(
                        code="type_mismatch",
                        severity=ValidationSeverity.ERROR,
                        message=f"Expected array at {path}",
                        path=path,
                    )
                )
        elif expected_type == "string":
            if not isinstance(value, str):
                issues.append(
                    AIValidationIssue(
                        code="type_mismatch",
                        severity=ValidationSeverity.ERROR,
                        message=f"Expected string at {path}",
                        path=path,
                    )
                )
        elif expected_type == "number":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                issues.append(
                    AIValidationIssue(
                        code="type_mismatch",
                        severity=ValidationSeverity.ERROR,
                        message=f"Expected number at {path}",
                        path=path,
                    )
                )
        elif expected_type == "integer":
            if not isinstance(value, int) or isinstance(value, bool):
                issues.append(
                    AIValidationIssue(
                        code="type_mismatch",
                        severity=ValidationSeverity.ERROR,
                        message=f"Expected integer at {path}",
                        path=path,
                    )
                )
        elif expected_type == "boolean":
            if not isinstance(value, bool):
                issues.append(
                    AIValidationIssue(
                        code="type_mismatch",
                        severity=ValidationSeverity.ERROR,
                        message=f"Expected boolean at {path}",
                        path=path,
                    )
                )
        enum_values = schema.get("enum")
        if enum_values is not None and value not in enum_values:
            issues.append(
                AIValidationIssue(
                    code="enum_mismatch",
                    severity=ValidationSeverity.ERROR,
                    message=f"Value not in enum at {path}",
                    path=path,
                )
            )
        return issues
