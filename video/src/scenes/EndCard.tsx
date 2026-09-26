import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import hero from "../data/hero.json";
import { Flap } from "../lib/Flap";
import { C, SIGNAGE, UI, modelColor, modelName } from "../lib/theme";

// Shot 6: the open-book standings as a departure board, and where to find the benchmark.
export const REPO = "github.com/almajna/LLMuni";

type S = { feasible_pct: number | null; median_gap: number | null };

export const EndCard: React.FC = () => {
  const frame = useCurrentFrame();
  const { width } = useVideoConfig();
  const narrow = width < 1400;
  const results = hero.results as Record<string, Record<string, S>>;
  const rows = Object.entries(results).filter(([, m]) => m.open_book).map(([id, m]) => ({ id, s: m.open_book }))
    .sort((a, b) => (b.s.feasible_pct ?? -1) - (a.s.feasible_pct ?? -1) || (a.s.median_gap ?? 9) - (b.s.median_gap ?? 9))
    .slice(0, 5);
  const cell = narrow ? { w: 24, h: 40, fs: 31 } : { w: 34, h: 54, fs: 42 };
  const meta = hero.meta as { tasks: number; run: string; benchmark_version: string };
  return (
    <AbsoluteFill style={{ background: C.ground, padding: narrow ? "90px 60px" : "80px 140px", justifyContent: "center", alignItems: "center" }}>
      <div style={{ display: "flex", flexDirection: "column", gap: narrow ? 30 : 34 }}>
      <div style={{ fontFamily: SIGNAGE, fontWeight: 600, fontSize: narrow ? 30 : 32, letterSpacing: "0.14em", color: C.label }}>
        STANDINGS · OPEN BOOK · {meta.tasks} TASKS
      </div>
      <div style={{ display: "grid", gap: narrow ? 12 : 14 }}>
        <div style={{ display: "flex", gap: 14, fontFamily: SIGNAGE, fontWeight: 600, fontSize: 22, letterSpacing: "0.14em", color: C.label }}>
          <span style={{ width: 10 + 14 + cell.w }} />
          <span style={{ width: 16 * (cell.w + 4) }}>MODEL</span>
          <span style={{ width: 4 * (cell.w + 4), textAlign: "right" }}>FEASIBLE</span>
          <span style={{ width: 6 * (cell.w + 4), textAlign: "right" }}>VS OPTIMAL</span>
        </div>
        {rows.map((r, i) => (
          <div key={r.id} style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <span style={{ width: 12, height: 4, borderRadius: 1, background: modelColor(r.id), flex: "none" }} />
            <Flap text={String(i + 1)} width={1} start={6 + i * 6} cell={cell} steps={4} stepFrames={2} />
            <Flap text={modelName(r.id)} width={16} start={8 + i * 6} cell={cell} stagger={1} steps={4} stepFrames={2} gap={4} />
            <Flap text={r.s.feasible_pct == null ? "—" : `${Math.round(r.s.feasible_pct)}%`} width={4} align="right" start={14 + i * 6} cell={cell} stagger={1} steps={4} stepFrames={2} gap={4} />
            <Flap text={r.s.median_gap == null ? "—" : `+${(r.s.median_gap * 100).toFixed(1)}%`} width={6} align="right" start={18 + i * 6} cell={cell} stagger={1} steps={4} stepFrames={2} gap={4} />
          </div>
        ))}
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: 16, marginTop: narrow ? 30 : 36,
        opacity: interpolate(frame, [60, 80], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.16, 1, 0.3, 1) }) }}>
        <div style={{ fontFamily: SIGNAGE, fontWeight: 700, fontSize: narrow ? 58 : 64, color: C.ink, letterSpacing: "0.02em" }}>LLMuni</div>
        <div style={{ fontFamily: UI, fontWeight: 500, fontSize: narrow ? 32 : 36, color: C.ink2 }}>{REPO}</div>
      </div>
      <div style={{ fontFamily: UI, fontSize: narrow ? 22 : 24, color: C.label, maxWidth: narrow ? 900 : 1300,
        opacity: interpolate(frame, [70, 90], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>
        {meta.benchmark_version} · {meta.run === "final" ? "final run" : `${meta.run} run`} · every plan replayed on the Muni + BART timetable · independent research, not affiliated with SFMTA or BART
      </div>
      </div>
    </AbsoluteFill>
  );
};
