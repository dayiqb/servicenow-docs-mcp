"""The search tool's `product` filter: docs folder names, common abbreviations, suggestions.

Folder names are ServiceNow's own ("it-service-management"); people type "itsm", "HRSD" or
"IT Service Management". Abbreviations follow ServiceNow's naming; a feature maps to the
folder that holds it (so "cmdb" searches all of servicenow-platform, and the result says so).
Every target was checked against both releases' indexes (2026-09-24).
"""

from __future__ import annotations

import difflib
import re
from collections import Counter

ALIASES: dict[str, str] = {
    # suites
    "itsm": "it-service-management",
    "csm": "customer-service-management",
    "itom": "it-operations-management",
    "itam": "it-asset-management",
    "sam": "it-asset-management",
    "ham": "it-asset-management",
    "eam": "it-asset-management",
    "itbm": "it-business-management",
    "spm": "it-business-management",
    "ppm": "it-business-management",
    "apm": "application-portfolio-management",
    "hr": "employee-service-management",
    "hrsd": "employee-service-management",
    "wsd": "employee-service-management",
    "lsd": "employee-service-management",
    "fsm": "field-service-management",
    "grc": "governance-risk-compliance",
    "irm": "governance-risk-compliance",
    "secops": "security-management",
    "sir": "security-management",
    "vr": "security-management",
    "security-operations": "security-management",
    "esg": "environmental-social-governance",
    "fso": "financial-services-operations",
    "otsm": "operational-technology",
    "s2p": "source-to-pay-operations",
    "hls": "healthcare-life-sciences",
    "tmt": "telecom-media-technology",
    "api": "api-reference",
    "apis": "api-reference",
    # features, mapped to the folder that holds them
    "cmdb": "servicenow-platform",
    "csdm": "servicenow-platform",
    "service-catalog": "servicenow-platform",
    "knowledge-management": "servicenow-platform",
    "mid-server": "servicenow-platform",
    "now-platform": "servicenow-platform",  # the folder of that name is 5 landing pages
    "service-portal": "platform-user-interface",
    "sp": "platform-user-interface",
    "ui-builder": "application-development",
    "uib": "application-development",
    "app-engine": "application-development",
    "atf": "application-development",
    "flow-designer": "build-workflows",
    "workflow-studio": "build-workflows",
    "integration-hub": "integrate-applications",
    "integrationhub": "integrate-applications",
    "virtual-agent": "conversational-interfaces",
    "va": "conversational-interfaces",
    "now-assist": "intelligent-experiences",
    "performance-analytics": "now-intelligence",
    "pa": "now-intelligence",
    "discovery": "it-operations-management",
    "event-management": "it-operations-management",
    "service-mapping": "it-operations-management",
}


# Real folders whose name people use for a bigger one: "now-platform" holds 5 landing pages.
_REDIRECTED = frozenset({"now-platform"})


def normalize(value: str) -> str:
    """'IT Service Management' / 'it_service_management/' -> 'it-service-management'."""
    return re.sub(r"[\s_]+", "-", value.strip().strip("/").lower())


def resolve(value: str, known: list[str]) -> tuple[str, str]:
    """(folder, how) for a `product` value: how is "exact", "alias", "alias-absent" (an
    abbreviation whose folder this release doesn't have) or "unknown" (folder "")."""
    wanted = normalize(value)
    if wanted in known and wanted not in _REDIRECTED:
        return wanted, "exact"
    if wanted in ALIASES:
        folder = ALIASES[wanted]
        return folder, "alias" if folder in known else "alias-absent"
    return "", "unknown"


def suggestions(value: str, known: list[str], paths, n: int = 3) -> list[str]:
    """Folders a mistyped or unknown `product` value probably meant, best first: a sub-area
    of that name ("incident management"), a close abbreviation ("itsn"), sub-areas whose name
    contains the words, then close spellings of folder names."""
    wanted = normalize(value)
    words = [w for w in wanted.split("-") if w]
    out: list[str] = []

    def add(folder: str) -> None:
        if folder in known and folder not in out:
            out.append(folder)

    sub: Counter = Counter()
    for fp in paths:
        parts = fp.split("/")
        if len(parts) >= 4 and parts[0] == "markdown":
            sub[(parts[1], parts[2])] += 1
    for (top, area), _ in sorted(sub.items(), key=lambda kv: (-kv[1], kv[0])):
        if area == wanted:
            add(top)
    if len(words) == 1:
        for key in difflib.get_close_matches(wanted, list(ALIASES), n=2, cutoff=0.75):
            add(ALIASES[key])
    containing: Counter = Counter()
    for (top, area), pages in sub.items():
        parts = area.split("-")
        if words and any(parts[i : i + len(words)] == words for i in range(len(parts))):
            containing[top] += pages
    for top, _ in sorted(containing.items(), key=lambda kv: (-kv[1], kv[0]))[:n]:
        add(top)
    for folder in difflib.get_close_matches(wanted, known, n=n, cutoff=0.6):
        add(folder)
    return out[:n]
