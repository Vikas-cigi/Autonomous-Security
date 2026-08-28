"""Grype JSON parser — raw structures only."""

from __future__ import annotations

import json
from typing import Any, Dict

from src.adapters.base.adapter_exception import AdapterParserError


class GrypeParser:
    """Parse Grype JSON reports into raw dict payloads."""

    def parse(self, stdout: str, stderr: str, exit_code: int) -> Dict[str, Any]:
        text = (stdout or "").strip()
        if not text:
            if exit_code == 0:
                return {"matches": []}
            raise AdapterParserError(
                "Grype produced empty stdout with non-zero exit",
                tool_name="grype",
                details={"exit_code": exit_code, "stderr": (stderr or "")[:500]},
            )
        try:
            loaded = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AdapterParserError(
                "Grype stdout is not valid JSON",
                tool_name="grype",
                details=str(exc),
            ) from exc
        if not isinstance(loaded, dict):
            raise AdapterParserError(
                "Grype JSON root must be an object",
                tool_name="grype",
                details={"type": type(loaded).__name__},
            )
        return loaded
