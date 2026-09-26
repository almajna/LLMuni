"""Messages for the three evaluation modes:

- closed_book: the task prompt only; the model must name real stores from its own knowledge;
- open_book: plus the listed candidate stores (ids, addresses, coordinates, opening hours), no travel times;
- tool_use: open_book plus a get_travel_time tool backed by the router.
"""

from __future__ import annotations

from llmuni.tasks.prompts import NOUNS
from llmuni.tasks.schema import Task

SYSTEM = """You plan days of errands in San Francisco for people without a car. They travel by Muni \
(buses, Muni Metro, cable cars), BART, and on foot.

Choose one specific store for each errand and the order to visit them so the person finishes everything as \
early as possible. Respect store opening hours, the time each errand takes, any deadlines, and when they must \
reach their final destination. If the errands cannot all be done under those constraints, say so.

Reply with one JSON object and nothing else:
{"feasible": true, "stops": [{"category": "<errand category>", "store_name": "<name>", "address": "<street \
address>", "poi_id": "<the store's id if ids were given, else null>"}], "reason": null}

- One stop per errand, in visiting order. Use exactly these category names: CATEGORIES.
- Give each store's name and its street address in San Francisco.
- If it is impossible, reply {"feasible": false, "stops": [], "reason": "<why>"}."""

TOOL_SPEC = {
    "type": "function",
    "function": {
        "name": "get_travel_time",
        "description": "Door-to-door travel time by Muni, BART and walking on the task's day, "
        "leaving from_id at depart_time (waiting for connections is included).",
        "parameters": {
            "type": "object",
            "properties": {
                "from_id": {"type": "string", "description": "'start', 'end', or a store id from the list"},
                "to_id": {"type": "string", "description": "'start', 'end', or a store id from the list"},
                "depart_time": {"type": "string", "description": "HH:MM, 24-hour clock"},
            },
            "required": ["from_id", "to_id", "depart_time"],
        },
    },
}


def system_prompt(task: Task) -> str:
    categories = ", ".join(f'"{e.category}" ({e.brand or NOUNS[e.category]})' for e in task.errands)
    return SYSTEM.replace("CATEGORIES", categories)


def user_prompt(task: Task, mode: str, max_tool_calls: int) -> str:
    if mode == "closed_book":
        return task.prompt
    lines = [task.prompt, "", "Candidate stores (opening hours in OpenStreetMap syntax; travel times are not given):"]
    for errand in task.errands:
        lines.append(f"{errand.category}:")
        for c in task.candidates[errand.category]:
            address = c.address or "address unknown"
            lines.append(f"- id {c.poi_id}: {c.name}, {address} ({c.lat:.5f}, {c.lon:.5f}); hours: {c.opening_hours}")
    if mode == "tool_use":
        lines += ["", f"You can call get_travel_time up to {max_tool_calls} times. Use 'start' for "
                  f"{task.start.label}" + (f", 'end' for {task.end.label}" if task.end else "") + ", or a store id."]
    return "\n".join(lines)


def messages(task: Task, mode: str, max_tool_calls: int) -> list[dict]:
    return [
        {"role": "system", "content": system_prompt(task)},
        {"role": "user", "content": user_prompt(task, mode, max_tool_calls)},
    ]


def repair_message(error: str) -> dict:
    return {"role": "user", "content": f"Your reply could not be used ({error}). Reply again with only the JSON "
            "object described in the instructions."}
