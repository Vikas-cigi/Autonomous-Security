"""Trivy JSON parser — raw structures only."""

from __future__ import annotations

import json
from typing import Any, Dict

from src.adapters.base.adapter_exception import AdapterParserError


class TrivyParser:
    """Parse Trivy JSON reports into raw dict payloads."""

    def parse(self, stdout: str, stderr: str, exit_code: int) -> Dict[str, Any]:
        text = (stdout or "").strip()
        if not text:
            if exit_code == 0:
                return {"Results": []}
            raise AdapterParserError(
                "Trivy produced empty stdout with non-zero exit",
                tool_name="trivy",
                details={"exit_code": exit_code, "stderr": (stderr or "")[:500]},
            )
        try:
            loaded = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AdapterParserError(
                "Trivy stdout is not valid JSON",
                tool_name="trivy",
                details=str(exc),
            ) from exc
        if not isinstance(loaded, dict):
            raise AdapterParserError(
                "Trivy JSON root must be an object",
                tool_name="trivy",
                details={"type": type(loaded).__name__},
            )
        return loaded
