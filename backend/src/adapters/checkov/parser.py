"""Checkov JSON parser — raw structures only."""

from __future__ import annotations

import json
from typing import Any, Dict

from src.adapters.base.adapter_exception import AdapterParserError


class CheckovParser:
    """Parse Checkov JSON reports into raw dict payloads."""

    def parse(self, stdout: str, stderr: str, exit_code: int) -> Dict[str, Any]:
        text = (stdout or "").strip()
        if not text:
            if exit_code == 0:
                return {"results": {"failed_checks": []}}
            raise AdapterParserError(
                "Checkov produced empty stdout with non-zero exit",
                tool_name="checkov",
                details={"exit_code": exit_code, "stderr": (stderr or "")[:500]},
            )
        try:
            loaded = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AdapterParserError(
                "Checkov stdout is not valid JSON",
                tool_name="checkov",
                details=str(exc),
            ) from exc
        if not isinstance(loaded, (dict, list)):
            raise AdapterParserError(
                "Unexpected Checkov JSON root type",
                tool_name="checkov",
                details={"type": type(loaded).__name__},
            )
        if isinstance(loaded, list):
            return {"results": {"failed_checks": loaded}}
        return loaded
