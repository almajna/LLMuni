"""OSM `opening_hours` evaluation in San Francisco local time.

LLMuni works in naive local datetimes (America/Los_Angeles). The Rust-backed
`opening_hours` parser reads naive inputs as local time and returns aware values,
which are converted back to naive here. The UNKNOWN state counts as closed.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from opening_hours import OpeningHours, State

TZ = ZoneInfo("America/Los_Angeles")
SF_CENTER = (37.7749, -122.4194)


def parse_hours(expr: object, coords: tuple[float, float] = SF_CENTER) -> OpeningHours | None:
    """Parse an OSM opening_hours expression; None if it is missing or unparseable."""
    if not isinstance(expr, str) or not expr.strip():
        return None
    try:
        return OpeningHours(expr.strip(), timezone=TZ, country="US", coords=coords)
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException:  # the Rust parser can also raise pyo3's PanicException, a BaseException
        return None


def open_intervals(oh: OpeningHours, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
    """Maximal open intervals within [start, end)."""
    out: list[tuple[datetime, datetime]] = []
    for a, b, state in _runs(oh, start, end):
        if state != State.OPEN:
            continue
        if out and out[-1][1] == a:  # runs split only by a comment change
            out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return out


def weekly_summary(oh: OpeningHours, week_start: datetime) -> dict[str, float | int]:
    """Open hours, unknown hours, and days with any opening in the 7 days from week_start."""
    week_end = week_start + timedelta(days=7)
    open_s = unknown_s = 0.0
    open_days: set[date] = set()
    for a, b, state in _runs(oh, week_start, week_end):
        if state == State.UNKNOWN:
            unknown_s += (b - a).total_seconds()
        elif state == State.OPEN:
            open_s += (b - a).total_seconds()
            day, last = a.date(), (b - timedelta(microseconds=1)).date()
            while day <= last:
                open_days.add(day)
                day += timedelta(days=1)
    return {"open_hours": open_s / 3600, "unknown_hours": unknown_s / 3600, "open_days": len(open_days)}


def _runs(oh: OpeningHours, start: datetime, end: datetime) -> Iterator[tuple[datetime, datetime, State]]:
    """(start, end, state) runs clipped to [start, end), as naive local datetimes."""
    for a, b, state, _comment in oh.intervals(start, end):
        a = start if a is None else max(_naive(a), start)
        b = end if b is None else min(_naive(b), end)
        if a < b:
            yield a, b, state


def _naive(dt: datetime) -> datetime:
    return dt.astimezone(TZ).replace(tzinfo=None) if dt.tzinfo else dt
