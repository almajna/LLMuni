from llmuni.site.export import failure_kind
from llmuni.site.routes import hop_key, plan_hops, timed_path

START, A, B, END = (-122.40, 37.78), (-122.41, 37.77), (-122.43, 37.76), (-122.45, 37.78)


def test_plan_hops_follow_the_replay_and_stop_at_the_first_failure():
    stops = [{"at": list(A), "arrive": 560, "done": 575}, {"at": list(B), "arrive": 600, "done": None}]
    hops = plan_hops(START, 540, stops, END, 640)
    assert hops == [(START, A, 540, 560), (A, B, 575, 600)]  # no done at B: the plan broke there, no hop to the end


def test_plan_hops_reach_the_end_when_every_stop_is_done():
    hops = plan_hops(START, 540, [{"at": list(A), "arrive": 560, "done": 575}], END, 610)
    assert hops[-1] == (A, END, 575, 610)


def test_timed_path_stretches_an_itinerary_onto_the_replayed_times_and_waits_at_stops():
    hops = plan_hops(START, 540, [{"at": list(A), "arrive": 560, "done": 575}], END, 610)
    legs = {hop_key("2026-10-07", START, A, 540): [
        {"mode": "WALK", "route": None, "coords": [list(START), [-122.405, 37.775]], "t0": 540.0, "t1": 545.0},
        {"mode": "BUS", "route": "14", "coords": [[-122.405, 37.775], list(A)], "t0": 548.0, "t1": 555.0},
    ]}
    path = timed_path(hops, legs, "2026-10-07")
    times = [p[2] for p in path]
    assert times == sorted(times) and path[0][2] == 540 and path[-1][2] == 610
    at_a = [p[2] for p in path if (p[0], p[1]) == A]
    assert 560 in at_a and 575 in at_a  # arrives, waits for the errand, leaves
    assert any(p[:2] == [-122.405, 37.775] for p in path)  # follows the itinerary, not a straight line


def test_failure_kinds_name_how_a_plan_ended():
    assert failure_kind({"status": "infeasible", "failure": "closed: errand 1 ..."}) == "closed"
    assert failure_kind({"status": "hallucinated", "failure": "no store"}) == "no_such_store"
    assert failure_kind({"status": "wrong_address", "failure": "x"}) == "wrong_address"
