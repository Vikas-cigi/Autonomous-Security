"""Nuclei stdout/JSONL parser — returns raw structures only."""

from __future__ import annotations

import json
from typing import Any, List

from src.adapters.base.adapter_exception import AdapterParserError


class NucleiParser:
    """Parse Nuclei JSON or JSONL into a list of raw result objects."""

    def parse(self, stdout: str, stderr: str, exit_code: int) -> List[Any]:
        text = (stdout or "").strip()
        if not text:
            if exit_code == 0:
                return []
            raise AdapterParserError(
                "Nuclei produced empty stdout with non-zero exit",
                tool_name="nuclei",
                details={"exit_code": exit_code, "stderr": (stderr or "")[:500]},
            )

        try:
            loaded = json.loads(text)
            if isinstance(loaded, list):
                return loaded
            if isinstance(loaded, dict):
                return [loaded]
        except json.JSONDecodeError:
            pass

        items: List[Any] = []
        for line_no, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise AdapterParserError(
                    f"Invalid Nuclei JSONL at line {line_no}",
                    tool_name="nuclei",
                    details=str(exc),
                ) from exc
            items.append(obj)
        return items
