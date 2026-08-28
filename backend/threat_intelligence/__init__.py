"""
Enterprise Threat Intelligence Service.

Enriches SecurityFindingObjects (by finding_id) with CVE, MITRE, exploit,
IOC, actor, malware, and campaign intelligence. Sits between the Evidence
Repository and the (future) Risk Engine.

Does not modify existing platform modules. No REST APIs. No live external
feed integrations — provider interfaces + placeholders only.
"""

from threat_intelligence.di.container import ThreatIntelligenceContainer
from threat_intelligence.domain.ioc import IndicatorOfCompromise
from threat_intelligence.domain.models import (
    CVERecord,
    Campaign,
    ExploitInformation,
    MITRETechnique,
    MalwareFamily,
    ThreatActor,
    ThreatFeedMetadata,
    ThreatIntelligence,
)
from threat_intelligence.interfaces.ioc_repository import IOCRepository
from threat_intelligence.interfaces.threat_feed_repository import ThreatFeedRepository
from threat_intelligence.interfaces.threat_intel_repository import ThreatIntelRepository
from threat_intelligence.providers.base import (
    ThreatFeedProvider,
    ThreatFeedProviderRegistry,
)
from threat_intelligence.services.threat_intelligence_service import (
    ThreatIntelligenceService,
)

__all__ = [
    "CVERecord",
    "Campaign",
    "ExploitInformation",
    "IOCRepository",
    "IndicatorOfCompromise",
    "MITRETechnique",
    "MalwareFamily",
    "ThreatActor",
    "ThreatFeedMetadata",
    "ThreatFeedProvider",
    "ThreatFeedProviderRegistry",
    "ThreatFeedRepository",
    "ThreatIntelRepository",
    "ThreatIntelligence",
    "ThreatIntelligenceContainer",
    "ThreatIntelligenceService",
]

__version__ = "1.0.0"
