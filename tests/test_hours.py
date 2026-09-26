from datetime import datetime

from llmuni import hours
from llmuni.hours import hours_status, open_intervals, parse_hours, weekly_summary

MON = datetime(2026, 10, 5)  # reference week starts Monday 2026-10-05


def test_missing_and_unparseable_hours_are_none():
    assert parse_hours(None) is None
    assert parse_hours("   ") is None
    assert parse_hours(float("nan")) is None
    assert parse_hours("Mo-Fr 9-5pm") is None


def test_intervals_are_naive_local_times():
    oh = parse_hours("Mo-Fr 09:00-18:00; Sa 10:00-17:00")
    assert open_intervals(oh, MON, datetime(2026, 10, 6)) == [(datetime(2026, 10, 5, 9), datetime(2026, 10, 5, 18))]


def test_weekly_summary_counts_hours_and_days():
    week = weekly_summary(parse_hours("Mo-Fr 09:00-18:00; Sa 10:00-17:00"), MON)
    assert week == {"open_hours": 52.0, "unknown_hours": 0.0, "open_days": 6}


def test_overnight_hours_spill_past_midnight():
    oh = parse_hours("Mo-Su 06:00-02:00")
    assert open_intervals(oh, MON, datetime(2026, 10, 6, 6)) == [
        (datetime(2026, 10, 5, 0), datetime(2026, 10, 5, 2)),  # Sunday's evening shift
        (datetime(2026, 10, 5, 6), datetime(2026, 10, 6, 2)),
    ]


def test_closed_and_always_open_extremes():
    assert weekly_summary(parse_hours("closed"), MON)["open_hours"] == 0.0
    assert weekly_summary(parse_hours("24/7"), MON) == {"open_hours": 168.0, "unknown_hours": 0.0, "open_days": 7}


def test_sunset_depends_on_location():
    oh = parse_hours("Mo-Su 08:00-sunset", coords=(37.77, -122.42))
    ((start, end),) = open_intervals(oh, MON, datetime(2026, 10, 6))
    assert start == datetime(2026, 10, 5, 8)
    assert datetime(2026, 10, 5, 18, 30) <= end <= datetime(2026, 10, 5, 19, 0)


def test_unknown_periods_are_reported_separately_from_open_time():
    week = weekly_summary(parse_hours("Mo-Fr 09:00-17:00; Sa 10:00-14:00 unknown"), MON)
    assert week["open_hours"] == 40.0
    assert week["unknown_hours"] == 4.0


def test_hours_status_classes():
    def status(expr):
        oh = parse_hours(expr)
        week = weekly_summary(oh, MON) if oh else {"open_hours": 0.0, "unknown_hours": 0.0, "open_days": 0}
        return hours_status(expr, oh, week)

    assert status(None) == hours.MISSING
    assert status("Mo-Fr 9-5pm") == hours.UNPARSEABLE
    assert status("Mo-Fr 09:00-17:00; Sa 10:00-14:00 unknown") == hours.UNKNOWN
    assert status("closed") == hours.CLOSED_ALL_WEEK
    assert status("Mo-Fr 09:00-17:00") == hours.VALID
    assert hours.VERIFIABLE == {hours.VALID, hours.CLOSED_ALL_WEEK}
