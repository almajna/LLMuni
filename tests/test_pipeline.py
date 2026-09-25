import pandas as pd

from llmuni.data.pipeline import dedupe


def _poi(poi_id, name, lat, lon, category="coffee", hours=None, address=None):
    osm_type = {"n": "node", "w": "way"}[poi_id[0]]
    return {"poi_id": poi_id, "osm_type": osm_type, "category": category, "name": name,
            "lat": lat, "lon": lon, "opening_hours": hours, "address": address}


def test_dedupe_keeps_best_copy_and_distinct_places():
    df = pd.DataFrame([
        _poi("n1", "Blue Bottle", 37.77600, -122.42300),                        # node copy, no hours
        _poi("w2", "Blue Bottle", 37.77615, -122.42310, hours="Mo-Su 07:00-17:00"),  # building copy, ~19 m away
        _poi("n3", "Blue Bottle", 37.78100, -122.42300),                        # another branch, ~560 m away
        _poi("n4", "Blue Bottle", 37.77600, -122.42300, category="bakery"),     # same spot, other category
    ])
    assert sorted(dedupe(df, radius_m=75)["poi_id"]) == ["n3", "n4", "w2"]
