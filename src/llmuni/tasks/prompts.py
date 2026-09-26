"""Natural-language prompts: friendly, specific, and silent about the best order."""

from __future__ import annotations

import random

from llmuni.tasks.schema import ErrandSpec, Task

ERRAND_PHRASES = {
    "pharmacy": ["pick up a prescription at a pharmacy", "grab my prescription from a pharmacy"],
    "post_office": ["mail a package at a post office", "drop off a parcel at a post office"],
    "supermarket": ["do a grocery run at a supermarket", "pick up groceries at a supermarket"],
    "hardware": ["buy picture hooks at a hardware store", "get a replacement faucet washer at a hardware store"],
    "bank_atm": ["get cash from a bank or ATM", "withdraw cash at a bank or ATM"],
    "library": ["return books at a library", "drop off library books at a library"],
    "coffee": ["grab a coffee at a café", "pick up a coffee at a café"],
    "bakery": ["pick up a loaf of bread at a bakery", "buy pastries at a bakery"],
    "dry_cleaning": ["drop off a suit at a dry cleaner", "pick up my dry cleaning"],
    "bookstore": ["buy a birthday present at a bookstore", "pick up a book I ordered at a bookstore"],
    "florist": ["buy flowers at a florist", "get a bouquet from a florist"],
    "bike_shop": ["buy a new inner tube at a bike shop", "get my bike light fixed at a bike shop"],
}
NOUNS = {
    "pharmacy": "pharmacy", "post_office": "post office", "supermarket": "supermarket",
    "hardware": "hardware store", "bank_atm": "bank or ATM", "library": "library", "coffee": "café",
    "bakery": "bakery", "dry_cleaning": "dry cleaner", "bookstore": "bookstore", "florist": "florist",
    "bike_shop": "bike shop",
}
OPENINGS = [
    "It's {weekday}, {date}, and I'm heading out from {start} around {depart}.",
    "Plan my {weekday} ({date}) for me. I'll leave {start} at {depart}.",
    "Help me plan errands on {weekday}, {date}. I start at {start} at {depart}.",
]
TRANSPORT = [
    "I don't have a car, so I'll get around on Muni, BART and on foot.",
    "No car today: just Muni, BART and walking.",
]
CLOSINGS = [
    "Which specific stores should I go to, and in what order, so I'm done as early as possible?",
    "Tell me exactly which stores to visit and in what order so I finish as early as I can.",
]


def clock(hhmm: str) -> str:
    """'14:05' -> '2:05 pm'."""
    hour, minute = map(int, hhmm.split(":"))
    suffix = "am" if hour < 12 else "pm"
    return f"{(hour - 1) % 12 + 1}:{minute:02d} {suffix}"


def noun(errand: ErrandSpec) -> str:
    """'post office', or the brand for a branded grocery run."""
    return errand.brand or NOUNS[errand.category]


def errand_phrase(errand: ErrandSpec, rng: random.Random) -> str:
    """'pick up a prescription at a pharmacy' (one of a few phrasings; a brand replaces 'a supermarket')."""
    phrase = rng.choice(ERRAND_PHRASES[errand.category])
    return phrase.replace("a supermarket", f"a {errand.brand}") if errand.brand else phrase


def render_prompt(task: Task, rng: random.Random) -> str:
    start = f"{task.start.label} ({task.start.neighborhood})"
    parts = [
        rng.choice(OPENINGS).format(
            weekday=task.weekday, date=_day(task.date), start=start, depart=clock(task.start.depart_time)
        ),
        rng.choice(TRANSPORT),
    ]
    errands = list(task.errands)
    rng.shuffle(errands)  # the listed order carries no information about the best order
    phrases = {e.category: errand_phrase(e, rng) for e in errands}  # one phrasing per errand, reused below
    items = [f"{phrases[e.category]} (about {e.service_min} minutes)" for e in errands]
    parts.append("Today I need to " + _join(items) + ".")
    for errand in errands:
        if errand.deadline:
            parts.append(f"I have to {phrases[errand.category]} by {clock(errand.deadline)} at the latest.")
    if task.end:
        where = f"{task.end.label} ({task.end.neighborhood})"
        if task.end.arrive_by:
            parts.append(f"When I'm done I'm meeting a friend at {where} and need to be there by {clock(task.end.arrive_by)}.")
        else:
            parts.append(f"When I'm done I'm meeting a friend at {where}.")
    parts.append(rng.choice(CLOSINGS))
    parts.append("If it can't all be done, tell me it's impossible and why.")
    return " ".join(parts)


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + ", and " + items[-1]


def _day(iso: str) -> str:
    year, month, day = map(int, iso.split("-"))
    months = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
              "October", "November", "December"]
    return f"{months[month - 1]} {day}"
