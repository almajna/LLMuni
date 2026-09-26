# Phase 1: errand POI coverage

OSM snapshot 2026-09-18 · Muni GTFS 2026-08-29–2027-01-15 · BART GTFS 2026-08-10–2027-01-10 · reference week Oct 5–11, 2026

POIs are named, publicly accessible OSM features inside the San Francisco boundary, de-duplicated.
*Valid* means the hours parse, have no `unknown` periods, and open at least once in the reference week;
only valid places become task candidates. *Unknown* places parse but contain `unknown` periods.

| Category | POIs | Hours tagged | Parseable | Unknown | Valid | % valid | Kept |
|---|---:|---:|---:|---:|---:|---:|:---:|
| Pharmacy | 51 | 25 | 25 | 0 | 25 | 49.0 | yes |
| Post office | 40 | 16 | 16 | 0 | 16 | 40.0 | yes |
| Supermarket | 120 | 77 | 77 | 0 | 77 | 64.2 | yes |
| Hardware | 53 | 30 | 30 | 0 | 30 | 56.6 | yes |
| Bank / ATM | 323 | 123 | 123 | 0 | 122 | 37.8 | yes |
| Library | 29 | 15 | 15 | 0 | 15 | 51.7 | yes |
| Coffee | 793 | 423 | 422 | 0 | 421 | 53.1 | yes |
| Bakery | 142 | 76 | 76 | 0 | 76 | 53.5 | yes |
| Dry cleaning | 126 | 39 | 39 | 0 | 39 | 31.0 | yes |
| Bookstore | 61 | 38 | 38 | 0 | 38 | 62.3 | yes |
| Florist | 69 | 21 | 21 | 0 | 20 | 29.0 | yes |
| Bike shop | 43 | 26 | 25 | 0 | 25 | 58.1 | yes |
| Electronics | 15 | 7 | 6 | 0 | 6 | 40.0 | **no** |
| **All** | 1865 | 916 | 913 | 0 | 910 | 48.8 | |

Supermarket brands with valid hours: Safeway 13, Whole Foods Market 9, Trader Joe's 7.
