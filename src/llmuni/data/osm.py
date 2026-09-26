"""Errand POIs and road centerlines from the OSM extract (pyosmium)."""

from __future__ import annotations

import logging
from pathlib import Path

import osmium
import osmium.filter
import pandas as pd
import shapely.wkb

from llmuni.config import CategorySpec

log = logging.getLogger(__name__)

ROAD_CLASSES = ("motorway", "trunk", "primary", "secondary", "tertiary", "residential", "unclassified", "living_street")


def classify(tags: dict[str, str], categories: dict[str, CategorySpec]) -> list[str]:
    """Names of the errand categories whose tag rules match these tags."""
    return [name for name, spec in categories.items() if _matches(tags, spec)]


def _matches(tags: dict[str, str], spec: CategorySpec) -> bool:
    text = " ".join(tags.get(k, "") for k in ("name", "brand", "operator")).lower()
    if spec.require_any and not any(p in text for p in spec.require_any):
        return False
    if any(tags.get(k) in vals for k, vals in spec.tags.items()):
        return True
    branded = spec.branded_tags
    if branded and any(tags.get(k) in vals for k, vals in branded.tags.items()):
        return any(brand in text for brand in branded.brands)
    return False


def _filter_pairs(categories: dict[str, CategorySpec]) -> list[tuple[str, str]]:
    """Every (key, value) any category could match, for pyosmium's tag filter."""
    rules = [spec.tags for spec in categories.values()]
    rules += [spec.branded_tags.tags for spec in categories.values() if spec.branded_tags]
    return sorted({(k, v) for rule in rules for k, vals in rule.items() for v in vals})


def display_name(tags: dict[str, str]) -> str | None:
    """Store name as a person would say it: name, else brand, else operator; ATMs say 'ATM'."""
    name = tags.get("name") or tags.get("brand") or tags.get("operator")
    if name and tags.get("amenity") == "atm" and "atm" not in name.lower():
        name = f"{name} ATM"
    return name


def match_brand(tags: dict[str, str], brands: dict[str, list[str]]) -> str | None:
    """Configured brand label whose patterns occur in the name or brand tag."""
    text = f"{tags.get('name', '')} {tags.get('brand', '')}".lower()
    return next((label for label, patterns in brands.items() if any(p in text for p in patterns)), None)


def hours_tag(tags: dict[str, str], spec: CategorySpec) -> tuple[str | None, str | None]:
    """First configured hours key present on the object, and its value."""
    key = next((k for k in spec.hours_keys if tags.get(k)), None)
    return key, (tags[key] if key else None)


def format_address(tags: dict[str, str]) -> str | None:
    street = tags.get("addr:street")
    if not street:
        return None
    number = tags.get("addr:housenumber")
    return f"{number} {street}" if number else street


def extract_pois(pbf: Path, categories: dict[str, CategorySpec]) -> pd.DataFrame:
    """One row per (OSM object, matching category). Nodes use their location; buildings and
    other areas use a point guaranteed to lie inside the polygon."""
    pairs = _filter_pairs(categories)
    wkb = osmium.geom.WKBFactory()
    rows, broken = [], 0
    objects = (
        osmium.FileProcessor(str(pbf))
        .with_locations()
        .with_areas(osmium.filter.TagFilter(*pairs))
        .with_filter(osmium.filter.TagFilter(*pairs))
    )
    for obj in objects:
        if obj.is_node():
            osm_type, osm_id, lat, lon = "node", obj.id, obj.location.lat, obj.location.lon
        elif obj.is_area():
            osm_type, osm_id = ("way" if obj.from_way() else "relation"), obj.orig_id()
            try:
                point = shapely.wkb.loads(wkb.create_multipolygon(obj), hex=True).representative_point()
            except Exception:  # ring left incomplete at the extract boundary
                broken += 1
                continue
            lat, lon = point.y, point.x
        else:
            continue  # ways and relations arrive again as assembled areas
        tags = {t.k: t.v for t in obj.tags}
        for category in classify(tags, categories):
            spec = categories[category]
            key, hours = hours_tag(tags, spec)
            rows.append({
                "poi_id": f"{osm_type[0]}{osm_id}",
                "osm_type": osm_type,
                "osm_id": osm_id,
                "category": category,
                "name": display_name(tags),
                "brand": match_brand(tags, spec.brands),
                "address": format_address(tags),
                "postcode": tags.get("addr:postcode"),
                "lat": lat,
                "lon": lon,
                "hours_key": key,
                "opening_hours": hours,
                "access": tags.get("access"),
            })
    if broken:
        log.warning("skipped %d areas with broken geometry", broken)
    return pd.DataFrame(rows)


def extract_roads(pbf: Path) -> list[tuple[str, list[tuple[float, float]]]]:
    """(highway class, [(lon, lat), ...]) for streets, used as the map background."""
    roads = []
    objects = (
        osmium.FileProcessor(str(pbf))
        .with_locations()
        .with_filter(osmium.filter.TagFilter(*(("highway", c) for c in ROAD_CLASSES)))
    )
    for obj in objects:
        if obj.is_way():
            try:
                roads.append((obj.tags["highway"], [(n.lon, n.lat) for n in obj.nodes]))
            except osmium.InvalidLocationError:
                continue
    return roads


def intersection_points(pbf: Path, pairs: list[tuple[str, str]], max_spread_m: float = 150) -> dict:
    """(lat, lon) where two named streets meet: the mean of the nodes both streets share.
    Returns None for pairs that never meet (or meet in places farther apart than max_spread_m)."""
    names = {name for pair in pairs for name in pair}
    street_nodes: dict[str, set[int]] = {name: set() for name in names}
    locations: dict[int, tuple[float, float]] = {}
    objects = osmium.FileProcessor(str(pbf)).with_locations().with_filter(osmium.filter.KeyFilter("highway"))
    for obj in objects:
        if obj.is_way() and obj.tags.get("name") in names:
            for node in obj.nodes:
                try:
                    locations[node.ref] = (node.lat, node.lon)
                except osmium.InvalidLocationError:
                    continue
                street_nodes[obj.tags["name"]].add(node.ref)
    points = {}
    for a, b in pairs:
        shared = [locations[n] for n in street_nodes[a] & street_nodes[b]]
        if not shared:
            points[(a, b)] = None
            continue
        lat, lon = (sum(c) / len(shared) for c in zip(*shared))
        spread = max(abs(p[0] - lat) * 111_000 + abs(p[1] - lon) * 88_000 for p in shared)
        if spread > max_spread_m:
            log.warning("%s and %s meet in several places (spread %.0f m)", a, b, spread)
            points[(a, b)] = None
        else:
            points[(a, b)] = (lat, lon)
    return points


def snapshot_timestamp(pbf: Path) -> str | None:
    """Replication timestamp from the PBF header, if the extract recorded one."""
    header = osmium.FileProcessor(str(pbf)).header
    return header.get("osmosis_replication_timestamp") or header.get("timestamp") or None
