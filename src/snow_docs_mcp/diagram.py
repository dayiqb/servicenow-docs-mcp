"""A process from the docs as a diagram: checking that it holds together, and its text form.

The panel draws the steps, links and lanes as they are; clients without a panel get the same
diagram as Mermaid text.
"""

from __future__ import annotations

import re

from snow_docs_mcp import config, setup, store
from snow_docs_mcp.results import DiagramLane, DiagramLink, DiagramStep
from snow_docs_mcp.search import parse_id

STEPS = (2, 40)  # the fewest and the most steps a diagram can have
_STEP_ID = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


def problems(
    steps: list[DiagramStep], links: list[DiagramLink], lanes: list[DiagramLane]
) -> list[str]:
    """Why the diagram cannot be shown, one line per problem (none = it holds together): ids
    of steps and of lanes are unique and well-formed, every step and lane has a label, links
    join existing steps, and every source id names a page the docs have."""
    problems: list[str] = []
    low, high = STEPS
    if not low <= len(steps) <= high:
        problems.append(f"a diagram has {low} to {high} steps, this one has {len(steps)}")
    seen: set[str] = set()
    for step in steps:
        if not _STEP_ID.match(step.id):
            problems.append(f"step id '{step.id}' must be 1-40 letters, digits, _ or -")
        if step.id in seen:
            problems.append(f"the id '{step.id}' is used by more than one step")
        seen.add(step.id)
        if not step.label.strip():
            problems.append(f"step '{step.id}' has no label")
    lane_ids: set[str] = set()
    for lane in lanes:
        if not _STEP_ID.match(lane.id):
            problems.append(f"lane id '{lane.id}' must be 1-40 letters, digits, _ or -")
        if lane.id in lane_ids:
            problems.append(f"the id '{lane.id}' is used by more than one lane")
        lane_ids.add(lane.id)
        if not lane.label.strip():
            problems.append(f"lane '{lane.id}' has no label")
    for step in steps:
        if step.lane and step.lane not in lane_ids:
            problems.append(
                f"step '{step.id}' is in lane '{step.lane}', which is not one of the lanes"
            )
        if lanes and not step.lane:
            problems.append(f"step '{step.id}' has no lane")
    for link in links:
        for end in (link.source, link.target):
            if end not in seen:
                problems.append(f"a link names the step '{end}', which does not exist")
    for step in steps:
        if not step.source_id:
            continue
        parsed = parse_id(step.source_id)
        rel = config.normalize_release(parsed[0]) if parsed else None
        db = setup.active_index(rel) if rel else None
        if parsed is None or rel is None:
            problems.append(f"step '{step.id}' cites '{step.source_id}', which is not an id")
        elif db is not None and store.get_document(db, parsed[1]) is None:
            problems.append(
                f"step '{step.id}' cites the page '{parsed[1]}', which the {rel} docs do not have"
            )
    return list(dict.fromkeys(problems))


def mermaid(
    title: str, lanes: list[DiagramLane], steps: list[DiagramStep], links: list[DiagramLink]
) -> str:
    """The diagram as Mermaid text. Steps are named s1, s2, ... and lanes lane1, ...: an id the
    caller picked (`end`, `a--`, a lane and a step with the same id) can then never be read as
    Mermaid syntax."""

    def text(value: str) -> str:
        return value.replace('"', "'").replace("\n", " ")

    name = {step.id: f"s{n}" for n, step in enumerate(steps, 1)}

    def node(step: DiagramStep) -> str:
        label = text(step.label)
        if step.kind in ("start", "end"):
            return f'{name[step.id]}(["{label}"])'
        if step.kind == "decision":
            return f'{name[step.id]}{{"{label}"}}'
        return f'{name[step.id]}["{label}"]'

    lines = ["flowchart TD"]
    if lanes:
        for n, lane in enumerate(lanes, 1):
            lines.append(f'  subgraph lane{n}["{text(lane.label)}"]')
            lines += [f"    {node(s)}" for s in steps if s.lane == lane.id]
            lines.append("  end")
        lines += [f"  {node(s)}" for s in steps if not s.lane]
    else:
        lines += [f"  {node(s)}" for s in steps]
    for link in links:
        arrow = f'-- "{text(link.label)}" -->' if link.label else "-->"
        lines.append(f"  {name[link.source]} {arrow} {name[link.target]}")
    return "\n".join(lines)
