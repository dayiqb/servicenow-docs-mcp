"""The UserPromptSubmit hook: nudge Claude to check the docs for ServiceNow questions."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "hooks" / "servicenow_prompt.py"


def run_hook(stdin: str, **env: str) -> subprocess.CompletedProcess:
    import os

    full_env = {**os.environ, **env}
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=stdin,
        capture_output=True,
        text=True,
        env=full_env,
        timeout=20,
        check=False,
    )


def context_for(prompt: str, **env: str) -> str | None:
    out = run_hook(json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": prompt}), **env)
    assert out.returncode == 0, out.stderr
    if not out.stdout.strip():
        return None
    data = json.loads(out.stdout)  # the whole stdout must be one JSON object
    hso = data["hookSpecificOutput"]
    assert hso["hookEventName"] == "UserPromptSubmit"
    return hso["additionalContext"]


@pytest.mark.parametrize(
    "prompt",
    [
        "How do I make a field mandatory in ServiceNow?",
        "what's the difference between a business rule and a client script",
        "GlideRecord query with an encoded query, how?",
        "Our CMDB identification rules keep creating duplicates",
        "How are ITSM incident priorities calculated?",
        "can a UI policy hide a related list",
        "move an update set between instances",
        "Flow Designer: send an approval to the manager",
        "service now scripted REST API auth",
        "Find the sys_id of the current user in a script include",
        "Our MID Server keeps going down after the upgrade",
        "current.setAbortAction(true) isn't stopping the insert",
        "transform map coalesce on the email field",
        "How do I write an ATF test for a catalog item?",
        "use g_scratchpad in a display business rule",
        "gs.getProperty returns null in a scoped app",
        "What changed in the Brazil release for Now Assist?",
        "Virtual Agent topic for an incident",
    ],
)
def test_servicenow_questions_get_the_nudge(prompt: str) -> None:
    ctx = context_for(prompt)
    assert ctx is not None, prompt
    assert "snow_docs_search" in ctx and "cit" in ctx


@pytest.mark.parametrize(
    "prompt",
    [
        "fix the failing test in test_setup.py",
        "will it snow in Oslo tomorrow?",
        "summarize this incident report from our postmortem",
        "write a python function to parse dates",
        "/plugin list",
        "",
        # everyday developer/IT wording that shares words with ServiceNow
        "What SPM tool should our PMO use?",
        "why is sys_platform 'darwin' on my mac",
        "trace sys_enter_openat with bpftrace",
        "the UPDATE sets the flag on every row, why?",
        "implement a business rules engine in Drools",
        "Glide image loading is slow in my Android RecyclerView",
        "Glide.with(context).load(url) crashes",
        "OAuth application scopes for the GitHub API",
        "ACL rules on the S3 bucket deny my upload",
        "add catalog items to our Shopify store",
        "client scripts in Dynamics 365 vs server plugins",
        "Webpack script includes order in index.html",
        "is this now platform-independent?",
        "the now experience of using vim is great",
        "Workflow Studio in Power Automate",
        "What is ITSM?",
        "rename Code.gs.bak to Code.gs in clasp",
        "EC2 instance incident postmortem template",
        "our SLA for incidents is 4 hours",
        "a mid server tier in our 3-tier architecture",
    ],
)
def test_other_prompts_are_left_alone(prompt: str) -> None:
    assert context_for(prompt) is None, prompt


# What the app puts in a prompt itself: a command the user ran and its output, a note from
# another session, a reminder. None of it is a question the user typed.
_RAN = (
    "<bash-input>claude plugin install servicenow-docs@servicenow-docs-mcp</bash-input>"
    "<bash-stdout>Successfully installed plugin: servicenow-docs@servicenow-docs-mcp</bash-stdout>"
    "<bash-stderr></bash-stderr>"
)
_RELOADED = (
    "<local-command-caveat>The command below was run directly in Claude Code.</local-command-caveat>\n"
    "<command-name>/reload-plugins</command-name>\n"
    "<command-message>reload-plugins</command-message>\n"
    "<local-command-stdout>Reloaded: 34 plugins, ServiceNow Docs among them</local-command-stdout>\n"
)
_NOTE = (
    '<system-reminder>\nThe session "ServiceNow SDK panel" finished a turn.\n</system-reminder>\n'
    "<side-sessions-event>None of the sessions is working now.</side-sessions-event>"
)
_MESSAGE = (
    '<cross-session-message from="local_1" from-name="ServiceNow SDK panel">\n'
    "The ServiceNow SDK panel setting is on as installed.\n</cross-session-message>"
)


@pytest.mark.parametrize(
    "prompt",
    [
        _RAN,
        _RELOADED,
        _NOTE,
        _MESSAGE,
        "<task-notification>The ServiceNow index build finished.</task-notification>",
        _RELOADED + "wait, did the tests pass?",
    ],
)
def test_what_the_app_wrote_into_a_prompt_is_not_a_question(prompt: str) -> None:
    assert context_for(prompt) is None, prompt


def test_a_question_typed_after_a_command_still_gets_the_nudge() -> None:
    assert context_for(_RELOADED + "How do I make a field mandatory on the incident form?") is None
    assert context_for(_RELOADED + "How do I make a field mandatory in ServiceNow?") is not None


def test_the_nudge_leaves_the_release_to_the_setting() -> None:
    """The release is a setting: telling Claude that Australia is the default overrides it."""
    ctx = context_for("How do I make a field mandatory in ServiceNow?")
    assert ctx is not None
    assert "Australia is the default" not in ctx
    assert "leave `release` out" in ctx


def test_off_switch() -> None:
    assert context_for("How do I use GlideRecord?", SNOW_DOCS_PROMPT_HOOK="off") is None


@pytest.mark.parametrize("stdin", ["", "not json", "[1, 2]", '{"prompt": 5}'])
def test_bad_input_never_blocks_the_prompt(stdin: str) -> None:
    out = run_hook(stdin)
    assert out.returncode == 0 and out.stdout.strip() == ""
