"""get_travel_time for tool-use mode: the router's own FIFO arrival function (the one the grader replays)."""

from __future__ import annotations

import re

from llmuni.router import TravelMatrix
from llmuni.tasks.schema import Task
from llmuni.travel import hhmm

CLOCK = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*$")


class TravelTool:
    def __init__(self, task: Task, matrix: TravelMatrix, max_calls: int) -> None:
        self.matrix, self.max_calls, self.calls = matrix, max_calls, 0
        self.ids = {"start": task.start.place_id}
        if task.end:
            self.ids["end"] = task.end.place_id
        for stores in task.candidates.values():
            self.ids |= {c.poi_id: c.poi_id for c in stores}

    def __call__(self, args: dict) -> dict:
        self.calls += 1
        if self.calls > self.max_calls:
            return {"error": f"the limit of {self.max_calls} calls is reached; give your final answer now"}
        origin, destination = self.ids.get(str(args.get("from_id"))), self.ids.get(str(args.get("to_id")))
        if origin is None or destination is None:
            return {"error": "unknown id: use 'start', 'end' or a listed store id"}
        m = CLOCK.match(str(args.get("depart_time", "")))
        if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
            return {"error": "depart_time must be HH:MM on a 24-hour clock"}
        depart = 60 * int(m.group(1)) + int(m.group(2))
        arrive = self.matrix.arrival(self.matrix.index(origin), self.matrix.index(destination), depart)
        if arrive is None:
            return {"error": "no connection between these places that leaves then"}
        return {"from_id": args["from_id"], "to_id": args["to_id"], "depart_time": hhmm(depart),
                "arrive_time": hhmm(arrive), "travel_minutes": arrive - depart}
