"""UserPromptSubmit hook: for ServiceNow questions, remind Claude to check the docs first.

Reads the hook payload (JSON) on stdin. When the prompt is clearly about ServiceNow, prints
one JSON object that adds a short note to Claude's context; otherwise prints nothing. It
never blocks or alters the prompt: any problem means "stay silent, exit 0".

Standard library only, so it starts fast. Turn it off with SNOW_DOCS_PROMPT_HOOK=off.
"""

from __future__ import annotations

import json
import os
import re
import sys

# One of these is enough: they (almost) only occur in ServiceNow questions.
_STRONG = re.compile(
    r"""
    \bservice\s?now\b
    | \bglide(?:record(?:secure)?|ajax|system|aggregate|datetime|date|time|element|form
        |user|duration|schedule|email|query|filter|sysattachment|modal|dialogwindow)\b
    | \bg_(?:form|user|scratchpad|list|navigation)\b
    | \bgs\.(?:info|log|warn|error|debug|print|getuser|getuserid|getusername|getproperty
        |setproperty|addinfomessage|adderrormessage|eventqueue|hasrole|getsession
        |nowdatetime|now|daysago|beginningof\w+|endof\w+)\b
    | \bcurrent\.setabortaction\b
    | \bsys_(?:id|user\w*|properties|script\w*|ui_\w+|update_\w+|db_object|dictionary
        |choice|attachment\w*|audit\w*|journal_field|email\w*|trigger|hub_\w+|scope
        |security_acl\w*|metadata|created_on|updated_on|created_by|updated_by
        |class_name|domain|import_set\w*)\b
    | \bnow\s+assist\b | \bflow\s+designer\b | \bintegration\s?hub\b
    | \b(?-i:MID)\s+[Ss]ervers?\b
    | \brecord\s+producers?\b | \bscripted\s+rest\b | \bdata\s+lookup\s+rules?\b
    | \btransform\s+maps?\b | \bencoded\s+quer(?:y|ies)\b
    | \bautomated\s+test\s+framework\b
    | \b(?:australia|brazil|zurich|yokohama|xanadu|washington\s?dc|vancouver)\s+release\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# These also occur in everyday IT and developer talk ("business rules engine", "ACL rules
# on the bucket", "UPDATE sets"): two different ones are needed.
_WEAK = re.compile(
    r"""
    \b(?P<business_rule>business\s+rules?)\b
    | \b(?P<script_include>script\s+includes?)\b
    | \b(?P<client_script>client\s+scripts?)\b
    | \b(?P<ui_thing>ui\s+(?:polic(?:y|ies)|actions?|macros?))\b
    | \b(?P<update_set>update\s+sets?)\b
    | \b(?P<cmdb>cmdb)\b | \b(?P<itsm>itsm)\b | \b(?P<itom>itom)\b | \b(?P<hrsd>hrsd)\b
    | \b(?P<catalog_item>catalog\s+items?)\b
    | \b(?P<acl>acls?)\b
    | \b(?P<scope>(?:application\s+scopes?|scoped\s+apps?))\b
    | \b(?P<service_portal>service\s+portal)\b
    | \b(?P<workflow_studio>workflow\s+studio)\b
    | \b(?P<virtual_agent>virtual\s+agent)\b
    | \b(?P<import_set>import\s+sets?)\b
    | \b(?P<atf>(?-i:ATF))\b
    | \b(?P<identification_rule>identification\s+(?:and\s+reconciliation\s+)?rules?)\b
    | \b(?P<related_list>related\s+lists?)\b
    | \b(?P<instance>instances?)\b
    | \b(?P<incident>incidents?)\b
    | \b(?P<change_request>change\s+requests?)\b
    | \b(?P<assignment_group>assignment\s+groups?)\b
    | \b(?P<sla>slas?)\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


# Plain IT words: they count towards the two, but two of them alone ("the EC2 instance
# incident") are not enough.
_GENERIC = {"instance", "incident", "change_request", "assignment_group", "sla", "related_list"}


def looks_like_servicenow(prompt: str) -> bool:
    if _STRONG.search(prompt):
        return True
    kinds = {m.lastgroup for m in _WEAK.finditer(prompt)}
    return len(kinds) >= 2 and bool(kinds - _GENERIC)

NUDGE = (
    "This looks like a ServiceNow question. Before answering, search the official "
    "ServiceNow docs with the servicenow-docs tools: call snow_docs_search with an English "
    "query in ServiceNow's terms (translate the question if needed; answer in the user's "
    "language; pass "
    'release "brazil" if the user\'s instance runs Brazil; Australia is the default), '
    "answer only from the returned passages with [id] citations, and call snow_docs_read "
    "for the full section before giving steps. If the docs don't cover it, say so."
)


def main() -> int:
    if os.environ.get("SNOW_DOCS_PROMPT_HOOK", "").strip().lower() in ("off", "0", "false"):
        return 0
    try:
        payload = json.loads(sys.stdin.read() or "null")
    except (ValueError, UnicodeDecodeError):
        return 0
    prompt = payload.get("prompt") if isinstance(payload, dict) else None
    if not isinstance(prompt, str) or not prompt.strip() or prompt.lstrip().startswith("/"):
        return 0
    if not looks_like_servicenow(prompt):
        return 0
    out = {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": NUDGE}}
    sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001 - a hook must never block the user's prompt
        sys.exit(0)
