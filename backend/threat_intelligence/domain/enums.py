"""Domain enums for the Threat Intelligence Service."""

from __future__ import annotations

from enum import Enum


class ThreatFeedProviderId(str, Enum):
    """Known feed providers (connectors implemented later)."""

    NVD = "nvd"
    CISA_KEV = "cisa_kev"
    MITRE_ATTACK = "mitre_attack"
    MISP = "misp"
    OPENCTI = "opencti"
    VIRUSTOTAL = "virustotal"
    ALIENVAULT_OTX = "alienvault_otx"
    RECORDED_FUTURE = "recorded_future"
    INTERNAL = "internal"
    MANUAL = "manual"


class IOCType(str, Enum):
    """Indicator of compromise types."""

    IPV4 = "ipv4"
    IPV6 = "ipv6"
    DOMAIN = "domain"
    URL = "url"
    FILE_HASH_MD5 = "file_hash_md5"
    FILE_HASH_SHA1 = "file_hash_sha1"
    FILE_HASH_SHA256 = "file_hash_sha256"
    EMAIL = "email"
    CVE = "cve"
    MUTEX = "mutex"
    FILENAME = "filename"
    REGISTRY_KEY = "registry_key"
    OTHER = "other"


class CVSSVersion(str, Enum):
    V2 = "2.0"
    V3_0 = "3.0"
    V3_1 = "3.1"
    V4_0 = "4.0"


class ExploitMaturity(str, Enum):
    """Exploit availability / maturity."""

    UNPROVEN = "unproven"
    PROOF_OF_CONCEPT = "proof_of_concept"
    FUNCTIONAL = "functional"
    HIGH = "high"
    NOT_DEFINED = "not_defined"
    UNKNOWN = "unknown"


class ThreatActorSophistication(str, Enum):
    NONE = "none"
    MINIMAL = "minimal"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"
    INNOVATOR = "innovator"
    STRATEGIC = "strategic"
    UNKNOWN = "unknown"


class AuditAction(str, Enum):
    INTEL_CREATED = "intel_created"
    INTEL_UPDATED = "intel_updated"
    CVE_UPSERTED = "cve_upserted"
    IOC_UPSERTED = "ioc_upserted"
    FEED_SYNC_STARTED = "feed_sync_started"
    FEED_SYNC_COMPLETED = "feed_sync_completed"
    FEED_SYNC_FAILED = "feed_sync_failed"
    FINDING_ENRICHED = "finding_enriched"
    SEARCHED = "searched"


class FeedSyncStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
