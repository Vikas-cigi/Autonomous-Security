"""
Canonical security-domain enumerations for Forti-ai.

These enums are the closed vocabularies used by every adapter, policy
engine, AI module, and remediation workflow. Adapters must map raw scanner
values into these enums — never persist vendor-specific status strings as
canonical state.
"""

from __future__ import annotations

from enum import Enum


class Severity(str, Enum):
    """Industry-aligned finding severity."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"
    UNKNOWN = "unknown"


class FindingType(str, Enum):
    """Canonical finding taxonomy."""

    VULNERABILITY = "vulnerability"
    MISCONFIGURATION = "misconfiguration"
    EXPOSURE = "exposure"
    IDENTITY_RISK = "identity_risk"
    MALWARE = "malware"
    ANOMALY = "anomaly"
    COMPLIANCE = "compliance"
    SECRET_EXPOSURE = "secret_exposure"
    SUPPLY_CHAIN = "supply_chain"
    OTHER = "other"


class FindingStatus(str, Enum):
    """Lifecycle state of a security finding."""

    NEW = "new"
    TRIAGED = "triaged"
    IN_REVIEW = "in_review"
    APPROVED_FOR_REMEDIATION = "approved_for_remediation"
    REMEDIATING = "remediating"
    VERIFYING = "verifying"
    RESOLVED = "resolved"
    ACCEPTED_RISK = "accepted_risk"
    FALSE_POSITIVE = "false_positive"
    SUPPRESSED = "suppressed"
    REOPENED = "reopened"


class SourceTool(str, Enum):
    """Normalized provenance of a finding or evidence artifact."""

    NESSUS = "nessus"
    QUALYS = "qualys"
    RAPID7 = "rapid7"
    CROWDSTRIKE = "crowdstrike"
    WIZ = "wiz"
    PRISMA = "prisma"
    AWS_SECURITY_HUB = "aws_security_hub"
    AZURE_DEFENDER = "azure_defender"
    GCP_SCC = "gcp_scc"
    BURP = "burp"
    ZAP = "zap"
    NMAP = "nmap"
    NUCLEI = "nuclei"
    PROWLER = "prowler"
    CHECKOV = "checkov"
    TRIVY = "trivy"
    GRYPE = "grype"
    CUSTOM_SCANNER = "custom_scanner"
    MANUAL = "manual"
    AI_ANALYST = "ai_analyst"
    OTHER = "other"


class BusinessImpact(str, Enum):
    """Business impact classification for prioritization."""

    CATASTROPHIC = "catastrophic"
    MAJOR = "major"
    MODERATE = "moderate"
    MINOR = "minor"
    NEGLIGIBLE = "negligible"
    UNKNOWN = "unknown"


class Exploitability(str, Enum):
    """How readily the finding can be exploited."""

    ACTIVE_EXPLOIT = "active_exploit"
    WEAPONIZED = "weaponized"
    POC_AVAILABLE = "poc_available"
    THEORETICAL = "theoretical"
    NONE = "none"
    UNKNOWN = "unknown"


class EvidenceValidationStatus(str, Enum):
    """Validation state of supporting evidence."""

    UNVALIDATED = "unvalidated"
    VALIDATED = "validated"
    PARTIALLY_VALIDATED = "partially_validated"
    REJECTED = "rejected"
    EXPIRED = "expired"
    TAMPER_SUSPECTED = "tamper_suspected"


class EvidenceSource(str, Enum):
    """Origin class of an evidence artifact."""

    SCANNER = "scanner"
    AGENT = "agent"
    LOG = "log"
    PACKET_CAPTURE = "packet_capture"
    SCREENSHOT = "screenshot"
    CONFIG_SNAPSHOT = "config_snapshot"
    API_RESPONSE = "api_response"
    HUMAN_ATTESTATION = "human_attestation"
    SIMULATION = "simulation"
    OTHER = "other"


class DecisionAction(str, Enum):
    """Canonical security decision outcomes."""

    REMEDIATE = "remediate"
    MITIGATE = "mitigate"
    MONITOR = "monitor"
    ACCEPT_RISK = "accept_risk"
    ESCALATE = "escalate"
    SUPPRESS = "suppress"
    INVESTIGATE = "investigate"
    DEFER = "defer"
    NO_ACTION = "no_action"


class Priority(str, Enum):
    """Operational priority for remediation work."""

    P0 = "p0"
    P1 = "p1"
    P2 = "p2"
    P3 = "p3"
    P4 = "p4"


class RecommendedAction(str, Enum):
    """Recommended next action attached to a decision."""

    APPLY_PATCH = "apply_patch"
    CHANGE_CONFIGURATION = "change_configuration"
    REVOKE_CREDENTIAL = "revoke_credential"
    ISOLATE_ASSET = "isolate_asset"
    BLOCK_NETWORK = "block_network"
    ROTATE_SECRET = "rotate_secret"
    UPDATE_POLICY = "update_policy"
    MANUAL_REVIEW = "manual_review"
    RUN_SIMULATION = "run_simulation"
    VERIFY_ONLY = "verify_only"
    OTHER = "other"


class PolicyEffect(str, Enum):
    """Effect of a matched policy rule."""

    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"
    REQUIRE_SIMULATION = "require_simulation"
    REQUIRE_VERIFICATION = "require_verification"
    RATE_LIMIT = "rate_limit"
    AUDIT = "audit"


class PolicyVerdict(str, Enum):
    """
    Authoritative outcome of a PolicyEngine evaluation.

    Distinct from ``PolicyEffect`` (rule-document effects). ``ESCALATE`` means
    the action may proceed only after human / higher-privilege approval.
    """

    ALLOW = "allow"
    DENY = "deny"
    ESCALATE = "escalate"


class ActionClass(str, Enum):
    """
    Capability class for security-platform actions.

    Used by the PolicyEngine to gate progressively riskier operations.
    """

    READ = "read"
    SUGGEST = "suggest"
    PLAN = "plan"
    SIMULATE = "simulate"
    EXECUTE_LOW = "execute_low"
    EXECUTE_HIGH = "execute_high"


class PolicyScope(str, Enum):
    """Scope at which a policy applies."""

    GLOBAL = "global"
    TENANT = "tenant"
    ENVIRONMENT = "environment"
    ASSET_GROUP = "asset_group"
    ASSET = "asset"
    FINDING_TYPE = "finding_type"


class ExecutionStatus(str, Enum):
    """Remediation execution lifecycle."""

    PENDING = "pending"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    SIMULATING = "simulating"
    SIMULATION_FAILED = "simulation_failed"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class ApprovalStatus(str, Enum):
    """Human or policy approval state."""

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    REVOKED = "revoked"


class SimulationStatus(str, Enum):
    """Dry-run / blast-radius simulation state."""

    NOT_RUN = "not_run"
    QUEUED = "queued"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"
    SKIPPED = "skipped"


class VerificationStatus(str, Enum):
    """Post-remediation verification state."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"
    SKIPPED = "skipped"


class OutcomeStatus(str, Enum):
    """Terminal outcome of a remediation workflow."""

    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"
    ACCEPTED_WITH_RISK = "accepted_with_risk"


class HashAlgorithm(str, Enum):
    """Supported content-addressing algorithms for evidence."""

    SHA256 = "sha256"
    SHA384 = "sha384"
    SHA512 = "sha512"
    BLAKE3 = "blake3"
