"""Prowler security tool adapter."""

from __future__ import annotations

import logging
from typing import Any, List

from src.adapters.base.base_adapter import BaseToolAdapter, CommandResult
from src.adapters.base.raw_result import RawResultStatus
from src.adapters.base.registry import AdapterRegistry
from src.adapters.common.authentication import EnvironmentTokenAuthenticator
from src.adapters.common.execution_context import AdapterExecutionContext
from src.adapters.prowler.config import ProwlerAdapterConfig
from src.adapters.prowler.parser import ProwlerParser

logger = logging.getLogger(__name__)


@AdapterRegistry.register("prowler")
class ProwlerAdapter(BaseToolAdapter):
    """
    Adapter for Prowler multi-cloud checks.

    Authentication uses cloud credentials via environment / config token.
    ``context.targets`` carry account / subscription identifiers recorded in
    scope metadata; CLI selection uses provider flags and ``arguments``.
    """

    tool_name = "prowler"

    def __init__(self, config: ProwlerAdapterConfig, **kwargs: Any) -> None:
        authenticator = kwargs.pop(
            "authenticator",
            EnvironmentTokenAuthenticator(
                required=False,
                env_keys=[
                    "AWS_ACCESS_KEY_ID",
                    "AWS_PROFILE",
                    "AZURE_CLIENT_ID",
                    "GOOGLE_APPLICATION_CREDENTIALS",
                ],
            ),
        )
        super().__init__(config, authenticator=authenticator, **kwargs)
        self._prowler_config = config
        self._parser = ProwlerParser()

    def build_command(self, context: AdapterExecutionContext) -> List[str]:
        command = [
            self._config.binary_path,
            self._prowler_config.provider,
            "-M",
            self._prowler_config.output_format,
        ]
        if self._prowler_config.region:
            command.extend(["--region", self._prowler_config.region])
        for check in self._prowler_config.checks:
            command.extend(["--check", check])
        command.extend(self._config.default_args)
        command.extend(context.arguments)
        return command

    def parse(self, stdout: str, stderr: str, exit_code: int) -> Any:
        return self._parser.parse(stdout, stderr, exit_code)

    def map_status(self, result: CommandResult) -> RawResultStatus:
        if result.exit_code in {0, 1, 2, 3}:
            return RawResultStatus.SUCCEEDED
        return RawResultStatus.FAILED

    def version(self) -> str:
        try:
            result = self.run_command([self._config.binary_path, "--version"])
            text = (result.stdout or result.stderr or "").strip()
            return text.splitlines()[0][:128] if text else "prowler"
        except Exception:  # noqa: BLE001
            logger.debug("Prowler version probe failed", exc_info=True)
            return "prowler"
