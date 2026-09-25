from llmuni.config import CategorySpec
from llmuni.data.osm import classify, display_name, format_address, hours_tag, match_brand

CATEGORIES = {
    "pharmacy": CategorySpec(
        tags={"amenity": ["pharmacy"], "healthcare": ["pharmacy"]},
        hours_keys=["opening_hours:pharmacy", "opening_hours"],
    ),
    "coffee": CategorySpec(tags={"amenity": ["cafe"]}),
    "bakery": CategorySpec(tags={"shop": ["bakery"]}),
    "bank_atm": CategorySpec(tags={"amenity": ["bank", "atm"]}),
}


def test_one_object_can_serve_several_categories():
    assert classify({"amenity": "cafe", "shop": "bakery"}, CATEGORIES) == ["coffee", "bakery"]
    assert classify({"amenity": "bench"}, CATEGORIES) == []


def test_pharmacy_counter_hours_win_over_store_hours():
    tags = {"amenity": "pharmacy", "opening_hours": "Mo-Su 07:00-22:00", "opening_hours:pharmacy": "Mo-Fr 09:00-21:00"}
    assert hours_tag(tags, CATEGORIES["pharmacy"]) == ("opening_hours:pharmacy", "Mo-Fr 09:00-21:00")
    assert hours_tag({"amenity": "cafe"}, CATEGORIES["coffee"]) == (None, None)


def test_display_names():
    assert display_name({"name": "Arizmendi Bakery", "brand": "Other"}) == "Arizmendi Bakery"
    assert display_name({"amenity": "atm", "operator": "Chase"}) == "Chase ATM"
    assert display_name({"amenity": "cafe"}) is None


def test_brand_matching_is_case_insensitive():
    brands = {"Trader Joe's": ["trader joe"], "Safeway": ["safeway"]}
    assert match_brand({"name": "TRADER JOE'S"}, brands) == "Trader Joe's"
    assert match_brand({"name": "Rainbow Grocery"}, brands) is None


def test_address_formatting():
    assert format_address({"addr:housenumber": "555", "addr:street": "9th Street"}) == "555 9th Street"
    assert format_address({"addr:housenumber": "555"}) is None
