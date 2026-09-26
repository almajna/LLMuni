---
name: LLMuni
description: "Night dispatch console for a transit-planning benchmark: matte green-black slate, lamp colors with fixed meanings, and a split-flap departure board."
colors:
  gold: "#f0a500"
  alert: "#e5484d"
  alert-ink: "#ff8f8a"
  alert-plate: "#962024eb"
  alert-plate-ink: "#ffecea"
  ok: "#8fcf9c"
  ground: "#0b1110"
  panel: "#111918"
  panel-2: "#172120"
  housing: "#080c0b"
  rule: "#26332f"
  rule-2: "#1b2624"
  ink: "#ebe8de"
  ink-2: "#b9c1bb"
  label: "#8d9f98"
  disabled: "#56675f"
  unverifiable: "#5d6c67"
  flap-top: "#242621"
  flap-bottom: "#181a17"
  flap-split: "#060706"
  flap-ink: "#f3efe2"
  unit-sky: "#72c3f0"
  unit-orchid: "#e394d6"
  unit-teal: "#54d1bd"
  unit-periwinkle: "#a9afff"
  unit-cobalt: "#5b8cff"
  unit-lime: "#9ad36a"
  unit-sand: "#cdb9a0"
  fail-late: "#f29d93"
  fail-wrong-address: "#b39cff"
  fail-invented: "#6f52d9"
  map-water: "#0a1618"
  map-park: "#0f1a16"
  map-arterial: "#24312f"
  map-rail: "#3b4a47"
  map-building: "#1c2826"
  map-label: "#6f817a"
typography:
  display:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "clamp(34px, 4.4vw, 52px)"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "0.01em"
  headline:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "20px"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "0.01em"
  title:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "17px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "0.06em"
  body:
    fontFamily: "Barlow, Segoe UI, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.55
    fontFeature: '"tnum"'
  body-dense:
    fontFamily: "Barlow, Segoe UI, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.45
    fontFeature: '"tnum"'
  caption:
    fontFamily: "Barlow, Segoe UI, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.55
    fontFeature: '"tnum"'
  note:
    fontFamily: "Barlow, Segoe UI, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.4
    fontFeature: '"tnum"'
  label:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "0.14em"
    fontFeature: '"tnum"'
  control:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "0.1em"
    fontFeature: '"tnum"'
  readout:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "14px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "0.03em"
    fontFeature: '"tnum"'
  flap:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "22px"
    fontWeight: 600
    lineHeight: "30px"
  flap-small:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "17px"
    fontWeight: 600
    lineHeight: "23px"
  alert-tag:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "16px"
    fontWeight: 700
    lineHeight: 1
rounded:
  hairline: "1px"
  cell: "2px"
  control: "3px"
  panel: "4px"
spacing:
  cell-gap: "2px"
  tight: "6px"
  snug: "10px"
  panel-x: "18px"
  inset: "20px"
  section: "88px"
  gutter: "clamp(16px, 3vw, 40px)"
components:
  top-strip:
    backgroundColor: "{colors.ground}"
    textColor: "{colors.ink}"
    height: "56px"
  nav-link:
    textColor: "{colors.label}"
    padding: "8px 0"
  nav-link-hover:
    textColor: "{colors.ink}"
  rail-panel:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
    padding: "10px 18px"
    width: "404px"
  board-housing:
    backgroundColor: "{colors.housing}"
    rounded: "{rounded.panel}"
    padding: "18px 18px 14px"
  message-board:
    backgroundColor: "{colors.housing}"
    rounded: "{rounded.panel}"
    padding: "10px 10px 9px"
  flap-cell:
    backgroundColor: "{colors.flap-top}"
    textColor: "{colors.flap-ink}"
    typography: "{typography.flap}"
    rounded: "{rounded.cell}"
    width: "18px"
    height: "30px"
  flap-cell-small:
    backgroundColor: "{colors.flap-top}"
    textColor: "{colors.flap-ink}"
    typography: "{typography.flap-small}"
    rounded: "{rounded.cell}"
    width: "15px"
    height: "23px"
  play-key:
    backgroundColor: "{colors.flap-ink}"
    textColor: "{colors.ground}"
    size: "40px"
  play-key-hover:
    backgroundColor: "#fffaf0"
  switch-group:
    backgroundColor: "{colors.ground}"
    rounded: "{rounded.control}"
    padding: "2px"
  switch-key:
    backgroundColor: "transparent"
    textColor: "{colors.label}"
    typography: "{typography.control}"
    rounded: "{rounded.cell}"
    padding: "5px 10px"
  switch-key-hover:
    textColor: "{colors.ink}"
  switch-key-pressed:
    backgroundColor: "{colors.panel-2}"
    textColor: "{colors.ink}"
  switch-key-disabled:
    textColor: "{colors.disabled}"
  speed-key:
    backgroundColor: "transparent"
    textColor: "{colors.label}"
    rounded: "{rounded.control}"
    padding: "5px 8px"
  speed-key-hover:
    textColor: "{colors.ink}"
  task-select:
    backgroundColor: "{colors.panel-2}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "5px 26px 5px 9px"
  errand-chip:
    textColor: "{colors.ink-2}"
    rounded: "{rounded.control}"
    padding: "2px 7px"
  unit-swatch:
    rounded: "{rounded.hairline}"
    width: "12px"
    height: "4px"
  unit-swatch-optimal:
    backgroundColor: "{colors.gold}"
    rounded: "{rounded.hairline}"
    width: "12px"
    height: "6px"
  lamp-gold:
    backgroundColor: "{colors.gold}"
    size: "9px"
  lamp-ok:
    backgroundColor: "{colors.ok}"
    size: "9px"
  lamp-bad:
    backgroundColor: "{colors.alert}"
    size: "9px"
  lamp-off:
    backgroundColor: "{colors.unverifiable}"
    size: "9px"
  alert-tag:
    backgroundColor: "{colors.alert-plate}"
    textColor: "{colors.alert-plate-ink}"
    typography: "{typography.alert-tag}"
    padding: "3px 6px"
  failure-bar:
    rounded: "{rounded.hairline}"
    height: "18px"
---

# Design System: LLMuni

## Overview

**Creative North Star: "The Night Dispatch Console"**

LLMuni is a dispatch floor at night. San Francisco is the wall: a full-bleed 3D map drawn in the console's own slate, where each model is a unit sent across the city on its own clock, the provably optimal plan runs in gold, and failures page in as alerts. Around the wall sits the equipment: matte control-room slate with a green-black cast (never blue), engraved 1px hairlines, sage-gray small-caps labels, and a split-flap board of real cells, lettered in Barlow Condensed like California transit signage.

The system is dense and exact, closer to an instrument panel than to a marketing page. Color is scarce and each color carries one meaning: gold is the optimal plan, red is a failure, sage is done, unlit gray is can't be checked, and seven unit colors kept clear of gold and red tell the models apart. Controls are neutral keys in rocker groups; the only filled key is the warm-white Play. Motion is mechanical: replay time runs linear, flaps drop fast and staggered by column, alerts pulse once and never loop, and reduced motion swaps every flip for its final value.

The world refuses the category default of a white leaderboard table over a hero-metric row, and it has no glow and no glass. The Remotion video (video/src/lib/theme.ts, video/src/lib/Flap.tsx) is a second surface of the same system: the same palette, the same two faces, the same flap cell.

**Key Characteristics:**
- Matte green-black slate, with groups divided by engraved 1px hairlines instead of boxes.
- Lamp colors with fixed meanings: gold optimal, red failed, sage done, gray unverifiable.
- Real split-flap cells for the headline, the standings, the replay clock and the plate.
- One family in two widths: Barlow Condensed for signage, Barlow for reading, tabular numerals throughout.
- A full-bleed 3D map wall with panels hung on it.
- Mechanical motion: linear time, fast staggered flips, single alert pulses.
- Small physical corners (4px at most); no glow, no glass.

## Colors

A matte slate console with lamp colors of fixed meaning, two categorical data sets (units and failure kinds), and a map wall drawn in the console's own tones.

### Primary
- **Optimal Gold** (#f0a500): the provably optimal plan and nothing else: its route (5px, drawn above every unit), its name and swatch in the rail, its lamp when it arrives, and the one word in the rail's opening line that names it. Primary here means the reference point, not the action color: no control, link or heading is ever gold.

### Secondary
- **Alert Red** (#e5484d): a failure, as a mark: failed lamps, the dot and contracting ring where a plan fails on the map, the closed-store segment in the failure bars.
- **Alert Ink** (#ff8f8a): a failure, as words: verdicts in the unit rows ("Late", "Wrong address", "No usable answer") and the load-error line. Alert red on the panel reads at about 4.6:1; alert ink at about 8:1.
- **Alert Plate** (#962024eb, the plate at 92%) with **Plate Ink** (#ffecea): the paged alert tag on the map.

### Tertiary
- **Done Sage** (#8fcf9c): a plan that works on the timetable: done lamps, the "Works on the timetable" segment, and "Correct" when a model rightly calls an impossible day impossible. It also tints text selection, at 32%.

### Neutral
- **Night Slate** (#0b1110): the ground of the page, the strip and the map; the fill of switch groups; the ring around route heads and place markers.
- **Console Slate** (#111918): the rail panel (at 96% over the map) and the map controls.
- **Pressed Slate** (#172120): a pressed key and the task select.
- **Housing Black** (#080c0b): the housings of the standings board and the message board.
- **Engraved Rule** (#26332f): 1px hairlines between panels and sections and around controls; the fader track.
- **Inner Rule** (#1b2624): 1px hairlines inside a panel (between rail sections, unit rows, method columns, fact rows); also the tone of minor streets on the map.
- **Console Ink** (#ebe8de): primary text and names.
- **Faded Ink** (#b9c1bb): secondary reading text: the rail's opening line, definitions, method copy, chips.
- **Sage Gray** (#8d9f98): labels, column heads, nav, captions, notes, the ring of a live lamp, and the underline of links.
- **Dead Key** (#56675f): disabled keys and the thin scrollbar thumbs inside panels.
- **Unlit Lamp** (#5d6c67): can't be checked: the off lamp and the unverifiable segment.
- **Upper Leaf** (#242621) and **Lower Leaf** (#181a17): the two halves of every flap cell, the upper one lighter.
- **Split Line** (#060706): the 1px split across each flap cell.
- **Flap Ink** (#f3efe2): warm white for flap characters, the Play key, the fader cap, the focus ring and the skip link.

### Unit Colors
Seven route colors, assigned in the order of the run's model list and kept clear of gold and red: **Sky** (#72c3f0), **Orchid** (#e394d6), **Teal** (#54d1bd), **Periwinkle** (#a9afff), **Cobalt** (#5b8cff), **Lime** (#9ad36a), **Sand** (#cdb9a0). They draw a model's route (3px), its moving head and the swatch beside its name. Baselines carry no color.

### Failure Kinds
The failure bars add three fills to the lamp colors: **Late Salmon** (#f29d93) for a missed deadline or meet-up, **Wrong-Address Lavender** (#b39cff) for a real store at the wrong address, **Invented Violet** (#6f52d9) for a store that doesn't exist. Closed stores take alert red, working plans done sage, unverifiable plans the unlit lamp gray, and no plan a dark 135° hatch (2px #3a4744 stripes every 6px on #1a2321).

### Map Wall
OpenFreeMap vector tiles drawn in the console's tones, so the routes stay the brightest thing on the wall: ground in night slate, **Bay Water** (#0a1618), **Park** (#0f1a16), minor streets in the inner-rule tone, **Arterial** (#24312f), **Rail Dash** (#3b4a47, dashed 3:2), **Matte Building** (#1c2826, extruded at 90% from zoom 13), and **Neighbourhood Label** (#6f817a) with a night-slate halo.

### Named Rules
**The One Meaning Rule.** Gold is the provably optimal plan and nothing else; red is a failure and nothing else. In lamps and bars, sage always means done and unlit gray always means can't be checked.

**The Separate Channels Rule.** The seven unit colors only identify models: a model's route, its moving head and the swatch beside its name. They never fill a bar, a lamp or a word, and no lamp or failure color ever draws a model's route.

**The Alert Ink Rule.** Red words are set in alert ink; alert red is for marks: lamps, dots, rings and bar fills.

## Typography

**Display Font:** Barlow Condensed (with Arial Narrow, sans-serif)
**Body Font:** Barlow (with Segoe UI, system-ui, sans-serif)

**Character:** One family in two widths. The condensed cut is the console's signage: titles, labels, keys, readouts and every flap character. The regular cut is the plain voice of sentences, names and notes. Both are self-hosted (Barlow 400, 500 and 600; Barlow Condensed 500, 600 and 700), and every numeral is tabular.

### Hierarchy
- **Display** (Barlow Condensed 600, clamp(34px, 4.4vw, 52px), line-height 1, 0.01em, uppercase): section titles (Standings, How plans fail, Method). Scope captions go beneath a title, never above it.
- **Headline** (Barlow Condensed 600, 20px, line-height 1, 0.01em): the one-line question in the top strip, which is the page's h1; 17px at 900px and below, visually hidden at 560px and below.
- **Title** (Barlow Condensed 600, 17px, line-height 1.2, 0.06em, uppercase): method step titles and the run-facts and limits heads.
- **Body** (Barlow 400, 16px, line-height 1.55): reading copy such as the mode explanation, at most 72ch.
- **Body Dense** (Barlow 400, 14px, line-height 1.45): copy inside the rail and the standings definitions. Method copy and run facts sit a half step up, at 14.5px.
- **Caption** (Barlow 400, 15px, line-height 1.55, sage gray): the line under a section title that states its scope (task counts, run status).
- **Note** (Barlow 400, 12px, line-height 1.4, sage gray): unit states, the map caption and small print; notes run from 12 to 13px.
- **Label** (Barlow Condensed 600, 12px, line-height 1, 0.14em, uppercase, sage gray): the engraved label that names a panel ("Request", "Units · Open book").
- **Control** (Barlow Condensed 600, 12px, line-height 1, 0.1em, uppercase): switch keys. The same small caps run a size up for the nav (13px, 0.12em) and for definition terms (13px, 0.1em, console ink), a half size down for board column heads (11.5px, 0.12em), and at weight 500 for the data stamp (12px, 0.1em).
- **Readout** (Barlow Condensed 600, 14px, line-height 1.3, 0.03em): finish times, gaps and verdicts in the unit rows; failure counts at 15px; place labels on the map (START, MEET BY 2:15 PM) at 14px.
- **Flap** (Barlow Condensed 600, 22px on a 30px cell) and **Flap Small** (17px on a 23px cell): split-flap characters, always capitals from a fixed drum.
- **Alert Tag** (Barlow Condensed 700, 16px, uppercase): paged alert tags on the map, the only bold on the site.

Map neighbourhood names are the one exception to the family: the tile server's Noto Sans, uppercase, tracked 0.14em, 9 to 12px, because the map renders its own glyphs.

### Named Rules
**The Signage Rule.** Barlow Condensed is the console's signage: titles, labels, keys, column heads, readouts, flap characters and map tags. Barlow carries everything read as prose: sentences, definitions, names, states and notes.

**The Engraved Label Rule.** Labels are condensed small caps in sage gray, tracked 0.1 to 0.14em. A label names a panel, a control group or a column; it never sits above a heading as a kicker.

**The Tabular Rule.** Every numeral is tabular, so clocks, percentages and costs hold their columns while the replay runs and the board flips.

## Layout

The page is a console bay followed by a reading column. A sticky top strip (56px; 52px at 900px and below) carries the LLMUNI flap plate, the one-line question, the data stamp and the section nav, over a 1px engraved rule. Below it the map wall fills the viewport at full bleed (viewport height minus the strip, held between 680 and 1100px).

Panels hang on the wall at a 20px inset: the rail on the left (404px wide; 360px at 1180px and below) and the message board at the top right, sized to the space the rail leaves. The rail is one column of sections, each padded 10px by 18px and divided by inner rules: the opening line, the call ticket (request, errands, deadlines), the unit list, and the transport. The unit list takes the remaining height and scrolls, its last 44px fading out while more rows wait below. The camera frames the routes clear of both panels (desktop padding of 170px top, 480px left, 120px right, 80px bottom), and the map caption sits on the wall at the bottom left, beside the rail, at most 42ch wide.

Below the wall, sections sit in a 1280px column with side gutters of clamp(16px, 3vw, 40px) and 88px above each title (64px at 900px and below). A section head puts the title and its caption on the left and its switches on the right, wrapping when narrow; the head sits 14px above its content, and the parts of a section sit 22 to 28px apart. The standings definitions run in an auto-fit grid of columns at least 260px wide. The method runs as five columns divided by inner rules (two at 1180px, one at 560px), with the run facts and limits in two columns 56px beneath (one at 900px). The footer sits 72px below the last section, over an engraved rule.

At 900px and below the wall stacks: the map (62svh, 380 to 560px tall) with the message board as two rows of 20 cells across its top, then the rail as a full-width panel with the transport first. The standings board scrolls sideways inside its housing, fading at the right edge, with a swipe hint and each row's key numbers repeated as a flap line under the model name. The nav drops Failures and Method at 900px and keeps only Code at 560px.

## Elevation & Depth

Depth is physical and sparing. The page body is flat and divided by hairlines; the only things that cast shadows are mounted: the panels hung on the map wall, the flap-board housings, and each flap cell. Panels are matte and near-opaque, with no backdrop blur. The one halo in the system is a dark, ground-colored one behind text set directly on the map, the same legibility halo the map's own labels carry.

### Shadow Vocabulary
- **Wall mount** (`box-shadow: 0 12px 32px rgba(0, 0, 0, 0.45)`): the rail and the message board, hung on the map.
- **Board housing** (`box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03), 0 16px 40px rgba(0, 0, 0, 0.35)`): the standings housing, a black box with a faint top lip.
- **Flap ledge** (`box-shadow: 0 1px 0 #000, 0 2px 3px rgba(0, 0, 0, 0.45)`): each flap cell's lower edge and its drop.
- **Pressed bar** (`box-shadow: inset 0 -2px 0 #ebe8de`): a state mark rather than depth: the ink bar along the bottom of a pressed key.
- **Map text halo** (`text-shadow: 0 0 6px #0b1110, 0 0 3px #0b1110`): legibility for text set on the map.

### Named Rules
**The Mounted Panel Rule.** Only mounted things cast shadows: wall panels, flap-board housings and flap cells. Everything else is flat and divided by hairlines.

**The No Glow, No Glass Rule.** Nothing blurs what is behind it and no color glows; panels on the map stay near-opaque (the rail is 96%). The only halo is dark, behind text on the map.

## Shapes

Corners are small and physical, like machined equipment: 1px on swatches and bar segments; 2px on flap cells, switch keys and the fader cap; 3px on switch groups, the select, chips and the speed key; 4px on panels and housings. Round marks carry meaning: a lamp is a 9px circle (a 1.5px sage ring while the outcome is open, filled when it is decided), the Play key is a 40px circle, and on the map the round marks are points (route heads, place markers, alert dots and rings). A model's identity is a short bar that echoes its route stroke: 12 by 4px in the rail and the failure rows, 9 by 4px on the board, and 12 by 6px for the optimal plan, whose route is thicker. Bars are flat blocks with 2px gaps; the no-plan segment is hatched.

### Named Rules
**The Lamp And Swatch Rule.** A circle is a lamp, the Play key or a point on the map; a model's swatch is a short bar that echoes its route.

## Components

### Buttons
Tactile rocker keys, neutral until touched.
- **Shape:** 2px keys inside a 3px rocker group (1px engraved-rule border, night-slate fill, 2px padding and gap).
- **Switch keys:** transparent, sage-gray control caps, 5px by 10px. Hover lifts the text to console ink (150ms); a press scales the key to 0.97 (120ms, ease-out); the pressed key turns pressed slate with console ink and the 2px pressed bar. Disabled keys ("Travel tool · v2") go dead-key gray with a not-allowed cursor.
- **Play (primary):** the only filled key: a 40px warm-white circle with a night-slate play or pause glyph (inline SVG, 14px) and a 1px engraved border. Hover brightens it to #fffaf0 and a press scales it to 0.94; Space toggles it while the wall is in view. It is never gold.
- **Speed (ghost):** a 3px key with an engraved border, 5px by 8px, reading 1× or 3× in 13px condensed; hover to console ink, press to 0.95.
- **Text toggle:** "Full request" is condensed small caps in faded ink, underlined in sage gray at a 3px offset.
- **Focus:** every control takes a 2px flap-ink outline at a 2px offset; unit rows draw it inside their edge.

### Chips
- **Style:** errands on the call ticket: a 1px engraved outline, 3px corners, 2px by 7px, 12.5px faded ink; a deadline follows in 12px sage gray ("by 1:15 PM").
- **State:** none; chips are read-only.

### Cards / Containers
There are no cards. Containers are equipment:
- **Rail panel:** console slate at 96% over the map, a 1px engraved border, 4px corners and the wall-mount shadow; sections padded 10px by 18px, divided by inner rules.
- **Housings:** housing black, a 1px engraved border and 4px corners. The standings housing pads 18px (14px below) with the board-housing shadow; the message board pads 10px with the wall-mount shadow.
- **Definitions and facts:** unboxed. Terms are condensed caps; facts sit in rows underlined by inner rules, with a 130px term column.

### Inputs / Fields
- **Task select:** pressed-slate fill, a 1px engraved border, 3px corners, padding 5px 26px 5px 9px, 13px console ink, and a drawn chevron in sage gray; hover turns the border sage gray. Tasks are grouped by tier.
- **Replay fader:** a 3px engraved-rule track with a 10 by 20px warm-white fader cap (2px corners).

### Navigation
- **Top strip:** night slate over a 1px engraved rule, sticky, 56px tall with 18px between its parts. The plate (six small flap cells reading LLMUNI) links back to the replay; the question follows in the headline style; the data stamp (run, tasks, version, map date) in 500-weight condensed caps; the nav sits at the right with 22px gaps.
- **Links:** 13px condensed caps tracked 0.12em, sage gray, 8px vertical padding; hover to console ink (150ms). No active underline or fill.
- **Mobile:** at 900px the nav keeps Replay, Standings and Code; at 560px only Code, with the question hidden and the stamp tightened to 11px.
- **Body links:** console ink, underlined in sage gray at a 3px offset; the underline turns console ink on hover. A skip link to the standings appears on focus as a warm-white tab at the top left.

### Split-Flap Cells
The signature. Every value the console posts is a run of real flap cells: two-tone halves (upper leaf over lower leaf, 2px corners), a 1px split line across the middle, and warm-white condensed capitals lifted 9% of the cell height so the split never cuts a crossbar. Cells sit 2px apart. Medium cells are 18 by 30px with 22px characters (15 by 25px with 18px characters at 560px); small cells are 15 by 23px with 17px characters (12 by 20px with 14px characters at 1180px). A value is uppercased and padded or clipped to its width, and a clipped value ends in a middle dot. Changing a value drops the upper leaf and raises the lower one, stepping through the last few glyphs of a fixed drum (space, A to Z, 0 to 9, + - % . : $ / · —): the fall eases in and the landing eases out, within one step of 60 to 90ms. Cells stagger left to right by 11 to 16ms, board rows by 55ms, and a newer value takes over mid-flip. Cells are hidden from assistive technology, and every value has a plain-text twin. Under reduced motion the final value appears at once. On the site, flap characters are always flap ink; on the video's arrivals board a status column may take its lamp color (gold, alert ink, done sage).

### Departure Board
The standings: one row per model, every value a run of medium cells in the standings housing: position, model (16 cells), feasible, vs optimal, impossible, no such store, wrong address, spots impossible, and dollars per task. Column heads are condensed caps at 11.5px in sage gray; a 9 by 4px swatch sits left of the position. Baseline rows follow the ranked models at 62% opacity, with no rank or swatch. The board flips when a quarter of it first scrolls into view and again whenever the mode or difficulty changes.

### Message Board
A housing mounted at the wall's top right, holding one line of 34 small cells that states the headline measurement, with its scope note beneath in 12.5px sage gray, right-aligned and at most 52ch wide. At 900px and below it becomes two rows of 20 cells, broken at the colon.

### Unit Rows and Lamps
Each model is a unit row in the rail: its swatch; its name (Barlow 600, 14px; gold for the optimal plan); its result as a readout (the finish time with the gap to optimal in 12px sage gray, a verdict in alert ink, or "Correct" in done sage); and a lamp. Beneath runs a state line in 12px sage gray that follows the replay ("en route to…", "at…", "arrived 2:17 PM, 2 min late"). Rows are divided by inner rules. The lamp is a ring while the outcome is open and fills at the moment it is decided: gold (the optimal plan has arrived), done sage, alert red, or unlit gray (can't be checked). Hovering or focusing a row dims the other models (to 40% in the list and to about a quarter on the map) and lets its state line wrap; the optimal plan never dims.

### Map Wall Marks
Routes are arcs joining each plan's stops in visiting order, drawn as trails that grow with replay time: models at 3px in their colors, the optimal plan at 5px in gold above them, all with rounded caps and joints. Each moving head is a dot in the route's color (7px radius for the optimal plan, 5px for models) ringed 2px in night slate. Start and meet-up are night-slate dots ringed 2px in console ink, labelled in the readout style with a night-slate outline and set toward the middle of the map. When a plan fails, an alert pages in: a 6px alert-red dot, a 2px ring that contracts from a 31px to a 9px radius and fades to 35% over eight replay minutes, and an alert tag (condensed bold capitals on the alert plate, padded 3px by 6px) naming the model and the failure. Store failures hang below their point; late arrivals stack above the meet-up, 25px apart.

### Failure Bars
One row per model: swatch and name (Barlow 600, 15px) in a 190px column, a 100% bar 18px tall made of flat segments (1px corners, 2px gaps, at least 3px each), and the count of working plans as a readout (26/27) in a 52px column. The legend repeats each fill as a 14 by 10px key with its total; kinds at zero drop to 50%.

### Named Rules
**The Real Flap Rule.** A split-flap value is always real cells, with two-tone halves, a hairline split and warm-white characters that flip through the drum; never a font imitation or an image.

**The Linear Time Rule.** Replay time runs linear, at 6 or 18 replay minutes per second; flaps are fast and mechanical, staggered by column; alerts pulse once and never loop. Under reduced motion, flips land at once and the replay opens on its final state instead of playing.

## Do's and Don'ts

### Do:
- **Do** reserve gold (#f0a500) for the provably optimal plan: its 5px route above every model, its name, its swatch and its lamp.
- **Do** mark failure in red only: alert red (#e5484d) for lamps, dots, rings and closed-store fills; alert ink (#ff8f8a) for failure words.
- **Do** post headline measurements, the standings and the replay clock in real flap cells, each value with a plain-text twin for screen readers.
- **Do** name panels, control groups and columns with engraved labels: Barlow Condensed 600, uppercase, tracked 0.1 to 0.14em, in sage gray (#8d9f98).
- **Do** divide groups with 1px hairlines (#26332f between panels and sections, #1b2624 inside them) instead of boxes.
- **Do** hang panels on the map wall at a 20px inset with the wall-mount shadow, and frame the camera so the routes stay clear of them.
- **Do** theme every browser surface from the palette: a 2px flap-ink focus ring at a 2px offset, a done-sage selection at 32%, slate scrollbars, underlines in sage gray at a 3px offset, tabular numerals.
- **Do** assign the seven unit colors in the run's model order, and draw baselines without color.

### Don't:
- **Don't** use gold or red for a control, link, heading, focus ring or decoration.
- **Don't** show the standings or the headline as a light table or a big-number stat row; they belong on flap boards in dark housings.
- **Don't** put an engraved label above a heading as a kicker; a section title stands alone, with its caption beneath.
- **Don't** add glow or glass: no backdrop blur and no colored halos.
- **Don't** fill a key with color: a pressed key is pressed slate with an ink bar, and the only filled key is the warm-white Play.
- **Don't** loop an alert pulse or add ambient motion; the console moves when replay time runs, a value changes or a key is pressed.
- **Don't** round a panel, housing, switch key or flap cell past 4px.
- **Don't** borrow SFMTA, Muni or BART marks or official styling; LLMuni is independent research.
