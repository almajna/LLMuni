import React from "react";
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import hero from "../data/hero.json";
import { Flap } from "../lib/Flap";
import { type Camera, type TimedPoint, PLATE, fit, fitTilted, mixCamera, project, toPlate, travelled } from "../lib/geo";
import { C, SIGNAGE, UI, clock, modelColor, modelName, shortName } from "../lib/theme";

// Shots 2-4 on one continuous map: fly in over the city while the request appears as a checklist, race the
// routes on the replay clock (failures page in red), then hold on the arrivals board.
export const FLY = 150; // frames of fly-in
export const RACE = 450; // frames of racing
export const HOLD = 195; // frames on the arrivals board
const HERO_MODEL = "openai/gpt-6-astra"; // Checkpoint 3 pick: late to the meet-up in open book
const MODE = "open_book";
const PERSPECTIVE = 1500;

type Stop = { category: string; name: string; at: number[] | null; arrive: number | null; done: number | null; failed?: string | null; match?: string };
type Plan = { model: string; mode: string; baseline: boolean; kind: string; status: string; finish: number | null; end_arrive?: number | null;
  gap: number | null; stops: Stop[]; path?: number[][] };

interface Unit { id: string; name: string; color: string; optimal: boolean; plan: Plan | null; path: TimedPoint[]; stops: Stop[] }

const task = hero.task as { id: string; weekday: string; prompt: string; start: { label: string; at: number[]; depart: number };
  end: { label: string; at: number[]; arrive_by: number | null } | null; errands: { category: string; brand: string | null; deadline: number | null }[] };
const optimal = hero.optimal as { finish: number; stops: Stop[]; path?: number[][] } | null;
const MODELS = Object.keys(hero.results);

const UNITS: Unit[] = [
  ...(optimal ? [{ id: "optimal", name: "Optimal plan", color: C.gold, optimal: true, plan: null,
    path: (optimal.path ?? []) as TimedPoint[], stops: optimal.stops }] : []),
  ...MODELS.map((m) => {
    const plan = (hero.plans as Plan[]).find((p) => p.model === m && p.mode === MODE && !p.baseline) ?? null;
    return { id: m, name: modelName(m), color: modelColor(m), optimal: false, plan, path: (plan?.path ?? []) as TimedPoint[], stops: plan?.stops ?? [] };
  }),
];

const T0 = task.start.depart;
const T1 = Math.max(T0 + 60, ...UNITS.flatMap((u) => u.path.map((p) => p[2]))) + 4;

const CATEGORY: Record<string, string> = { pharmacy: "Pharmacy", post_office: "Post office", supermarket: "Groceries",
  hardware: "Hardware store", bank_atm: "Bank or ATM", library: "Library", coffee: "Coffee", bakery: "Bakery",
  dry_cleaning: "Dry cleaner", bookstore: "Bookstore", florist: "Florist", bike_shop: "Bike shop" };

interface Alert { at: [number, number]; time: number; text: string; hero: boolean }
const ALERTS: Alert[] = UNITS.flatMap((u) => {
  const p = u.plan;
  if (!p) return [];
  const failed = p.stops.find((s) => s.failed);
  if (failed?.at && failed.arrive != null) {
    const what = failed.failed === "closed" ? "CLOSED" : failed.failed === "deadline" ? "MISSED DEADLINE" : String(failed.failed).toUpperCase();
    return [{ at: toPlate(failed.at[0], failed.at[1]), time: failed.arrive, text: `${u.name} · ${what}`, hero: u.id === HERO_MODEL }];
  }
  if (p.kind === "late" && task.end && p.end_arrive != null) {
    const late = task.end.arrive_by != null ? Math.round(p.end_arrive - task.end.arrive_by) : null;
    return [{ at: toPlate(task.end.at[0], task.end.at[1]), time: p.end_arrive, text: `${u.name} · LATE${late ? ` +${late} MIN` : ""}`, hero: u.id === HERO_MODEL }];
  }
  return [];
}).sort((a, b) => a.time - b.time);

const POINTS: [number, number][] = [toPlate(task.start.at[0], task.start.at[1]), ...(task.end ? [toPlate(task.end.at[0], task.end.at[1])] : []),
  ...UNITS.flatMap((u) => u.path.map((p) => toPlate(p[0], p[1])))];

function bbox(): [number, number, number, number] {
  const xs = POINTS.map((p) => p[0]), ys = POINTS.map((p) => p[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}

function layout(width: number, height: number) {
  const wide = width > height;
  const panel = wide ? { x: width - 600, y: 0, w: 600, h: height } : { x: 0, y: height - 560, w: width, h: 560 };
  const map = wide ? { w: width - 600, h: height } : { w: width, h: height - 560 };
  return { wide, panel, map, cx: map.w / 2, cy: map.h / 2 };
}

function status(u: Unit, t: number): { text: string; tone: "live" | "ok" | "bad" | "gold" } {
  if (!u.optimal && (!u.plan || u.path.length < 2)) return { text: u.plan ? KIND[u.plan.kind] ?? u.plan.kind : "No answer", tone: "bad" };
  if (t <= T0) return { text: `Leaving ${task.start.label}`, tone: "live" };
  for (const s of u.stops) {
    if (s.arrive == null) break;
    if (t < s.arrive) return { text: `To ${s.name}`, tone: "live" };
    if (s.failed) return { text: `${s.failed === "closed" ? "Closed" : "Missed deadline"}: ${s.name}`, tone: "bad" };
    if (s.done != null && t < s.done) return { text: `At ${s.name}`, tone: "live" };
  }
  const end = u.path[u.path.length - 1][2];
  if (t < end) return { text: task.end ? `To ${task.end.label}` : "On the way", tone: "live" };
  if (u.optimal) return { text: `Arrived ${clock(end)}`, tone: "gold" };
  if (u.plan!.kind === "late") return { text: `Late: ${clock(end)}`, tone: "bad" };
  if (u.plan!.kind !== "feasible") return { text: KIND[u.plan!.kind] ?? u.plan!.kind, tone: "bad" };
  return { text: `Arrived ${clock(end)}`, tone: "ok" };
}

const KIND: Record<string, string> = { feasible: "Arrived", closed: "Store closed", deadline: "Missed a deadline", late: "Late",
  wrong_address: "Wrong address", no_such_store: "No such store", unverifiable: "Can't verify", invalid_plan: "Invalid plan",
  declined: "Said impossible", invalid_json: "No usable answer" };

export const MapStory: React.FC = () => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const L = layout(width, height);
  const overview = fit([0, 0, PLATE.w, PLATE.h], L.map.w, L.map.h, 0.02);
  const framed = fit(bbox(), L.map.w, L.map.h, 0.08);
  const target = fitTilted({ ...framed, tilt: 46, bearing: -14 }, POINTS, L.cx, L.cy, L.map.w, L.map.h, PERSPECTIVE, L.wide ? 0.12 : 0.1);
  const drift = fitTilted({ ...target, bearing: -9 }, POINTS, L.cx, L.cy, L.map.w, L.map.h, PERSPECTIVE, L.wide ? 0.11 : 0.09);
  const fly = interpolate(frame, [0, FLY], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.65, 0, 0.35, 1) });
  const drifting = interpolate(frame, [FLY, FLY + RACE + HOLD], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const cam = frame < FLY ? mixCamera(overview, target, fly) : mixCamera(target, drift, drifting);
  const t = interpolate(frame, [FLY, FLY + RACE], [T0, T1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const racing = frame >= FLY;
  const at = (lon: number, lat: number) => project(cam, L.cx, L.cy, PERSPECTIVE, ...toPlate(lon, lat));
  const sw = (px: number) => px / cam.zoom; // screen-constant stroke widths on the scaled plate
  const liveAlerts = racing ? ALERTS.filter((a) => t >= a.time) : [];

  return (
    <AbsoluteFill style={{ background: C.ground, overflow: "hidden" }}>
      <div style={{ position: "absolute", left: 0, top: 0, width: L.map.w, height: L.map.h, overflow: "hidden", perspective: PERSPECTIVE,
        perspectiveOrigin: `${L.cx}px ${L.cy}px` }}>
        <div style={{ position: "absolute", left: L.cx - cam.fx, top: L.cy - cam.fy, width: PLATE.w, height: PLATE.h,
          transformOrigin: `${cam.fx}px ${cam.fy}px`, transform: `rotateX(${cam.tilt}deg) rotateZ(${cam.bearing}deg) scale(${cam.zoom})` }}>
          <Img src={staticFile("basemap.png")} style={{ width: PLATE.w, height: PLATE.h }} />
          <svg width={PLATE.w} height={PLATE.h} style={{ position: "absolute", left: 0, top: 0, overflow: "visible" }}>
            {UNITS.filter((u) => u.path.length > 1 && !u.optimal).map((u) => {
              const pts = racing ? travelled(u.path, t) : [];
              const heroish = u.id === HERO_MODEL;
              return pts.length > 1 ? <polyline key={u.id} points={pts.map((p) => p.join(",")).join(" ")} fill="none" stroke={u.color}
                strokeWidth={sw(heroish ? 5 : 3.2)} strokeLinecap="round" strokeLinejoin="round" opacity={heroish ? 1 : 0.85} /> : null;
            })}
            {UNITS.filter((u) => u.optimal && u.path.length > 1).map((u) => {
              const pts = racing ? travelled(u.path, t) : [];
              return pts.length > 1 ? <polyline key="optimal" points={pts.map((p) => p.join(",")).join(" ")} fill="none" stroke={C.gold}
                strokeWidth={sw(6)} strokeLinecap="round" strokeLinejoin="round" /> : null;
            })}
            {liveAlerts.map((a, i) => {
              const age = t - a.time;
              const ring = sw(10 + 34 * Math.max(0, 1 - age / 10));
              return (
                <g key={i}>
                  <circle cx={a.at[0]} cy={a.at[1]} r={ring} fill="none" stroke={C.alert} strokeWidth={sw(3)} opacity={0.35 + 0.65 * Math.max(0, 1 - age / 10)} />
                  <circle cx={a.at[0]} cy={a.at[1]} r={sw(7)} fill={C.alert} />
                </g>
              );
            })}
            {racing ? UNITS.filter((u) => u.path.length > 1).map((u) => {
              const pts = travelled(u.path, t);
              const head = pts[pts.length - 1];
              return head ? <circle key={`h-${u.id}`} cx={head[0]} cy={head[1]} r={sw(u.optimal ? 9 : 7)} fill={u.color}
                stroke={C.ground} strokeWidth={sw(3)} /> : null;
            }) : null}
          </svg>
        </div>
        <Marker at={at(task.start.at[0], task.start.at[1])} label={`START · ${clock(task.start.depart)}`} show={fly > 0.7} mapW={L.map.w} />
        {task.end ? <Marker at={at(task.end.at[0], task.end.at[1])} label={task.end.arrive_by != null ? `MEET BY ${clock(task.end.arrive_by)}` : "END"} show={fly > 0.7} mapW={L.map.w} /> : null}
        {liveAlerts.map((a, i) => {
          const [x, y] = project(cam, L.cx, L.cy, PERSPECTIVE, a.at[0], a.at[1]);
          const atEnd = !!task.end && Math.hypot(toPlate(task.end.at[0], task.end.at[1])[0] - a.at[0], toPlate(task.end.at[0], task.end.at[1])[1] - a.at[1]) < 60;
          const stack = liveAlerts.slice(0, i).filter((b) => Math.hypot(b.at[0] - a.at[0], b.at[1] - a.at[1]) < 80).length;
          const born = interpolate(t - a.time, [0, 3], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          const top = atEnd ? y - 64 - stack * 40 : y + 46 + stack * 40; // meet-up alerts stack above, store alerts below
          return (
            <div key={i} style={{ position: "absolute", left: Math.max(220, Math.min(L.map.w - 220, x)), top, translate: atEnd ? "-50% -100%" : "-50% 0%", opacity: born,
              scale: interpolate(born, [0, 1], [0.92, 1]), background: a.hero ? C.alert : C.alertPlate, color: C.alertPlateInk, padding: "5px 11px",
              fontFamily: SIGNAGE, fontWeight: 700, fontSize: L.wide ? 26 : 24, letterSpacing: "0.04em", whiteSpace: "nowrap", borderRadius: 3,
              boxShadow: "0 6px 16px rgba(0,0,0,0.5)", textTransform: "uppercase" }}>
              {a.text}
            </div>
          );
        })}
      </div>

      <Panel frame={frame} t={t} L={L} />
    </AbsoluteFill>
  );
};

const Marker: React.FC<{ at: [number, number]; label: string; show: boolean; mapW: number }> = ({ at, label, show, mapW }) => {
  const left = at[0] > mapW * 0.72; // near the right edge the label reads leftwards
  return (
    <div style={{ position: "absolute", left: at[0], top: at[1], opacity: show ? 1 : 0 }}>
      <div style={{ position: "absolute", left: -8, top: -8, width: 16, height: 16, borderRadius: "50%", background: C.ground, border: `3px solid ${C.ink}` }} />
      <div style={{ position: "absolute", left: left ? undefined : 16, right: left ? 16 : undefined, top: -14, whiteSpace: "nowrap", fontFamily: SIGNAGE,
        fontWeight: 600, fontSize: 22, letterSpacing: "0.08em", color: C.ink, textShadow: `0 0 6px ${C.ground}, 0 0 3px ${C.ground}` }}>{label}</div>
    </div>
  );
};

const Panel: React.FC<{ frame: number; t: number; L: ReturnType<typeof layout> }> = ({ frame, t, L }) => {
  const pad = L.wide ? 44 : 40;
  const enter = interpolate(frame, [20, 50], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.16, 1, 0.3, 1) });
  const board = frame >= FLY + RACE;
  const racing = frame >= FLY;
  return (
    <div style={{ position: "absolute", left: L.panel.x, top: L.panel.y, width: L.panel.w, height: L.panel.h, background: "rgba(13, 19, 18, 0.97)",
      borderLeft: L.wide ? `1px solid ${C.rule}` : undefined, borderTop: L.wide ? undefined : `1px solid ${C.rule}`, padding: pad,
      display: "flex", flexDirection: "column", gap: 22, opacity: enter, translate: interpolate(enter, [0, 1], L.wide ? ["40px 0px", "0px 0px"] : ["0px 40px", "0px 0px"]) }}>
      {!racing ? <Ticket frame={frame} wide={L.wide} /> : board ? <Arrivals frame={frame - FLY - RACE} wide={L.wide} /> : <Units t={t} wide={L.wide} />}
    </div>
  );
};

const Ticket: React.FC<{ frame: number; wide: boolean }> = ({ frame, wide }) => (
  <>
    <div style={{ fontFamily: SIGNAGE, fontWeight: 600, fontSize: 22, letterSpacing: "0.14em", color: C.label }}>THE REQUEST · HARD TIER</div>
    <div style={{ fontFamily: UI, fontSize: wide ? 30 : 28, lineHeight: 1.3, color: C.ink }}>
      {task.weekday}, {clock(task.start.depart)}, from {task.start.label}. No car: Muni, BART and walking.
    </div>
    <div style={{ display: "grid", gap: wide ? 14 : 10, gridTemplateColumns: wide ? "1fr" : "1fr 1fr" }}>
      {task.errands.map((e, i) => {
        const on = interpolate(frame, [40 + i * 12, 52 + i * 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.16, 1, 0.3, 1) });
        return (
          <div key={i} style={{ display: "flex", alignItems: "baseline", gap: 14, opacity: on, translate: `${(1 - on) * 16}px 0px`,
            fontFamily: UI, fontSize: wide ? 28 : 25, color: C.ink }}>
            <span style={{ width: 20, height: 20, border: `2px solid ${C.label}`, borderRadius: 3, flex: "none", translate: "0px 3px" }} />
            <span>{e.brand ?? CATEGORY[e.category] ?? e.category}</span>
            {e.deadline != null ? <span style={{ color: C.label, fontSize: wide ? 24 : 22 }}>by {clock(e.deadline)}</span> : null}
          </div>
        );
      })}
      {task.end ? (
        <div style={{ display: "flex", alignItems: "baseline", gap: 14, fontFamily: UI, fontSize: wide ? 28 : 25, color: C.ink,
          opacity: interpolate(frame, [40 + task.errands.length * 12, 52 + task.errands.length * 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>
          <span style={{ width: 20, height: 20, borderRadius: "50%", border: `2px solid ${C.ink}`, flex: "none", translate: "0px 3px" }} />
          <span>Meet at {task.end.label}</span>
          {task.end.arrive_by != null ? <span style={{ color: C.label, fontSize: wide ? 24 : 22 }}>by {clock(task.end.arrive_by)}</span> : null}
        </div>
      ) : null}
    </div>
  </>
);

const Units: React.FC<{ t: number; wide: boolean }> = ({ t, wide }) => (
  <>
    <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
      <div style={{ fontFamily: SIGNAGE, fontWeight: 600, fontSize: 22, letterSpacing: "0.14em", color: C.label }}>OPEN BOOK · SAME TIMETABLE</div>
      <div style={{ fontFamily: SIGNAGE, fontWeight: 600, fontSize: wide ? 56 : 48, color: C.flapInk, letterSpacing: "0.02em" }}>{clock(t)}</div>
    </div>
    <div style={{ display: "grid", gap: wide ? 12 : 10, gridTemplateColumns: wide ? "1fr" : "1fr 1fr", columnGap: 28 }}>
      {UNITS.map((u) => {
        const s = status(u, t);
        return (
          <div key={u.id} style={{ display: "grid", gridTemplateColumns: "26px 1fr", columnGap: 14, alignItems: "center", borderBottom: `1px solid ${C.rule}`, paddingBottom: wide ? 10 : 7 }}>
            <span style={{ width: 26, height: u.optimal ? 8 : 6, borderRadius: 2, background: u.color }} />
            <span style={{ fontFamily: UI, fontWeight: 600, fontSize: wide ? 27 : 24, color: u.optimal ? C.gold : C.ink }}>{u.name}</span>
            <span />
            <span style={{ fontFamily: UI, fontSize: wide ? 21 : 19, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
              color: s.tone === "bad" ? C.alertInk : s.tone === "ok" ? C.ok : s.tone === "gold" ? C.gold : C.label }}>{s.text}</span>
          </div>
        );
      })}
    </div>
  </>
);

const Arrivals: React.FC<{ frame: number; wide: boolean }> = ({ frame, wide }) => {
  const rows = UNITS.map((u) => {
    const end = u.path.length > 1 ? u.path[u.path.length - 1][2] : null;
    const kind = u.optimal ? "optimal" : u.plan?.kind ?? "missing";
    const late = kind === "late" && task.end?.arrive_by != null && end != null ? Math.round(end - task.end.arrive_by) : null;
    const note = kind === "optimal" ? "BEST" : kind === "feasible" ? `+${(Math.round((u.plan!.gap ?? 0) * 1000) / 10).toFixed(1)}%`
      : kind === "late" ? `LATE ${late}` : kind === "deadline" ? "MISSED" : kind === "invalid_json" ? "NO PLAN" : (KIND[kind] ?? kind).toUpperCase().slice(0, 7);
    const time = kind === "optimal" || kind === "feasible" || kind === "late" ? clock(end) : "—";
    return { u, time, note, bad: !["optimal", "feasible"].includes(kind), order: kind === "optimal" ? -1 : end ?? 9999 };
  }).sort((a, b) => (a.bad === b.bad ? a.order - b.order : a.bad ? 1 : -1));
  const cell = wide ? { w: 15, h: 27, fs: 20 } : { w: 21, h: 34, fs: 26 };
  return (
    <>
      <div style={{ fontFamily: SIGNAGE, fontWeight: 600, fontSize: 22, letterSpacing: "0.14em", color: C.label }}>
        ARRIVALS · {task.end ? `${task.end.label.toUpperCase()} · DUE ${clock(task.end.arrive_by)}` : "ALL ERRANDS DONE"}
      </div>
      <div style={{ display: "grid", gap: 10 }}>
        {rows.map((r, i) => (
          <div key={r.u.id} style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ width: 12, height: 4, borderRadius: 1, background: r.u.color, flex: "none" }} />
            <Flap text={wide ? (r.u.optimal ? "Optimal" : shortName(r.u.id)) : r.u.name} width={wide ? 11 : 16} start={i * 4} cell={cell} stagger={1} steps={4} stepFrames={2} gap={2} />
            <Flap text={r.time} width={8} align="right" start={8 + i * 4} cell={cell} stagger={1} steps={4} stepFrames={2} gap={2}
              color={r.u.optimal ? C.gold : undefined} />
            <Flap text={r.note} width={7} align="right" start={14 + i * 4} cell={cell} stagger={1} steps={4} stepFrames={2} gap={2}
              color={r.bad ? C.alertInk : r.u.optimal ? C.gold : C.ok} />
          </div>
        ))}
      </div>
      <div style={{ marginTop: "auto", fontFamily: UI, fontSize: wide ? 22 : 21, color: C.label, lineHeight: 1.35,
        opacity: interpolate(frame, [50, 70], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>
        Every plan replayed on the same Muni and BART timetable. Gold is the provably optimal plan.
      </div>
    </>
  );
};
