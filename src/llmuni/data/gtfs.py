"""GTFS feed summaries for the manifest: version, validity, and service in the reference week."""

from __future__ import annotations

import zipfile
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def summarize_feed(path: Path, week_start: date) -> dict:
    with zipfile.ZipFile(path) as z:
        agency, feed_info = _read(z, "agency.txt"), _read(z, "feed_info.txt")
        calendar, calendar_dates = _read(z, "calendar.txt"), _read(z, "calendar_dates.txt")
        routes, stops, trips = _read(z, "routes.txt"), _read(z, "stops.txt"), _read(z, "trips.txt")

    dates: list[str] = []
    if calendar is not None and len(calendar):
        dates += [calendar["start_date"].min(), calendar["end_date"].max()]
    if calendar_dates is not None and len(calendar_dates):
        dates += [calendar_dates["date"].min(), calendar_dates["date"].max()]

    trips_per_service = trips["service_id"].value_counts()
    week = {}
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        ids = active_service_ids(calendar, calendar_dates, day)
        n_trips = int(trips_per_service.reindex(sorted(ids)).fillna(0).sum())
        week[day.isoformat()] = {"service_ids": len(ids), "trips": n_trips}

    info = feed_info.iloc[0].to_dict() if feed_info is not None and len(feed_info) else {}
    keys = ("feed_publisher_name", "feed_version", "feed_start_date", "feed_end_date")
    return {
        "agencies": sorted(agency["agency_name"].unique()) if agency is not None else [],
        "feed_info": {k: info[k] for k in keys if info.get(k)},
        "service_date_range": [_iso(min(dates)), _iso(max(dates))] if dates else None,
        "n_routes": len(routes),
        "n_stops": len(stops),
        "n_trips": len(trips),
        "reference_week_service": week,
    }


def active_service_ids(calendar: pd.DataFrame | None, calendar_dates: pd.DataFrame | None, day: date) -> set[str]:
    """service_ids running on day: calendar.txt ranges, then calendar_dates.txt additions/removals."""
    ymd = day.strftime("%Y%m%d")
    active: set[str] = set()
    if calendar is not None and len(calendar):
        runs = (calendar["start_date"] <= ymd) & (calendar["end_date"] >= ymd) & (calendar[WEEKDAYS[day.weekday()]] == "1")
        active |= set(calendar.loc[runs, "service_id"])
    if calendar_dates is not None and len(calendar_dates):
        today = calendar_dates[calendar_dates["date"] == ymd]
        active |= set(today.loc[today["exception_type"] == "1", "service_id"])
        active -= set(today.loc[today["exception_type"] == "2", "service_id"])
    return active


def _read(z: zipfile.ZipFile, name: str) -> pd.DataFrame | None:
    members = {Path(n).name: n for n in z.namelist()}  # some feeds nest their files in a folder
    if name not in members:
        return None
    with z.open(members[name]) as f:
        df = pd.read_csv(f, dtype=str, keep_default_na=False, skipinitialspace=True, encoding="utf-8-sig")
    return df.apply(lambda col: col.str.strip())


def _iso(ymd: str) -> str:
    return f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}"
