import random

from llmuni.tasks.prompts import clock, noun, render_prompt
from llmuni.tasks.schema import Candidate, Design, End, ErrandSpec, Start, Task


def _task(**changes) -> Task:
    task = Task(
        task_id="v2026.10-medium-001", benchmark_version="v2026.10", tier="medium", weekday="Wednesday",
        date="2026-10-07",
        start=Start(place_id="L02", label="24th & Valencia", neighborhood="Mission", lat=37.75, lon=-122.42,
                    depart_time="10:30"),
        errands=[ErrandSpec(category="pharmacy", service_min=10),
                 ErrandSpec(category="supermarket", brand="Trader Joe's", service_min=20, deadline="14:00")],
        end=End(place_id="L25", label="Union Square (Powell & Geary)", neighborhood="Downtown", lat=37.787,
                lon=-122.408, arrive_by="16:00"),
        candidates={"pharmacy": [Candidate(poi_id="n1", name="Walgreens", address=None, lat=37.75, lon=-122.42,
                                           opening_hours="Mo-Su 08:00-22:00")]},
        prompt="", design=Design(),
    )
    return task.model_copy(update=changes)


def test_clock_formats_twelve_hour_times():
    assert [clock(t) for t in ("00:30", "09:05", "12:00", "14:05", "23:59")] == [
        "12:30 am", "9:05 am", "12:00 pm", "2:05 pm", "11:59 pm"]


def test_prompt_states_every_errand_constraint_and_the_impossibility_option():
    prompt = render_prompt(_task(), random.Random(0))
    assert "24th & Valencia (Mission)" in prompt and "10:30 am" in prompt and "October 7" in prompt
    assert "pharmacy" in prompt and "Trader Joe's" in prompt
    assert "by 2:00 pm at the latest" in prompt  # the grocery deadline
    assert "Union Square (Powell & Geary)" in prompt and "by 4:00 pm" in prompt
    assert "impossible" in prompt
    assert "Walgreens" not in prompt  # candidate stores belong to open-book mode only


def test_deadline_sentence_reuses_the_errands_own_wording():
    for seed in range(20):
        prompt = render_prompt(_task(), random.Random(seed))
        errand_list = prompt.split("Today I need to ")[1].split(".")[0]
        deadline_what = prompt.split("I have to ")[1].split(" by 2:00 pm")[0]
        assert deadline_what in errand_list


def test_brand_replaces_the_generic_store_noun():
    assert noun(ErrandSpec(category="supermarket", brand="Safeway", service_min=20)) == "Safeway"
    assert noun(ErrandSpec(category="bank_atm", service_min=5)) == "bank or ATM"
