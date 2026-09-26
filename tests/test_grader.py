from datetime import date

import numpy as np
import pandas as pd
import pytest

from llmuni.config import load_config
from llmuni.grader.answer import Answer, parse_answer
from llmuni.grader.geocode import Geocoder, parse_address
from llmuni.grader.match import StoreMatcher
from llmuni.grader.registry import build_registry, core_name, distinctive
from llmuni.grader.replay import Grader
from llmuni.oracle.build import InstanceBuilder
from llmuni.router import TravelMatrix, fifo_arrivals
from llmuni.tasks.schema import Design, End, ErrandSpec, Start, Task

POIS = pd.DataFrame([
    # poi_id, category, name, address, lat, lon, opening_hours, hours_status
    ("p1", "pharmacy", "Walgreens", "100 Market Street", 37.7900, -122.4000, "Mo-Su 08:00-22:00", "valid"),
    ("p2", "pharmacy", "Walgreens", "900 Irving Street", 37.7640, -122.4660, "Mo-Su 08:00-22:00", "valid"),
    ("p3", "coffee", "Blue Bottle Coffee", "66 Mint Street", 37.7820, -122.4050, "Mo-Su 07:00-09:30", "valid"),
    ("p4", "coffee", "Ritual Coffee Roasters", "1026 Valencia Street", 37.7560, -122.4210, "Mo-Su 07:00-19:00", "valid"),
    ("p5", "coffee", "Mystery Cafe", None, 37.7700, -122.4300, None, "missing"),
    ("p6", "supermarket", "Safeway", "2020 Market Street", 37.7690, -122.4280, "Mo-Su 06:00-23:00", "valid"),
], columns=["poi_id", "category", "name", "address", "lat", "lon", "opening_hours", "hours_status"])
POIS["valid_hours"] = POIS["hours_status"] == "valid"
POIS["brand"] = None


class OneDayMatrices:
    """Stands in for travel.Matrices: 10 minutes between any two places on a 5-minute grid, 30 on foot."""

    def __init__(self) -> None:
        ids = ["L01", "L02", "p1", "p2", "p3", "p4", "p6"]
        minutes = np.full((len(ids), len(ids), 60), 10, dtype=np.uint16)
        walk = np.full((len(ids), len(ids)), 30, dtype=np.uint16)
        np.fill_diagonal(walk, 0)
        self.tm = TravelMatrix(ids, date(2026, 10, 7), 540, 5, fifo_arrivals(minutes, 540, 5), walk)

    def for_day(self, day):
        return self.tm


def make_task(infeasible: bool = False) -> Task:
    return Task(
        task_id="t1", benchmark_version="test", tier="easy", weekday="Wednesday", date="2026-10-07",
        start=Start(place_id="L01", label="Start", neighborhood="SoMa", lat=37.78, lon=-122.41, depart_time="09:00"),
        errands=[ErrandSpec(category="pharmacy", service_min=10), ErrandSpec(category="coffee", service_min=10)],
        end=End(place_id="L02", label="End", neighborhood="Mission", lat=37.76, lon=-122.42, arrive_by="11:00"),
        candidates={}, prompt="", design=Design(infeasible=infeasible),
    )


REGISTRY = build_registry(pd.DataFrame([
    # dba_name, ownership_name, full_business_address, location
    ("Golden Gate Apothecary", "Golden Gate Apothecary Inc", "100 Market St", "POINT (-122.4001 37.7901)"),
    ("Sightglass Coffee #002", "Sightglass Coffee Roasters Llc", "270 7th St", "POINT (-122.4086 37.7766)"),
    ("Cafe", "Jane Doe", "1030 Valencia St", "POINT (-122.4211 37.7561)"),
], columns=["dba_name", "ownership_name", "full_business_address", "location"]))


def _geocoder() -> Geocoder:
    return Geocoder(
        {
            "market street": (np.array([100, 2020]), np.array([[37.7900, -122.4000], [37.7690, -122.4280]])),
            "mint street": (np.array([66]), np.array([[37.7820, -122.4050]])),
            "valencia street": (np.array([1026]), np.array([[37.7560, -122.4210]])),
            "irving street": (np.array([900]), np.array([[37.7640, -122.4660]])),
        },
        {}, {},
    )


def _grader(registry=None) -> Grader:
    builder = InstanceBuilder(load_config(), OneDayMatrices(), POIS)
    oracle = {"t1": {"optimum": {"finish": "09:50"}, "global_optimum": {"finish": "09:50"}}}
    return Grader(builder, StoreMatcher(POIS, _geocoder(), registry=registry), oracle)


@pytest.fixture(scope="module")
def grader() -> Grader:
    return _grader()


@pytest.fixture(scope="module")
def registered() -> Grader:
    return _grader(REGISTRY)


def answer(*stops, feasible=True) -> Answer:
    return Answer(feasible=feasible, stops=[dict(zip(("category", "store_name", "address"), s)) for s in stops])


def test_good_plan_replays_feasible_with_zero_gap(grader):
    g = grader.grade(make_task(), answer(("pharmacy", "Walgreens", "100 Market St"),
                                         ("coffee", "Ritual Coffee", "1026 Valencia St")), "closed_book")
    assert g.status == "feasible" and g.finish == "09:50" and g.optimality_gap == 0.0
    assert [s["done"] for s in g.stops] == ["09:20", "09:40"]


def test_store_that_closes_before_arrival_makes_the_plan_infeasible(grader):
    g = grader.grade(make_task(), answer(("pharmacy", "Walgreens", "100 Market St"),
                                         ("coffee", "Blue Bottle", "66 Mint St")), "closed_book")
    assert g.status == "infeasible" and g.failure.startswith("closed")
    assert g.stops[1]["failed"] == "closed" and g.stops[1]["arrive"] == "09:30"


def test_made_up_store_at_a_real_address_is_hallucinated(grader):
    g = grader.grade(make_task(), answer(("pharmacy", "Golden Gate Apothecary", "100 Market St"),
                                         ("coffee", "Ritual Coffee", "1026 Valencia St")), "closed_book")
    assert g.status == "hallucinated" and g.hallucinated_store


def test_store_with_unknown_hours_is_unverifiable_not_infeasible(grader):
    g = grader.grade(make_task(), answer(("pharmacy", "Walgreens", "100 Market St"),
                                         ("coffee", "Mystery Cafe", "somewhere downtown")), "closed_book")
    assert g.status == "unverifiable" and g.unverifiable_stops == 1 and "hours_unknown" in g.failure


def test_chain_without_address_uses_the_branch_nearest_the_previous_stop(grader):
    g = grader.grade(make_task(), answer(("pharmacy", "Walgreens", None),
                                         ("coffee", "Ritual Coffee", "1026 Valencia St")), "closed_book")
    assert g.stops[0]["poi_id"] == "p1" and g.stops[0]["method"] == "nearest_branch"


def test_store_mapped_for_another_errand_is_unverifiable(grader):
    g = grader.grade(make_task(), answer(("pharmacy", "Safeway", "2020 Market St"),
                                         ("coffee", "Ritual Coffee", "1026 Valencia St")), "closed_book")
    assert g.status == "unverifiable" and "category_unconfirmed" in g.failure


def test_declining_is_right_only_for_infeasible_tasks(grader):
    declined = answer(feasible=False)
    assert grader.grade(make_task(infeasible=True), declined, "open_book").correct_infeasible_call is True
    wrong = grader.grade(make_task(), declined, "open_book")
    assert wrong.status == "declined" and wrong.false_infeasible_call


def test_plan_for_an_impossible_task_is_not_a_correct_call(grader):
    g = grader.grade(make_task(infeasible=True), answer(("pharmacy", "Walgreens", "100 Market St"),
                                                        ("coffee", "Ritual Coffee", "1026 Valencia St")), "open_book")
    assert g.correct_infeasible_call is False


def test_plans_must_cover_each_errand_once(grader):
    g = grader.grade(make_task(), answer(("pharmacy", "Walgreens", "100 Market St")), "closed_book")
    assert g.status == "invalid_plan" and "missing errands: coffee" in g.failure
    assert grader.grade(make_task(), None, "closed_book").status == "invalid_json"


def test_parse_answer_accepts_fenced_json_and_reports_schema_errors():
    good, error, pure = parse_answer('Here you go:\n```json\n{"feasible": true, "stops": []}\n```')
    assert good is not None and error is None and not pure
    assert parse_answer('{"feasible": false, "reason": "closed"}')[2] is True
    bad, error, _ = parse_answer('{"stops": []}')
    assert bad is None and error.startswith("schema")
    assert parse_answer("I think you should go to Walgreens first.")[1] == "no JSON object found"


def test_address_parsing():
    assert parse_address("2690 Mission St, San Francisco, CA 94110") == (2690, "mission street", None)
    assert parse_address("Haight & Ashbury") == (None, "haight", "ashbury")
    assert parse_address("2020 Market Street #100")[:2] == (2020, "market street")


RITUAL = ("coffee", "Ritual Coffee", "1026 Valencia St")


def test_real_store_missing_from_osm_is_unverifiable_not_hallucinated(registered):
    g = registered.grade(make_task(), answer(("pharmacy", "Golden Gate Apothecary", "100 Market St"), RITUAL), "closed_book")
    assert g.status == "unverifiable" and g.not_in_osm_stops == 1 and not g.hallucinated_store
    assert g.stops[0]["reason"] == "not_in_osm" and g.stops[0]["method"] == "registry"


def test_registered_store_named_without_an_address_is_not_in_osm(registered):
    g = registered.grade(make_task(), answer(("pharmacy", "Golden Gate Apothecary", None), RITUAL), "closed_book")
    assert g.status == "unverifiable" and g.stops[0]["reason"] == "not_in_osm"


def test_chain_mapped_elsewhere_is_a_wrong_address(registered):
    g = registered.grade(make_task(), answer(("pharmacy", "Walgreens", "66 Mint St"), RITUAL), "closed_book")
    assert g.status == "wrong_address" and g.wrong_address and not g.hallucinated_store


def test_store_registered_only_elsewhere_is_a_wrong_address(registered):
    g = registered.grade(make_task(), answer(("pharmacy", "Walgreens", "100 Market St"),
                                             ("coffee", "Sightglass Coffee", "2020 Market St")), "closed_book")
    assert g.status == "wrong_address" and g.stops[1]["reason"] == "wrong_address"


def test_store_in_neither_source_does_not_exist(registered):
    g = registered.grade(make_task(), answer(("pharmacy", "Imaginary Drugs", "100 Market St"), RITUAL), "closed_book")
    assert g.status == "hallucinated" and g.hallucinated_store and g.stops[0]["reason"] == "no_such_store"


def test_generic_names_never_match_the_registry():
    assert core_name("Walgreens #04529") == "walgreens" and core_name("Bank Of America, N.A.") == "bank of america"
    assert not distinctive(core_name("The Coffee Shop")) and distinctive(core_name("Ritual Coffee"))
    assert not REGISTRY.near("Coffee", (37.7561, -122.4211), None, None, 150)  # "Cafe" is too generic to be a name
    assert not REGISTRY.anywhere("Blue Cafe")
