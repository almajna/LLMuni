// The map wall: OpenFreeMap vector tiles (OpenMapTiles schema, no key) drawn in the console's own slate
// palette. Streets are dim engraving, rail lines read as the network, neighbourhoods are small-caps labels,
// and buildings extrude in matte slate so routes stay the brightest thing on the wall.
import type { StyleSpecification } from "maplibre-gl";

const C = {
  ground: "#0b1110",
  water: "#0a1618",
  park: "#0f1a16",
  street: "#1b2624",
  major: "#24312f",
  rail: "#3b4a47",
  building: "#1c2826",
  label: "#6f817a",
  halo: "#0b1110",
};

export const MAP_STYLE: StyleSpecification = {
  version: 8,
  glyphs: "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf",
  sources: {
    omt: { type: "vector", url: "https://tiles.openfreemap.org/planet" },
  },
  layers: [
    { id: "ground", type: "background", paint: { "background-color": C.ground } },
    { id: "park", type: "fill", source: "omt", "source-layer": "park", paint: { "fill-color": C.park } },
    {
      id: "landcover", type: "fill", source: "omt", "source-layer": "landcover",
      filter: ["in", ["get", "class"], ["literal", ["grass", "wood"]]], paint: { "fill-color": C.park },
    },
    { id: "water", type: "fill", source: "omt", "source-layer": "water", paint: { "fill-color": C.water } },
    {
      id: "streets", type: "line", source: "omt", "source-layer": "transportation",
      filter: ["in", ["get", "class"], ["literal", ["minor", "service", "tertiary", "path", "track"]]],
      paint: { "line-color": C.street, "line-width": ["interpolate", ["linear"], ["zoom"], 12, 0.4, 16, 2.2] },
    },
    {
      id: "major", type: "line", source: "omt", "source-layer": "transportation",
      filter: ["in", ["get", "class"], ["literal", ["primary", "secondary", "trunk", "motorway"]]],
      paint: { "line-color": C.major, "line-width": ["interpolate", ["linear"], ["zoom"], 11, 0.8, 16, 4] },
    },
    {
      id: "rail", type: "line", source: "omt", "source-layer": "transportation",
      filter: ["in", ["get", "class"], ["literal", ["rail", "transit"]]],
      paint: {
        "line-color": C.rail, "line-dasharray": [3, 2],
        "line-width": ["interpolate", ["linear"], ["zoom"], 11, 0.7, 16, 2],
      },
    },
    {
      id: "buildings", type: "fill-extrusion", source: "omt", "source-layer": "building", minzoom: 13,
      paint: {
        "fill-extrusion-color": C.building,
        "fill-extrusion-height": ["coalesce", ["get", "render_height"], 6],
        "fill-extrusion-base": ["coalesce", ["get", "render_min_height"], 0],
        "fill-extrusion-opacity": 0.9,
      },
    },
    {
      id: "neighbourhoods", type: "symbol", source: "omt", "source-layer": "place",
      filter: ["in", ["get", "class"], ["literal", ["neighbourhood", "suburb", "quarter"]]],
      layout: {
        "text-field": ["upcase", ["get", "name"]],
        "text-font": ["Noto Sans Regular"],
        "text-size": ["interpolate", ["linear"], ["zoom"], 11, 9, 15, 12],
        "text-letter-spacing": 0.14,
        "text-max-width": 8,
      },
      paint: { "text-color": C.label, "text-halo-color": C.halo, "text-halo-width": 1.2 },
    },
  ],
};
