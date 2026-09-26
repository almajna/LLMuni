from llmuni.config import BrandedTags, CategorySpec
from llmuni.data.osm import classify, display_name, format_address, hours_tag, match_brand

CATEGORIES = {
    "pharmacy": CategorySpec(
        tags={"amenity": ["pharmacy"], "healthcare": ["pharmacy"]},
        branded_tags=BrandedTags(tags={"shop": ["chemist"]}, brands=["walgreens", "cvs", "rite aid"]),
        hours_keys=["opening_hours:pharmacy", "opening_hours"],
    ),
    "coffee": CategorySpec(tags={"amenity": ["cafe"]}),
    "bakery": CategorySpec(tags={"shop": ["bakery"]}),
    "bank_atm": CategorySpec(tags={"amenity": ["bank", "atm"]}),
}


def test_one_object_can_serve_several_categories():
    assert classify({"amenity": "cafe", "shop": "bakery"}, CATEGORIES) == ["coffee", "bakery"]
    assert classify({"amenity": "bench"}, CATEGORIES) == []


def test_chemist_counts_as_pharmacy_only_for_counter_chains():
    assert classify({"shop": "chemist", "name": "Walgreens"}, CATEGORIES) == ["pharmacy"]
    assert classify({"shop": "chemist", "name": "Pharmacy", "brand": "CVS Pharmacy"}, CATEGORIES) == ["pharmacy"]
    assert classify({"shop": "chemist", "name": "Sephora"}, CATEGORIES) == []


def test_require_any_keeps_only_matching_operators_or_names():
    spec = {"post_office": CategorySpec(tags={"amenity": ["post_office"]},
                                        require_any=["united states postal service", "post office", " station"])}
    assert classify({"amenity": "post_office", "name": "Rincon Station"}, spec) == ["post_office"]
    assert classify({"amenity": "post_office", "name": "X", "operator": "United States Postal Service"}, spec) == ["post_office"]
    assert classify({"amenity": "post_office", "name": "The UPS Store", "brand": "The UPS Store"}, spec) == []


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
