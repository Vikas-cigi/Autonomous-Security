"""Placeholder feed provider implementations (no external I/O)."""

from __future__ import annotations

from threat_intelligence.domain.enums import ThreatFeedProviderId
from threat_intelligence.providers.base import PlaceholderThreatFeedProvider


class NVDProvider(PlaceholderThreatFeedProvider):
    def __init__(self) -> None:
        super().__init__(ThreatFeedProviderId.NVD)


class CisaKevProvider(PlaceholderThreatFeedProvider):
    def __init__(self) -> None:
        super().__init__(ThreatFeedProviderId.CISA_KEV)


class MitreAttackProvider(PlaceholderThreatFeedProvider):
    def __init__(self) -> None:
        super().__init__(ThreatFeedProviderId.MITRE_ATTACK)


class MispProvider(PlaceholderThreatFeedProvider):
    def __init__(self) -> None:
        super().__init__(ThreatFeedProviderId.MISP)


class OpenCTIProvider(PlaceholderThreatFeedProvider):
    def __init__(self) -> None:
        super().__init__(ThreatFeedProviderId.OPENCTI)


class VirusTotalProvider(PlaceholderThreatFeedProvider):
    def __init__(self) -> None:
        super().__init__(ThreatFeedProviderId.VIRUSTOTAL)


class AlienVaultOTXProvider(PlaceholderThreatFeedProvider):
    def __init__(self) -> None:
        super().__init__(ThreatFeedProviderId.ALIENVAULT_OTX)


class RecordedFutureProvider(PlaceholderThreatFeedProvider):
    def __init__(self) -> None:
        super().__init__(ThreatFeedProviderId.RECORDED_FUTURE)


def default_placeholder_providers() -> list[PlaceholderThreatFeedProvider]:
    """All known future connectors as placeholders."""

    return [
        NVDProvider(),
        CisaKevProvider(),
        MitreAttackProvider(),
        MispProvider(),
        OpenCTIProvider(),
        VirusTotalProvider(),
        AlienVaultOTXProvider(),
        RecordedFutureProvider(),
    ]
