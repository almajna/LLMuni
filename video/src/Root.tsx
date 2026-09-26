import React from "react";
import { AbsoluteFill, Composition, Sequence, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import hero from "./data/hero.json";

// Shot list (brief section 9), 30 fps, 42 s. The hero task comes from src/data/hero.json (`npm run data`);
// it is a placeholder until the hero pick at Checkpoint 3. The map shots are schematic until the
// map layer is built (remotion-maps); every number is read from the benchmark's own results.
const FPS = 30;
const SHOTS = { title: [0, 90], flyIn: [90, 300], race: [300, 660], finish: [660, 900], stats: [900, 1140], end: [1140, 1260] } as const;
const GOLD = "#eda100", FAIL = "#d03b3b", INK = "#f2f1ec", MUTED = "#7d7c76";
type XY = [number, number];

const fmt = (m: number | null) => (m == null ? "—" : `${Math.floor(m / 60)}:${String(Math.round(m % 60)).padStart(2, "0")}`);

function project(points: XY[], width: number, height: number) {
  const lons = points.map((p) => p[0]), lats = points.map((p) => p[1]);
  const [x0, x1, y0, y1] = [Math.min(...lons), Math.max(...lons), Math.min(...lats), Math.max(...lats)];
  const s = Math.min((width * 0.8) / (x1 - x0 || 1), (height * 0.6) / (y1 - y0 || 1));
  return (p: XY): XY => [width / 2 + (p[0] - (x0 + x1) / 2) * s, height / 2 - (p[1] - (y0 + y1) / 2) * s];
}

const Title: React.FC = () => {
  const f = useCurrentFrame();
  return <AbsoluteFill style={{ background: "#000", color: INK, justifyContent: "center", padding: 80, fontSize: 64, fontWeight: 700,
    opacity: interpolate(f, [0, 15], [0, 1]) }}>I gave AI {hero.meta.tasks === 300 ? 300 : "real"} San Francisco errand days.</AbsoluteFill>;
};

const RouteShot: React.FC<{ reveal: number; showFailures: boolean }> = ({ reveal, showFailures }) => {
  const { width, height } = useVideoConfig();
  const task = hero.task as { start: { at: XY }; end: { at: XY } | null };
  const plans = [{ name: "Optimal", color: GOLD, stops: hero.optimal?.stops ?? [] },
    ...hero.plans.filter((p) => !p.baseline && p.mode === "open_book").slice(0, 4).map((p) => ({ name: p.model.split("/")[1], color: p.status === "feasible" ? INK : FAIL, stops: p.stops }))];
  const all: XY[] = [task.start.at, ...(task.end ? [task.end.at] : []), ...plans.flatMap((p) => p.stops.filter((s) => s.at).map((s) => s.at as XY))];
  const xy = project(all, width, height);
  return <AbsoluteFill style={{ background: "#0b0b0c" }}>
    <svg width={width} height={height}>
      {plans.map((p, i) => {
        const pts = [task.start.at, ...p.stops.filter((s) => s.at).map((s) => s.at as XY)].map(xy);
        const shown = pts.slice(0, Math.max(1, Math.ceil(pts.length * reveal)));
        return <polyline key={i} points={shown.map((q) => q.join(",")).join(" ")} fill="none" stroke={p.color} strokeWidth={i === 0 ? 8 : 4} opacity={i === 0 ? 1 : 0.8} />;
      })}
      {showFailures && hero.plans.flatMap((p) => p.stops.filter((s) => s.failed && s.at)).map((s, i) => {
        const [x, y] = xy(s.at as XY);
        return <g key={i}><circle cx={x} cy={y} r={28} fill={FAIL} opacity={0.7} /><text x={x} y={y - 36} fill={INK} fontSize={28} textAnchor="middle">{String(s.failed).toUpperCase()}</text></g>;
      })}
    </svg>
  </AbsoluteFill>;
};

const Race: React.FC = () => {
  const f = useCurrentFrame();
  return <RouteShot reveal={interpolate(f, [0, SHOTS.race[1] - SHOTS.race[0]], [0, 1], { extrapolateRight: "clamp" })} showFailures={f > 200} />;
};

const Finish: React.FC = () => (
  <AbsoluteFill style={{ background: "#0b0b0c", color: INK, padding: 80, justifyContent: "center", gap: 16, fontSize: 40 }}>
    <div style={{ color: GOLD }}>Optimal · done {fmt(hero.optimal?.finish ?? null)}</div>
    {hero.plans.filter((p) => !p.baseline && p.mode === "open_book").slice(0, 4).map((p) =>
      <div key={p.model} style={{ color: p.status === "feasible" ? INK : FAIL }}>{p.model.split("/")[1]} · {p.status === "feasible" ? `done ${fmt(p.finish)}` : p.status}</div>)}
  </AbsoluteFill>
);

const Stats: React.FC = () => {
  const h = hero.headline;
  const cards = [`${h.pct_impossible_best_model_closed_book ?? "—"}% of the best model's plans were impossible`,
    `Best model: ${h.best_gap_open_book == null ? "—" : Math.round(h.best_gap_open_book * 100)}% slower than optimal`,
    `With a travel-time tool: ${h.best_gap_tool_mode == null ? "—" : Math.round(h.best_gap_tool_mode * 100) + "%"}`];
  const f = useCurrentFrame();
  return <AbsoluteFill style={{ background: "#000", color: INK, padding: 80, justifyContent: "center", gap: 40, fontSize: 52, fontWeight: 700 }}>
    {cards.map((c, i) => <div key={i} style={{ opacity: interpolate(f, [i * 60, i * 60 + 15], [0, 1], { extrapolateRight: "clamp" }) }}>{c}</div>)}
  </AbsoluteFill>;
};

const EndCard: React.FC = () => (
  <AbsoluteFill style={{ background: "#000", color: INK, padding: 80, justifyContent: "center", gap: 12, fontSize: 36 }}>
    {(hero.leaderboard as { model: string; mode: string; feasible_pct: number | null }[]).filter((e) => e.mode === "open_book").slice(0, 5)
      .map((e, i) => <div key={e.model}>{i + 1}. {e.model.split("/").pop()} · {e.feasible_pct ?? "—"}% feasible</div>)}
    <div style={{ color: MUTED, marginTop: 24 }}>github.com/&lt;repo&gt; · LLMuni {hero.meta.benchmark_version}</div>
  </AbsoluteFill>
);

const LLMuni: React.FC = () => (
  <AbsoluteFill style={{ fontFamily: "system-ui, sans-serif" }}>
    <Sequence from={SHOTS.title[0]} durationInFrames={SHOTS.title[1] - SHOTS.title[0]}><Title /></Sequence>
    <Sequence from={SHOTS.flyIn[0]} durationInFrames={SHOTS.flyIn[1] - SHOTS.flyIn[0]}><RouteShot reveal={0} showFailures={false} /></Sequence>
    <Sequence from={SHOTS.race[0]} durationInFrames={SHOTS.race[1] - SHOTS.race[0]}><Race /></Sequence>
    <Sequence from={SHOTS.finish[0]} durationInFrames={SHOTS.finish[1] - SHOTS.finish[0]}><Finish /></Sequence>
    <Sequence from={SHOTS.stats[0]} durationInFrames={SHOTS.stats[1] - SHOTS.stats[0]}><Stats /></Sequence>
    <Sequence from={SHOTS.end[0]} durationInFrames={SHOTS.end[1] - SHOTS.end[0]}><EndCard /></Sequence>
  </AbsoluteFill>
);

export const Root: React.FC = () => (
  <>
    <Composition id="LLMuni-4x5" component={LLMuni} durationInFrames={SHOTS.end[1]} fps={FPS} width={1080} height={1350} />
    <Composition id="LLMuni-16x9" component={LLMuni} durationInFrames={SHOTS.end[1]} fps={FPS} width={1920} height={1080} />
  </>
);
