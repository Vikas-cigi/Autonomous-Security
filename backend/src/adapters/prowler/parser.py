"""Prowler JSON parser — raw structures only."""

from __future__ import annotations

import json
from typing import Any, List

from src.adapters.base.adapter_exception import AdapterParserError


class ProwlerParser:
    """Parse Prowler JSON exports into a list of raw finding dicts."""

    def parse(self, stdout: str, stderr: str, exit_code: int) -> List[Any]:
        text = (stdout or "").strip()
        if not text:
            if exit_code == 0:
                return []
            raise AdapterParserError(
                "Prowler produced empty stdout with non-zero exit",
                tool_name="prowler",
                details={"exit_code": exit_code, "stderr": (stderr or "")[:500]},
            )
        try:
            loaded = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AdapterParserError(
                "Prowler stdout is not valid JSON",
                tool_name="prowler",
                details=str(exc),
            ) from exc

        if isinstance(loaded, list):
            return loaded
        if isinstance(loaded, dict):
            for key in ("findings", "results", "Checks", "checks"):
                value = loaded.get(key)
                if isinstance(value, list):
                    return value
            return [loaded]
        raise AdapterParserError(
            "Unexpected Prowler JSON root type",
            tool_name="prowler",
            details={"type": type(loaded).__name__},
        )
