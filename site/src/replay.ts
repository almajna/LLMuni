// The map wall: one errand day replayed on the real timetable. Every model is a unit with its own clock; the
// optimal plan runs in gold; a plan that reaches a closed store or misses a time pages in as an alert.
import maplibregl from "maplibre-gl";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { TripsLayer } from "@deck.gl/geo-layers";
import { ScatterplotLayer, TextLayer } from "@deck.gl/layers";
import { MAP_STYLE } from "./mapstyle";
import { Flaps } from "./flaps";
import {
  type Bundle, type OraclePlan, type Plan, type TaskInfo, type TimedPoint, type XY,
  CATEGORY, MODE_LABEL, clock, dateLabel, escapeHtml, gap, hexToRgb, modelColor, modelName,
} from "./data";

const GOLD = "#f0a500";
const ALERT: [number, number, number] = [229, 72, 77];
const SPEEDS = [6, 18]; // replay minutes per second
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");

interface Unit {
  id: string;
  name: string;
  color: string;
  optimal: boolean;
  plan: Plan | null;
  oracle: OraclePlan | null;
  path: TimedPoint[];
  row?: HTMLLIElement;
}

interface Alert {
  at: XY;
  time: number;
  label: string;
  stack: number; // labels at nearby places stack instead of overlapping
  atEnd: boolean; // late at the meet-up: stacks above; a failure at a store hangs below its point
}

export class Replay {
  private map: maplibregl.Map;
  private overlay: MapboxOverlay;
  private units: Unit[] = [];
  private alerts: Alert[] = [];
  private task!: TaskInfo;
  private mode = "open_book";
  private t = 0;
  private t0 = 0;
  private t1 = 0;
  private playing = false;
  private speed = 0;
  private last = 0;
  private focus: string | null = null;
  private readonly clockFlaps = new Flaps(8, { align: "right", size: "m" });

  constructor(private readonly data: Bundle, private readonly root: HTMLElement,
              private readonly onChange: (task: string, mode: string) => void) {
    this.map = new maplibregl.Map({
      container: root.querySelector<HTMLElement>(".map")!,
      style: MAP_STYLE,
      center: [-122.43, 37.765],
      zoom: 12.2,
      pitch: 48,
      bearing: -16,
      attributionControl: { compact: true },
      cooperativeGestures: matchMedia("(pointer: coarse)").matches,
    });
    this.overlay = new MapboxOverlay({ layers: [] });
    this.map.addControl(this.overlay as unknown as maplibregl.IControl);
    this.map.addControl(new maplibregl.NavigationControl({ visualizePitch: true, showCompass: true }), "bottom-right");
    root.querySelector(".clock-flaps")!.append(this.clockFlaps.el);
    this.map.once("load", () => this.task && this.frame());
    this.map.on("idle", () => (document.documentElement.dataset.mapIdle = "1")); // tiles drawn: screenshots wait on it
    let pending = 0;
    addEventListener("resize", () => {
      clearTimeout(pending);
      pending = window.setTimeout(() => this.task && this.frame(), 150);
    });
    this.wire();
  }

  private $(sel: string) {
    return this.root.querySelector<HTMLElement>(sel)!;
  }

  private wire() {
    const scrub = this.$(".scrub") as HTMLInputElement;
    scrub.addEventListener("input", () => {
      this.pause();
      this.seek(Number(scrub.value));
    });
    this.$(".play").addEventListener("click", () => (this.playing ? this.pause() : this.play()));
    this.$(".speed").addEventListener("click", () => {
      this.speed = (this.speed + 1) % SPEEDS.length;
      this.$(".speed").textContent = `${this.speed + 1}×`;
      this.$(".speed").setAttribute("aria-label", `Replay speed ${this.speed + 1}×`);
    });
    this.root.querySelectorAll<HTMLButtonElement>(".mode-switch button").forEach((b) =>
      b.addEventListener("click", () => this.onChange(this.task.id, b.dataset.mode!)));
    (this.$(".task-select") as HTMLSelectElement).addEventListener("change", (e) =>
      this.onChange((e.target as HTMLSelectElement).value, this.mode));
    this.$(".request-more").addEventListener("click", () => {
      const open = this.$(".ticket-request").classList.toggle("is-open");
      this.$(".request-more").textContent = open ? "Less" : "Full request";
      this.$(".request-more").setAttribute("aria-expanded", String(open));
    });
    addEventListener("keydown", (e) => {
      if (e.key === " " && document.activeElement === document.body && this.inView()) {
        e.preventDefault();
        this.playing ? this.pause() : this.play();
      }
    });
  }

  private inView() {
    const r = this.root.getBoundingClientRect();
    return r.bottom > 0 && r.top < innerHeight;
  }

  show(taskId: string, mode: string, autoplay = false) {
    const task = this.data.tasks.find((t) => t.id === taskId) ?? this.data.tasks[0];
    const entry = this.data.plans[task.id];
    this.task = task;
    this.mode = mode;
    const reference = mode === "closed_book" ? entry.optimal_all_sf : entry.optimal;
    const models = this.data.meta.models;
    this.units = [
      ...(reference ? [{ id: "optimal", name: "Optimal plan", color: GOLD, optimal: true, plan: null, oracle: reference,
        path: reference.path ?? [] }] : []),
      ...models.map((m) => {
        const plan = entry.plans.find((p) => p.model === m && p.mode === mode && !p.baseline) ?? null;
        return { id: m, name: modelName(m), color: modelColor(m, models), optimal: false, plan, oracle: null,
          path: plan?.path ?? [] };
      }),
    ];
    this.alerts = stack(this.units.flatMap((u) => alertOf(u, task)), task);
    this.t0 = task.start.depart;
    this.t1 = Math.max(this.t0 + 30, ...this.units.flatMap((u) => u.path.map((p) => p[2]))) + 6;
    const scrub = this.$(".scrub") as HTMLInputElement;
    scrub.min = String(this.t0);
    scrub.max = String(this.t1);
    scrub.step = "0.5";
    this.renderTicket();
    this.renderUnits();
    this.root.querySelectorAll<HTMLButtonElement>(".mode-switch button").forEach((b) =>
      b.setAttribute("aria-pressed", String(b.dataset.mode === mode)));
    (this.$(".task-select") as HTMLSelectElement).value = task.id;
    this.frame();
    this.seek(autoplay && !reduceMotion.matches ? this.t0 : this.t1);
    if (autoplay && !reduceMotion.matches) this.play();
  }

  private frame() {
    this.map.resize(); // the container may have been laid out after the map was created
    const pts: XY[] = [this.task.start.at, ...(this.task.end ? [this.task.end.at] : []),
      ...this.units.flatMap((u) => u.path.map((p) => [p[0], p[1]] as XY))];
    const lons = pts.map((p) => p[0]), lats = pts.map((p) => p[1]);
    const bounds: [XY, XY] = [[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]];
    const wide = innerWidth >= 1000;
    // Room for the rail (desktop), the headline plate and the alert labels that stack above the meet-up.
    const pad = wide ? { top: 170, bottom: 80, left: 480, right: 120 } : { top: 200, bottom: 34, left: 34, right: 40 };
    const camera = this.map.cameraForBounds(bounds, { padding: pad, maxZoom: 15, bearing: -16 });
    if (!camera) return;
    this.map.jumpTo({ ...camera, pitch: 48, bearing: -16 });
    // Pitch shrinks the far side and grows the near side, so settle the fit on the projected points themselves.
    const canvas = this.map.getCanvas().getBoundingClientRect();
    const boxW = canvas.width - pad.left - pad.right, boxH = canvas.height - pad.top - pad.bottom;
    for (let i = 0; i < 8 && boxW > 40 && boxH > 40; i++) {
      const q = pts.map((p) => this.map.project(p));
      const x0 = Math.min(...q.map((v) => v.x)), x1 = Math.max(...q.map((v) => v.x));
      const y0 = Math.min(...q.map((v) => v.y)), y1 = Math.max(...q.map((v) => v.y));
      this.map.panBy([(x0 + x1) / 2 - (pad.left + boxW / 2), (y0 + y1) / 2 - (pad.top + boxH / 2)], { animate: false });
      const scale = Math.min(boxW / Math.max(1, x1 - x0), boxH / Math.max(1, y1 - y0));
      if (Math.abs(Math.log2(scale)) < 0.02) break;
      this.map.setZoom(Math.min(15, this.map.getZoom() + Math.log2(scale) * 0.9));
    }
  }

  play() {
    if (this.t >= this.t1) this.seek(this.t0);
    this.playing = true;
    this.$(".play").setAttribute("aria-pressed", "true");
    this.$(".play").setAttribute("aria-label", "Pause the replay");
    this.last = performance.now();
    requestAnimationFrame(this.tick);
  }

  pause() {
    this.playing = false;
    this.$(".play").setAttribute("aria-pressed", "false");
    this.$(".play").setAttribute("aria-label", "Play the replay");
  }

  private tick = (now: number) => {
    if (!this.playing) return;
    const dt = Math.min(0.1, (now - this.last) / 1000);
    this.last = now;
    const next = this.t + dt * SPEEDS[this.speed];
    if (next >= this.t1) {
      this.seek(this.t1);
      this.pause();
      return;
    }
    this.seek(next);
    requestAnimationFrame(this.tick);
  };

  seek(t: number) {
    this.t = Math.max(this.t0, Math.min(this.t1, t));
    (this.$(".scrub") as HTMLInputElement).value = String(this.t);
    const label = clock(this.t);
    if (this.clockFlaps.value !== label) this.clockFlaps.set(label, { stagger: 0, steps: 1, stepMs: 90 });
    this.$(".clock-text").textContent = clock(this.t);
    this.draw();
    this.updateUnits();
  }

  private draw() {
    const t = this.t;
    const visible = this.units.filter((u) => u.path.length > 1);
    const dim = (u: Unit) => (this.focus && this.focus !== u.id && !u.optimal ? 60 : 255);
    const heads = visible.map((u) => ({ u, at: positionAt(u.path, t) })).filter((h) => h.at);
    const live = this.alerts.filter((a) => t >= a.time);
    const canvasW = this.map.getCanvas().clientWidth;
    const side = (at: XY) => (this.map.project(at).x < canvasW / 2 ? "start" : "end");
    const places = [
      { at: this.task.start.at, label: "START" },
      ...(this.task.end ? [{ at: this.task.end.at, label: this.task.end.arrive_by != null ? `MEET BY ${clock(this.task.end.arrive_by)}` : "END" }] : []),
    ];
    this.overlay.setProps({
      // Labels, alerts and markers draw over the routes: at this pitch the depth test would otherwise sort a label
      // hung below its point behind the arcs.
      layers: [
        new TripsLayer<Unit>({
          id: "routes", data: visible.filter((u) => !u.optimal),
          getPath: (u) => u.path.map((p) => [p[0], p[1]] as [number, number]), getTimestamps: (u) => u.path.map((p) => p[2]),
          getColor: (u) => [...hexToRgb(u.color), dim(u)], getWidth: 3, widthUnits: "pixels", widthMinPixels: 2,
          trailLength: 100000, fadeTrail: false, currentTime: t, capRounded: true, jointRounded: true,
          updateTriggers: { getColor: [this.focus] },
        }),
        new TripsLayer<Unit>({
          id: "optimal", data: visible.filter((u) => u.optimal),
          getPath: (u) => u.path.map((p) => [p[0], p[1]] as [number, number]), getTimestamps: (u) => u.path.map((p) => p[2]),
          getColor: () => hexToRgb(GOLD), getWidth: 5, widthUnits: "pixels", trailLength: 100000, fadeTrail: false,
          currentTime: t, capRounded: true, jointRounded: true,
        }),
        new ScatterplotLayer({
          id: "places", data: places, getPosition: (d) => d.at, getRadius: 5, radiusUnits: "pixels",
          getFillColor: [11, 17, 16], getLineColor: [233, 230, 220], lineWidthUnits: "pixels", getLineWidth: 2, stroked: true,
        }),
        new TextLayer({
          id: "place-labels", data: places, parameters: { depthCompare: "always", depthWriteEnabled: false },  getPosition: (d) => d.at, getText: (d) => d.label, getSize: 14,
          getColor: [233, 230, 220], getTextAnchor: (d) => side(d.at), getPixelOffset: (d) => [side(d.at) === "start" ? 10 : -10, -12],
          fontFamily: "Barlow Condensed, sans-serif", fontWeight: 600, updateTriggers: { getTextAnchor: [t], getPixelOffset: [t] },
          outlineWidth: 3, outlineColor: [11, 17, 16, 255], fontSettings: { sdf: true }, characterSet: "auto",
        }),
        new ScatterplotLayer({
          id: "alert-rings", data: live, parameters: { depthCompare: "always", depthWriteEnabled: false },  getPosition: (a) => a.at, radiusUnits: "pixels", stroked: true, filled: false,
          getRadius: (a) => 9 + 22 * Math.max(0, 1 - (t - a.time) / 8), getLineColor: (a) => [...ALERT, Math.round(90 + 165 * Math.max(0, 1 - (t - a.time) / 8))],
          lineWidthUnits: "pixels", getLineWidth: 2, updateTriggers: { getRadius: [t], getLineColor: [t] },
        }),
        new ScatterplotLayer({
          id: "alert-dots", data: live, parameters: { depthCompare: "always", depthWriteEnabled: false },  getPosition: (a) => a.at, getRadius: 6, radiusUnits: "pixels", getFillColor: ALERT,
        }),
        new TextLayer<Alert>({
          id: "alert-labels", data: live, parameters: { depthCompare: "always", depthWriteEnabled: false },  getPosition: (a) => a.at, getText: (a) => a.label, getSize: 16,
          getColor: [255, 236, 234], getPixelOffset: (a) => [side(a.at) === "start" ? 12 : -12, a.atEnd ? -12 - 25 * a.stack : 16 + 25 * a.stack],
          getAlignmentBaseline: (a) => (a.atEnd ? "bottom" : "top"),
          fontFamily: "Barlow Condensed, sans-serif", fontWeight: 700, characterSet: "auto", background: true,
          getBackgroundColor: [150, 32, 36, 235], backgroundPadding: [6, 3, 6, 3], getTextAnchor: (a) => side(a.at),
          updateTriggers: { getTextAnchor: [t], getPixelOffset: [t] },
        }),
        new ScatterplotLayer<{ u: Unit; at: XY | null }>({
          id: "heads", data: heads, getPosition: (h) => h.at!, radiusUnits: "pixels",
          getRadius: (h) => (h.u.optimal ? 7 : 5), getFillColor: (h) => [...hexToRgb(h.u.color), dim(h.u)],
          stroked: true, getLineColor: [11, 17, 16], lineWidthUnits: "pixels", getLineWidth: 2,
          updateTriggers: { getFillColor: [this.focus] },
        }),
      ],
    });
  }

  private renderTicket() {
    const task = this.task;
    const errands = task.errands.map((e) => {
      const what = e.brand ? `${e.brand}` : CATEGORY[e.category] ?? e.category;
      return `<li><span>${escapeHtml(what)}</span>${e.deadline != null ? `<em>by ${clock(e.deadline)}</em>` : ""}</li>`;
    }).join("");
    this.$(".ticket-meta").textContent =
      `${task.tier[0].toUpperCase()}${task.tier.slice(1)} tier · ${dateLabel(task.date)} · ${task.errands.length} errands${task.end ? " and a meet-up" : ""}`;
    const request = this.$(".ticket-request");
    request.textContent = task.prompt;
    request.classList.remove("is-open");
    const more = this.$(".request-more");
    more.hidden = request.scrollHeight <= request.clientHeight + 2;
    more.textContent = "Full request";
    more.setAttribute("aria-expanded", "false");
    this.$(".ticket-errands").innerHTML = errands;
    this.$(".ticket-note").innerHTML = task.infeasible
      ? `<b>Impossible by design.</b> The right answer is to say so${task.reason ? ` (${escapeHtml(task.reason.replace(/_/g, " "))})` : ""}.`
      : `Leaves ${escapeHtml(task.start.label)} at ${clock(task.start.depart)}${task.end ? `; ends at ${escapeHtml(task.end.label)}${task.end.arrive_by != null ? ` by ${clock(task.end.arrive_by)}` : ""}` : ""}.`;
    this.$(".mode-name").textContent = MODE_LABEL[this.mode];
  }

  private renderUnits() {
    const list = this.$(".unit-list");
    list.replaceChildren();
    const cue = () => list.classList.toggle("has-more", list.scrollTop + list.clientHeight < list.scrollHeight - 2);
    list.onscroll = cue;
    requestAnimationFrame(cue);
    const best = this.units.find((u) => u.optimal)?.oracle;
    for (const u of this.units) {
      const li = document.createElement("li");
      li.className = "unit";
      li.dataset.kind = u.optimal ? "optimal" : u.plan?.kind ?? "missing";
      li.style.setProperty("--unit", u.color);
      li.tabIndex = 0;
      li.innerHTML = `<span class="swatch" aria-hidden="true"></span><span class="unit-name">${escapeHtml(u.name)}</span>
        <span class="unit-result">${resultOf(u, best, this.task)}</span><span class="lamp" aria-hidden="true"></span>
        <span class="unit-state"></span>`;
      const focus = (on: boolean) => {
        this.focus = on ? u.id : null;
        list.classList.toggle("focused", on);
        li.classList.toggle("is-focus", on);
        this.draw();
      };
      li.addEventListener("mouseenter", () => focus(true));
      li.addEventListener("mouseleave", () => focus(false));
      li.addEventListener("focus", () => focus(true));
      li.addEventListener("blur", () => focus(false));
      u.row = li;
      list.append(li);
    }
  }

  private updateUnits() {
    for (const u of this.units) {
      const state = u.row?.querySelector(".unit-state");
      if (state) {
        const text = stateOf(u, this.t, this.task);
        if (state.textContent !== text) {
          state.textContent = text;
          u.row!.title = `${u.name}: ${text}`;
        }
      }
      u.row?.setAttribute("data-lamp", lampOf(u, this.t, this.task));
    }
  }
}

/** Status lamp with fixed meanings: live while the outcome is open, then gold (optimal), ok (done on time),
 *  bad (failed) or off (can't be checked). It changes state at the moment the unit's outcome is decided. */
function lampOf(u: Unit, t: number, task: TaskInfo): string {
  if (u.optimal) return u.path.length && t >= u.path[u.path.length - 1][2] ? "gold" : "live";
  const p = u.plan;
  if (!p || u.path.length < 2) return p?.kind === "unverifiable" ? "off" : p?.kind === "declined" && task.infeasible ? "ok" : "bad";
  const failed = p.stops.find((s) => s.failed);
  const decided = failed?.arrive ?? u.path[u.path.length - 1][2];
  if (t < decided) return "live";
  if (p.kind === "feasible") return "ok";
  return p.kind === "unverifiable" ? "off" : "bad";
}

function positionAt(path: TimedPoint[], t: number): XY | null {
  if (path.length === 0 || t < path[0][2]) return path.length ? [path[0][0], path[0][1]] : null;
  const last = path[path.length - 1];
  if (t >= last[2]) return [last[0], last[1]];
  let lo = 0, hi = path.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (path[mid][2] <= t) lo = mid; else hi = mid;
  }
  const a = path[lo], b = path[hi];
  const f = b[2] > a[2] ? (t - a[2]) / (b[2] - a[2]) : 1;
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];
}

function stack(alerts: Alert[], task: TaskInfo): Alert[] {
  const near = (a: XY, b: XY) => Math.abs(a[0] - b[0]) < 0.004 && Math.abs(a[1] - b[1]) < 0.003;
  const placed: Alert[] = [];
  for (const a of alerts.sort((x, y) => x.time - y.time)) {
    // late arrivals stack upwards above the meet-up label (slot 0); store failures hang downwards from their point
    const atEnd = a.atEnd || (!!task.end && near(task.end.at, a.at));
    const sameSide = placed.filter((p) => p.atEnd === atEnd && near(p.at, a.at)).length;
    placed.push({ ...a, atEnd, stack: atEnd ? sameSide + 1 : sameSide });
  }
  return placed;
}

function alertOf(u: Unit, task: TaskInfo): Alert[] {
  const p = u.plan;
  if (!p) return [];
  const failed = p.stops.find((s) => s.failed);
  if (failed?.at && failed.arrive != null) {
    const label = failed.failed === "closed" ? "CLOSED" : failed.failed === "deadline" ? "MISSED DEADLINE" : failed.failed!.toUpperCase();
    return [{ at: failed.at, time: failed.arrive, label: `${modelName(u.id).toUpperCase()} · ${label}`, stack: 0, atEnd: false }];
  }
  if (p.kind === "late" && task.end && p.end_arrive != null) {
    const late = task.end.arrive_by != null ? Math.round(p.end_arrive - task.end.arrive_by) : null;
    return [{ at: task.end.at, time: p.end_arrive, label: `${modelName(u.id).toUpperCase()} · LATE${late ? ` +${late} MIN` : ""}`, stack: 0, atEnd: true }];
  }
  return [];
}

const KIND_TEXT: Record<string, string> = {
  feasible: "Done",
  closed: "Store closed",
  deadline: "Missed a deadline",
  late: "Late",
  unreachable: "Can't get there",
  incomplete: "Errand skipped",
  wrong_address: "Wrong address",
  no_such_store: "No such store",
  unverifiable: "Can't verify",
  invalid_plan: "Invalid plan",
  declined: "Said impossible",
  invalid_json: "No usable answer",
  missing: "No answer",
};

/** The stop behind a plan's verdict: a store that cannot exist outranks an earlier unverifiable one. */
function verdictStop(p: Plan) {
  if (p.kind === "wrong_address") return p.stops.find((s) => s.reason === "wrong_address");
  if (p.kind === "no_such_store") return p.stops.find((s) => s.match === "hallucinated" && s.reason !== "wrong_address");
  return p.stops.find((s) => s.match && s.match !== "matched");
}

const STORE_TEXT: Record<string, string> = {
  wrong_address: "real store, not at that address",
  no_such_store: "in neither OpenStreetMap nor the city registry",
  not_in_osm: "real store OpenStreetMap lacks, hours unknown",
  hours_unknown: "opening hours unknown",
  category_unconfirmed: "mapped as a different kind of store",
  hallucinated: "no such store",
  unverifiable: "can't be checked",
};

const NO_PLAN_TEXT: Record<string, string> = {
  invalid_json: "reply could not be read as a plan, even after one retry",
  declined: "called the day impossible",
  invalid_plan: "skipped or repeated an errand",
};

function resultOf(u: Unit, best: OraclePlan | null | undefined, task: TaskInfo): string {
  if (u.optimal) return u.oracle ? clock(u.oracle.finish) : "—";
  const p = u.plan;
  if (!p) return "—";
  if (p.kind === "feasible") return `${clock(p.finish)} <small>${p.gap != null && p.gap > 0.0005 ? gap(p.gap) : "optimal"}</small>`;
  if (p.kind === "declined" && task.infeasible) return `<span class="ok">Correct</span>`;
  return `<span class="bad">${KIND_TEXT[p.kind] ?? p.kind}</span>`;
}

function stateOf(u: Unit, t: number, task: TaskInfo): string {
  if (!u.optimal && (!u.plan || u.path.length < 2)) {
    const p = u.plan;
    if (!p) return "sent no answer for this task";
    const blocked = verdictStop(p);
    if (blocked) return `${blocked.name}: ${STORE_TEXT[blocked.reason ?? blocked.match ?? ""] ?? "can't be matched"}`;
    return NO_PLAN_TEXT[p.kind] ?? (KIND_TEXT[p.kind] ?? p.kind).toLowerCase();
  }
  const stops = u.optimal ? u.oracle!.stops : u.plan!.stops;
  if (t <= task.start.depart) return `ready at ${task.start.label}`;
  for (const s of stops) {
    if (s.arrive == null) break;
    if (t < s.arrive) return `en route to ${s.name}`;
    if (s.failed && t >= s.arrive) return s.failed === "closed" ? `${s.name} was closed` : `missed the deadline at ${s.name}`;
    if (s.done != null && t < s.done) return `at ${s.name}`;
  }
  const end = u.path[u.path.length - 1][2];
  if (t < end) return task.end ? `en route to ${task.end.label}` : "en route";
  if (u.plan && u.plan.kind === "late" && task.end) {
    const late = task.end.arrive_by != null ? Math.round(end - task.end.arrive_by) : null;
    return `arrived ${clock(end)}${late ? `, ${late} min late` : ""}`;
  }
  if (u.plan && u.plan.kind !== "feasible") {
    const blocked = verdictStop(u.plan);
    if (blocked) return `${blocked.name}: ${STORE_TEXT[blocked.reason ?? blocked.match ?? ""] ?? "can't be matched"}`;
    return NO_PLAN_TEXT[u.plan.kind] ?? (KIND_TEXT[u.plan.kind] ?? u.plan.kind).toLowerCase();
  }
  return task.end ? `arrived ${clock(end)}` : `done ${clock(end)}`;
}
