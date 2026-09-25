"""San Francisco's city/county boundary from OSM (Nominatim via osmnx), cached as GeoJSON."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd


def load_boundary(query: str, cache_file: Path) -> tuple[gpd.GeoDataFrame, dict]:
    if not cache_file.exists():
        import osmnx as ox

        gdf = ox.geocode_to_gdf(query)
        gdf = gdf[[c for c in ("osm_type", "osm_id", "display_name", "geometry") if c in gdf.columns]]
        gdf["geometry"] = gdf.geometry.simplify(0.00005)  # ~5 m tolerance keeps the committed file small
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        gdf.to_file(cache_file, driver="GeoJSON")
    gdf = gpd.read_file(cache_file)
    row = gdf.iloc[0]
    meta = {
        "source": "OpenStreetMap boundary via Nominatim (osmnx.geocode_to_gdf)",
        "query": query,
        "osm": f"{row.get('osm_type')}/{row.get('osm_id')}",
        "display_name": row.get("display_name"),
    }
    return gdf, meta
