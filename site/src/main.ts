import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { TripsLayer } from "@deck.gl/geo-layers";
import { ScatterplotLayer, TextLayer } from "@deck.gl/layers";

type XY = [number, number];
interface Stop { category: string; name: string; at: XY | null; arrive: number | null; done: number | null; failed?: string | null; match?: string }
interface Plan { model: string; mode: string; baseline: boolean; status: string; failure: string | null; gap: number | null; finish: number | null; stops: Stop[] }
interface OraclePlan { finish: number; end_arrive: number | null; stops: Stop[] }
interface TaskInfo { id: string; tier: string; weekday: string; prompt: string; infeasible: boolean; reason: string | null;
  start: { label: string; at: XY; depart: number }; end: { label: string; at: XY; arrive_by: number | null } | null }
interface Summary { feasible_pct: number | null; median_gap: number | null; impossible_plan_pct: number | null; hallucination_pct: number | null;
  correct_infeasible_pct: number | null; cost_usd: number; tasks: number; by_tier?: Record<string, Summary> }

const MODES = ["closed_book", "open_book", "tool_use"] as const;
const MODE_LABEL: Record<string, string> = { closed_book: "Closed book", open_book: "Open book", tool_use: "With travel tool" };
const GOLD: [number, number, number] = [237, 161, 0];
const FAIL: [number, number, number] = [208, 59, 59];
const SERIES: [number, number, number][] = [[42, 120, 214], [27, 175, 122], [232, 123, 164], [74, 58, 167], [0, 131, 0], [235, 104, 52], [137, 135, 129]];

const load = (name: string) => fetch(`/data/${name}.json`).then((r) => r.json());
const [meta, results, tasks, plans] = await Promise.all([load("meta"), load("results"), load("tasks"), load("plans")]);
const app = document.getElementById("app")!;
const clock = (m: number | null) => (m == null ? "—" : `${Math.floor(m / 60) % 24}:${String(Math.round(m % 60)).padStart(2, "0")}`);
const pct = (v: number | null) => (v == null ? "—" : `${v.toFixed(0)}%`);
const short = (model: string) => model.replace(/^.*\//, "").replace(/^baseline:/, "");

function route() {
  const [, page, id] = location.hash.split("/");
  if (page === "explore") explorer(id || tasks.find((t: TaskInfo) => !t.infeasible)?.id);
  else leaderboard(new URLSearchParams(location.hash.split("?")[1] ?? "").get("mode") ?? "open_book");
}

function leaderboard(mode: string) {
  const h = results.headline;
  const rows: [string, Summary][] = Object.entries(results.per_model as Record<string, Record<string, Summary>>)
    .filter(([, m]) => m[mode]).map(([name, m]) => [name, m[mode]]);
  if (mode === "open_book") rows.push(...Object.entries(results.baselines as Record<string, Summary>).map(([n, s]) => [`baseline:${n}`, s] as [string, Summary]));
  rows.sort((a, b) => (b[1].feasible_pct ?? -1) - (a[1].feasible_pct ?? -1) || (a[1].median_gap ?? 9) - (b[1].median_gap ?? 9));
  app.innerHTML = `
    <section class="headline">
      <p class="kicker">${meta.run === "final" ? "Results" : `Pilot: ${meta.tasks} tasks`} · ${meta.benchmark_version} · timetable of ${meta.osm_date}</p>
      <div class="stats">
        <div><b>${pct(h.pct_impossible_best_model_closed_book)}</b><span>of the best model's closed-book plans were impossible</span></div>
        <div><b>${h.best_gap_open_book == null ? "—" : `+${Math.round(h.best_gap_open_book * 100)}%`}</b><span>best open-book plan vs optimal (median)</span></div>
        <div><b>${h.best_gap_tool_mode == null ? "—" : `+${Math.round(h.best_gap_tool_mode * 100)}%`}</b><span>with a travel-time tool</span></div>
      </div>
    </section>
    <nav class="tabs">${MODES.map((m) => `<a href="#/?mode=${m}" aria-current="${m === mode}">${MODE_LABEL[m]}</a>`).join("")}</nav>
    <table class="board">
      <thead><tr><th>Model</th><th>Feasible</th><th>Median gap</th><th>Impossible</th><th>Invented stores</th><th>Said "impossible" correctly</th><th>Easy / med / hard</th></tr></thead>
      <tbody>${rows.map(([name, s]) => `<tr class="${name.startsWith("baseline") ? "baseline" : ""}">
        <td>${short(name)}</td><td>${pct(s.feasible_pct)}</td><td>${s.median_gap == null ? "—" : `+${Math.round(s.median_gap * 100)}%`}</td>
        <td>${pct(s.impossible_plan_pct)}</td><td>${pct(s.hallucination_pct)}</td><td>${pct(s.correct_infeasible_pct)}</td>
        <td>${["easy", "medium", "hard"].map((t) => pct(s.by_tier?.[t]?.feasible_pct ?? null)).join(" / ")}</td></tr>`).join("")}</tbody>
    </table>
    <p class="note">Feasible: the plan replays on the real timetable with every store open and every deadline met. Gap: extra time vs the provably optimal plan. n = ${meta.tasks} tasks.</p>`;
}

/** [lon, lat, minute] waypoints: leave the start, travel to each stop, wait there until done, then the end. */
function waypoints(task: TaskInfo, stops: Stop[], endArrive: number | null): [number, number, number][] {
  const pts: [number, number, number][] = [[...task.start.at, task.start.depart]];
  for (const s of stops) {
    if (!s.at || s.arrive == null) break;
    pts.push([...s.at, s.arrive]);
    if (s.done != null) pts.push([...s.at, s.done]);
    if (s.failed) break;
  }
  if (task.end && endArrive != null) pts.push([...task.end.at, endArrive]);
  return pts;
}

let map: maplibregl.Map | null = null;
let overlay: MapboxOverlay | null = null;

function explorer(id: string) {
  const task: TaskInfo = tasks.find((t: TaskInfo) => t.id === id);
  const entry = plans[id];
  const modelPlans: Plan[] = entry.plans.filter((p: Plan) => !p.baseline && p.mode !== "closed_book");
  const optimal: OraclePlan | null = entry.optimal;
  const trips = [
    ...(optimal ? [{ name: "Optimal", color: GOLD, path: waypoints(task, optimal.stops, optimal.end_arrive), width: 7 }] : []),
    ...modelPlans.map((p, i) => ({ name: short(p.model), color: SERIES[i % SERIES.length],
      path: waypoints(task, p.stops, p.status === "feasible" && task.end ? p.finish : null), width: 4 })),
  ];
  const failures = modelPlans.flatMap((p) => p.stops.filter((s) => s.failed && s.at).map((s) => ({ at: s.at!, time: s.arrive!, label: s.failed!.toUpperCase() })));
  const t0 = task.start.depart;
  const t1 = Math.max(...trips.flatMap((t) => t.path.map((w) => w[2])));
  app.innerHTML = `
    <section class="explorer">
      <aside class="panel">
        <select id="task">${tasks.map((t: TaskInfo) => `<option value="${t.id}" ${t.id === id ? "selected" : ""}>${t.id.replace(/^v[\d.]+-/, "")}${t.infeasible ? " (impossible)" : ""}</option>`).join("")}</select>
        <p class="prompt">${task.prompt}</p>
        <ol class="clocks">
          ${optimal ? `<li class="optimal"><span>Optimal</span><b>${clock(optimal.finish)}</b></li>` : ""}
          ${modelPlans.map((p) => `<li class="${p.status}"><span>${short(p.model)}</span><b>${p.status === "feasible" ? clock(p.finish) : p.status}</b></li>`).join("")}
        </ol>
        <div class="scrub"><button id="play" aria-label="Play or pause">Play</button><input id="time" type="range" min="${t0}" max="${t1}" value="${t0}" step="0.5" /><output id="now">${clock(t0)}</output></div>
      </aside>
      <div id="map" class="map" role="img" aria-label="Replay of each model's route across San Francisco"></div>
    </section>`;
  document.getElementById("task")!.addEventListener("change", (e) => (location.hash = `#/explore/${(e.target as HTMLSelectElement).value}`));
  map?.remove();
  map = new maplibregl.Map({ container: "map", style: "https://tiles.openfreemap.org/styles/dark", center: task.start.at, zoom: 12.6, pitch: 55, bearing: -17 });
  map.on("load", () => {
    map!.addLayer({ id: "buildings-3d", type: "fill-extrusion", source: "openmaptiles", "source-layer": "building", minzoom: 12,
      paint: { "fill-extrusion-color": "#2a2a2e", "fill-extrusion-height": ["coalesce", ["get", "render_height"], 8], "fill-extrusion-opacity": 0.8 } });
  });
  overlay = new MapboxOverlay({ layers: [] });
  map.addControl(overlay as unknown as maplibregl.IControl);

  const slider = document.getElementById("time") as HTMLInputElement;
  const now = document.getElementById("now")!;
  let playing = false;
  const draw = (t: number) => {
    now.textContent = clock(t);
    overlay!.setProps({ layers: [
      new TripsLayer({ id: "trips", data: trips, getPath: (d) => d.path.map((w: number[]) => [w[0], w[1]]), getTimestamps: (d) => d.path.map((w: number[]) => w[2]),
        getColor: (d) => d.color, getWidth: (d) => d.width, widthUnits: "pixels", trailLength: 90, currentTime: t, capRounded: true, jointRounded: true }),
      new ScatterplotLayer({ id: "failures", data: failures.filter((f) => t >= f.time), getPosition: (f) => f.at, getFillColor: FAIL,
        getRadius: 60 + 40 * Math.abs(Math.sin(t * 0.8)), radiusUnits: "meters", opacity: 0.8 }),
      new TextLayer({ id: "failure-labels", data: failures.filter((f) => t >= f.time), getPosition: (f) => f.at, getText: (f) => f.label,
        getColor: [255, 255, 255], getSize: 13, getPixelOffset: [0, -22] }),
    ] });
  };
  slider.addEventListener("input", () => draw(Number(slider.value)));
  document.getElementById("play")!.addEventListener("click", () => { playing = !playing; if (playing) tick(); });
  const tick = () => {
    if (!playing) return;
    const t = Number(slider.value) + 0.4;
    slider.value = String(t > t1 ? t0 : t);
    draw(Number(slider.value));
    requestAnimationFrame(tick);
  };
  draw(t0);
}

addEventListener("hashchange", route);
route();
