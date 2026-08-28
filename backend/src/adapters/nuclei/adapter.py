"""Nuclei security tool adapter."""

from __future__ import annotations

import logging
from typing import Any, List

from src.adapters.base.base_adapter import BaseToolAdapter, CommandResult
from src.adapters.base.raw_result import RawResultStatus
from src.adapters.base.registry import AdapterRegistry
from src.adapters.common.execution_context import AdapterExecutionContext
from src.adapters.nuclei.config import NucleiAdapterConfig
from src.adapters.nuclei.parser import NucleiParser

logger = logging.getLogger(__name__)


@AdapterRegistry.register("nuclei")
class NucleiAdapter(BaseToolAdapter):
    """
    Adapter for ProjectDiscovery Nuclei.

    Returns ``RawResult`` only — never ``SecurityFindingObject``.
    """

    tool_name = "nuclei"

    def __init__(self, config: NucleiAdapterConfig, **kwargs: Any) -> None:
        super().__init__(config, **kwargs)
        self._nuclei_config = config
        self._parser = NucleiParser()

    def build_command(self, context: AdapterExecutionContext) -> List[str]:
        command = [self._config.binary_path]
        if self._nuclei_config.json_output:
            command.extend(["-jsonl", "-silent"])
        for template in self._nuclei_config.templates:
            command.extend(["-t", template])
        if self._nuclei_config.severity_filter:
            command.extend(["-severity", self._nuclei_config.severity_filter])
        if self._nuclei_config.rate_limit:
            command.extend(["-rate-limit", str(self._nuclei_config.rate_limit)])
        command.extend(self._config.default_args)
        command.extend(context.arguments)
        for target in context.targets:
            command.extend(["-u", target])
        return command

    def parse(self, stdout: str, stderr: str, exit_code: int) -> Any:
        return self._parser.parse(stdout, stderr, exit_code)

    def map_status(self, result: CommandResult) -> RawResultStatus:
        if result.exit_code in {0, 1}:
            return RawResultStatus.SUCCEEDED
        return RawResultStatus.FAILED

    def version(self) -> str:
        try:
            result = self.run_command(
                [self._config.binary_path, "-version"],
            )
            text = (result.stdout or result.stderr or "").strip()
            return text.splitlines()[0][:128] if text else "nuclei"
        except Exception:  # noqa: BLE001 - version probe must not fail init
            logger.debug("Nuclei version probe failed", exc_info=True)
            return "nuclei"
