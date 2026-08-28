"""Sample scanner payloads for simulate mode (no binary required)."""

from __future__ import annotations

from typing import Any, Dict, List


def sample_nuclei_payload(target: str) -> List[Dict[str, Any]]:
    """Deterministic Nuclei-shaped findings for local demos and tests."""

    return [
        {
            "template-id": "cve-2023-38408",
            "info": {
                "name": "OpenSSH Remote Code Execution (CVE-2023-38408)",
                "severity": "critical",
                "description": (
                    "Simulated Nuclei match: OpenSSH is vulnerable to remote "
                    "code execution via crafted forwarding."
                ),
                "tags": ["cve", "ssh", "rce"],
                "classification": {
                    "cve-id": ["CVE-2023-38408"],
                    "cwe-id": ["CWE-787"],
                    "cvss-score": 9.8,
                },
            },
            "host": target,
            "matched-at": target,
            "type": "http",
        },
        {
            "template-id": "http-missing-security-headers",
            "info": {
                "name": "Missing Security Headers",
                "severity": "medium",
                "description": (
                    "Simulated Nuclei match: response is missing recommended "
                    "security headers (CSP, HSTS)."
                ),
                "tags": ["misconfig", "headers"],
                "classification": {"cvss-score": 5.3},
            },
            "host": target,
            "matched-at": target,
            "type": "http",
        },
        {
            "template-id": "exposed-panel-detect",
            "info": {
                "name": "Exposed Admin Panel",
                "severity": "high",
                "description": (
                    "Simulated Nuclei match: administrative interface appears "
                    "reachable without network restriction."
                ),
                "tags": ["exposure", "panel"],
                "classification": {"cvss-score": 7.5},
            },
            "host": target,
            "matched-at": target,
            "type": "http",
        },
    ]


def sample_payload_for_tool(tool_name: str, target: str) -> Any:
    """Return a normalizer-compatible sample payload for ``tool_name``."""

    key = tool_name.strip().lower()
    if key == "nuclei":
        return sample_nuclei_payload(target)
    if key == "trivy":
        return {
            "Results": [
                {
                    "Target": target,
                    "Vulnerabilities": [
                        {
                            "VulnerabilityID": "CVE-2024-12345",
                            "PkgName": "openssl",
                            "InstalledVersion": "1.1.1",
                            "FixedVersion": "3.0.0",
                            "Severity": "HIGH",
                            "Title": "OpenSSL buffer overflow (simulated)",
                            "Description": "Simulated Trivy finding for wiring demos.",
                        }
                    ],
                }
            ]
        }
    if key == "grype":
        return {
            "matches": [
                {
                    "vulnerability": {
                        "id": "CVE-2024-21626",
                        "severity": "Critical",
                        "description": "Simulated Grype finding: runc container breakout.",
                        "fix": {"versions": ["1.1.12"], "state": "fixed"},
                        "cvss": [{"metrics": {"baseScore": 9.8}, "version": "3.1"}],
                    },
                    "artifact": {
                        "name": "runc",
                        "version": "1.1.5",
                        "type": "deb",
                    },
                    "relatedVulnerabilities": [
                        {"id": "CVE-2024-21626", "severity": "Critical"}
                    ],
                },
                {
                    "vulnerability": {
                        "id": "CVE-2023-44487",
                        "severity": "High",
                        "description": "Simulated Grype finding: HTTP/2 rapid reset DoS.",
                        "fix": {"versions": ["1.58.0"], "state": "fixed"},
                        "cvss": [{"metrics": {"baseScore": 7.5}, "version": "3.1"}],
                    },
                    "artifact": {
                        "name": "golang.org/x/net",
                        "version": "0.12.0",
                        "type": "go-module",
                    },
                    "relatedVulnerabilities": [
                        {"id": "CVE-2023-44487", "severity": "High"}
                    ],
                },
            ]
        }
    # Fallback: nuclei-shaped so normalize still has a registered tool.
    return sample_nuclei_payload(target)
