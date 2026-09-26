"""Match a store a model named to an OSM POI of the errand's category.

Order: explicit poi_id; a store of the category at the same house number and street; the best-named
store of the category within 150 m of the geocoded address; and, when the address is missing or
cannot be geocoded, the name alone (for a chain, the branch with verifiable hours nearest the previous
stop). A geocoded address with no such store nearby means the store does not exist there: hallucinated.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import pandas as pd
from rapidfuzz import fuzz

from llmuni.grader.geocode import Geocoder, normalize_street, parse_address
from llmuni.hours import VERIFIABLE

RADIUS_M = 150
NAME_NEAR = 60  # name similarity for a store within RADIUS_M of the given address
NAME_ALONE = 85  # name similarity when only the name is usable
NOISE = re.compile(r"\b(?:the|inc|llc|co|store|shop|san francisco|sf)\b")


def normalize_name(name: str) -> str:
    text = name.lower().replace("&", " and ").replace("’", "'")
    text = re.sub(r"[^a-z0-9' ]+", " ", text)
    return " ".join(NOISE.sub(" ", text).split())


def name_score(a: str, b: str) -> float:
    return fuzz.token_set_ratio(normalize_name(a), normalize_name(b))


@dataclass(frozen=True)
class Match:
    status: str  # matched | unverifiable | hallucinated
    poi_id: str | None = None
    method: str | None = None  # id | address | geocode | name | nearest_branch
    reason: str | None = None  # unverifiable: hours_unknown | category_unconfirmed
    hours_status: str | None = None
    lat: float | None = None
    lon: float | None = None


class StoreMatcher:
    def __init__(self, pois: pd.DataFrame, geocoder: Geocoder, radius_m: float = RADIUS_M) -> None:
        """pois: every named POI of the benchmark's categories, whatever its hours status."""
        self.pois = pois.reset_index(drop=True)
        self.by_category = {c: rows.reset_index(drop=True) for c, rows in self.pois.groupby("category")}
        self.geocoder = geocoder
        self.radius_m = radius_m

    def match(self, category: str, store_name: str, address: str | None = None, poi_id: str | None = None,
              near: tuple[float, float] | None = None) -> Match:
        stores = self.by_category.get(category)
        if stores is None or stores.empty:
            return Match("hallucinated")
        if poi_id:
            hit = np.flatnonzero(stores["poi_id"].to_numpy() == poi_id)
            if hit.size:
                return self._found(stores.iloc[hit[0]], "id")
        scores = np.array([name_score(store_name, n) for n in stores["name"]])

        number, street, _ = parse_address(address) if address else (None, None, None)
        if number is not None and street:
            same = [i for i, a in enumerate(stores["address"]) if _same_address(a, number, street)]
            same = [i for i in same if scores[i] >= NAME_NEAR]
            if same:
                return self._found(stores.iloc[max(same, key=lambda i: scores[i])], "address")

        point = self.geocoder.geocode(address)
        if point is not None:
            dist = _meters(point, stores["lat"].to_numpy(), stores["lon"].to_numpy())
            ok = (dist <= self.radius_m) & (scores >= NAME_NEAR)
            if ok.any():
                return self._found(stores.iloc[int(np.argmax(np.where(ok, scores - dist / self.radius_m, -np.inf)))],
                                   "geocode")
            return self._other_category(category, store_name, point) or Match("hallucinated")

        strong = np.flatnonzero(scores >= NAME_ALONE)
        if strong.size > 1:  # a chain named without an address: prefer branches whose hours we can verify
            verifiable = strong[stores["hours_status"].to_numpy()[strong] == "valid"]
            strong = verifiable if verifiable.size else strong
        if strong.size == 1 or (strong.size and near is None):
            return self._found(stores.iloc[strong[np.argmax(scores[strong])]], "name")
        if strong.size:
            dist = _meters(near, stores["lat"].to_numpy()[strong], stores["lon"].to_numpy()[strong])
            return self._found(stores.iloc[strong[int(np.argmin(dist))]], "nearest_branch")
        return self._other_category(category, store_name, None) or Match("hallucinated")

    def _found(self, row: pd.Series, method: str) -> Match:
        status = row["hours_status"]
        if status in VERIFIABLE:
            return Match("matched", row["poi_id"], method, hours_status=status, lat=row["lat"], lon=row["lon"])
        return Match("unverifiable", row["poi_id"], method, reason="hours_unknown", hours_status=status,
                     lat=row["lat"], lon=row["lon"])

    def _other_category(self, category: str, store_name: str, point: tuple[float, float] | None) -> Match | None:
        """A real store under this name, mapped for a different errand category: we cannot confirm
        it serves this errand (e.g. a Safeway named for a pharmacy errand)."""
        others = self.pois[self.pois["category"] != category]
        scores = np.array([name_score(store_name, n) for n in others["name"]])
        ok = scores >= NAME_ALONE
        if point is not None:
            ok &= _meters(point, others["lat"].to_numpy(), others["lon"].to_numpy()) <= self.radius_m
        if not ok.any():
            return None
        row = others.iloc[int(np.argmax(np.where(ok, scores, -1)))]
        return Match("unverifiable", row["poi_id"], "name", reason="category_unconfirmed",
                     hours_status=row["hours_status"], lat=row["lat"], lon=row["lon"])


def _same_address(poi_address: object, number: int, street: str) -> bool:
    if not isinstance(poi_address, str):
        return False
    poi_number, poi_street, _ = parse_address(poi_address)
    return poi_number == number and poi_street == normalize_street(street)


def _meters(point: tuple[float, float], lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    lat, lon = point
    x = np.radians(lons - lon) * np.cos(np.radians((lats + lat) / 2))
    return 6_371_000 * np.hypot(x, np.radians(lats - lat))
