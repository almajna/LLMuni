from datetime import date

import numpy as np
import pytest

from llmuni.router import NO_TRIP, TravelMatrix, fifo_arrivals


def _matrix(transit_minutes, walk, start=540, step=5):
    minutes = np.array(transit_minutes, dtype=np.uint16).reshape(1, 1, -1)
    arrive = np.full((2, 2, minutes.shape[2]), NO_TRIP, dtype=np.uint16)
    arrive[0, 1] = fifo_arrivals(minutes, start, step)[0, 0]
    walks = np.array([[0, walk], [walk, 0]], dtype=np.uint16)
    return TravelMatrix(["a", "b"], date(2026, 10, 7), start, step, arrive, walks)


def test_waiting_for_a_later_departure_can_win():
    # leaving at 9:00 takes 30 min (arrive 9:30); leaving at 9:05 takes 10 (arrive 9:15)
    arrive = fifo_arrivals(np.array([[[30, 10, 10]]], dtype=np.uint16), start=540, step=5)
    assert arrive[0, 0].tolist() == [555, 555, 560]


def test_unreachable_departures_inherit_later_connections():
    arrive = fifo_arrivals(np.array([[[NO_TRIP, 20, NO_TRIP]]], dtype=np.uint16), start=540, step=5)
    assert arrive[0, 0].tolist() == [565, 565, NO_TRIP]


def test_arrival_is_fifo_and_never_worse_than_walking():
    tm = _matrix([25, 12, 40, 8, 30], walk=35)
    arrivals = [tm.arrival(0, 1, t) for t in range(530, 575)]
    assert all(a <= b for a, b in zip(arrivals, arrivals[1:]))  # leaving later never arrives earlier
    assert all(arr <= t + 35 for t, arr in zip(range(530, 575), arrivals))


def test_arrival_between_grid_points_waits_for_next_departure():
    tm = _matrix([25, 12, 40], walk=60)
    assert tm.arrival(0, 1, 541) == 545 + 12  # next grid departure is 9:05
    assert tm.arrival(0, 1, 551) == 611  # after the grid ends only walking remains


def test_self_trip_is_immediate_and_missing_walk_means_no_trip():
    tm = _matrix([NO_TRIP] * 3, walk=NO_TRIP)
    assert tm.arrival(1, 1, 600) == 600
    assert tm.arrival(0, 1, 540) is None


def test_matrix_round_trips_through_disk(tmp_path):
    tm = _matrix([25, 12, 40], walk=35)
    tm.save(tmp_path / "m.npz")
    loaded = TravelMatrix.load(tmp_path / "m.npz")
    assert loaded.ids == ["a", "b"] and loaded.day == tm.day and loaded.start == 540
    assert np.array_equal(loaded.arrive, tm.arrive) and np.array_equal(loaded.walk, tm.walk)


@pytest.mark.router
def test_known_trips_are_plausible():
    from llmuni.config import load_config
    from llmuni.router_check import run_router_check

    result = run_router_check(load_config())
    assert result["ok"].all(), result.to_string()
