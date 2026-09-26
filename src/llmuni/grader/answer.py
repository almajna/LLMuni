"""The answer every model must return, and its parser."""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field, ValidationError


class AnswerStop(BaseModel):
    category: str = Field(description="One of the errand categories given in the task")
    store_name: str = Field(description="The store's name")
    address: str | None = Field(default=None, description="Street address in San Francisco")
    poi_id: str | None = Field(default=None, description="The store's id, when stores with ids were provided")


class Answer(BaseModel):
    feasible: bool = Field(description="false if the errands cannot all be done under the constraints")
    stops: list[AnswerStop] = Field(default_factory=list, description="Stores to visit, in order")
    reason: str | None = Field(default=None, description="Why it is impossible (when feasible is false)")


FENCED = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def parse_answer(text: str | None) -> tuple[Answer | None, str | None, bool]:
    """(answer, error, pure): the JSON object in a reply (bare, fenced, or embedded in prose),
    validated against the schema. `pure` is True when the whole reply was just the JSON."""
    if not text or not text.strip():
        return None, "empty reply", False
    stripped = text.strip()
    if "{" not in stripped:
        return None, "no JSON object found", False
    candidates = [stripped, *FENCED.findall(stripped)]
    first, last = stripped.find("{"), stripped.rfind("}")
    if 0 <= first < last:
        candidates.append(stripped[first : last + 1])
    error = "no JSON object found"
    for raw in candidates:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            error = f"invalid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})"
            continue
        try:
            return Answer.model_validate(data), None, raw is stripped
        except ValidationError as exc:
            first_error = exc.errors()[0]
            error = f"schema: {first_error['msg']} at {'.'.join(map(str, first_error['loc']))}"
    return None, error, False
