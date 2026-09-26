// Frame-driven split-flap text: each cell steps through a few glyphs of the drum, dropping its upper leaf
// and raising the lower one, exactly as on the site but computed from the frame so renders are deterministic.
import React from "react";
import { useCurrentFrame } from "remotion";
import { C, SIGNAGE } from "./theme";

const DRUM = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+-%.:$/·—";

function drumPath(from: string, to: string, steps: number): string[] {
  const a = Math.max(0, DRUM.indexOf(from));
  const b = DRUM.indexOf(to);
  if (b < 0 || from === to) return from === to ? [] : [to];
  const run: string[] = [];
  for (let k = (a + 1) % DRUM.length; ; k = (k + 1) % DRUM.length) {
    run.push(DRUM[k]);
    if (k === b) break;
  }
  return run.slice(-Math.max(1, steps));
}

function fitText(text: string, width: number, align: "left" | "right" | "center"): string {
  const t = text.toUpperCase();
  const clipped = t.length > width ? t.slice(0, width) : t;
  if (align === "right") return clipped.padStart(width, " ");
  if (align === "center") {
    const left = Math.floor((width - clipped.length) / 2);
    return (" ".repeat(left) + clipped).padEnd(width, " ");
  }
  return clipped.padEnd(width, " ");
}

interface CellSize {
  w: number;
  h: number;
  fs: number;
}

const Half: React.FC<{ ch: string; top: boolean; size: CellSize; rotate?: number; color?: string }> = ({ ch, top, size, rotate, color }) => (
  <div
    style={{
      position: "absolute",
      left: 0,
      right: 0,
      height: size.h / 2,
      top: top ? 0 : size.h / 2,
      overflow: "hidden",
      background: top ? C.flapTop : C.flapBottom,
      borderRadius: top ? "3px 3px 0 0" : "0 0 3px 3px",
      transformOrigin: top ? "50% 100%" : "50% 0%",
      transform: rotate != null ? `rotateX(${rotate}deg)` : undefined,
      backfaceVisibility: "hidden",
    }}
  >
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        height: size.h,
        top: (top ? 0 : -size.h / 2) - Math.round(size.h * 0.09), // lift glyphs so the split never erases a "+" bar
        lineHeight: `${size.h}px`,
        fontSize: size.fs,
        textAlign: "center",
        color: color ?? C.flapInk,
      }}
    >
      {ch}
    </div>
  </div>
);

const Cell: React.FC<{ path: string[]; local: number; stepFrames: number; size: CellSize; color?: string }> = ({ path, local, stepFrames, size, color }) => {
  const n = path.length - 1;
  const k = local < 0 ? 0 : Math.min(n, Math.floor(local / stepFrames));
  const base: React.CSSProperties = { position: "relative", width: size.w, height: size.h, perspective: 400,
    boxShadow: "0 2px 0 #000, 0 3px 6px rgba(0,0,0,0.5)", borderRadius: 3, fontFamily: SIGNAGE, fontWeight: 600 };
  if (k >= n || local < 0) {
    const ch = local < 0 ? path[0] : path[n];
    return (
      <div style={base}>
        <Half ch={ch} top size={size} color={color} />
        <Half ch={ch} top={false} size={size} color={color} />
        <div style={{ position: "absolute", left: 0, right: 0, top: size.h / 2 - 1, height: 2, background: C.flapSplit }} />
      </div>
    );
  }
  const current = path[k], next = path[k + 1];
  const p = (local - k * stepFrames) / stepFrames;
  return (
    <div style={base}>
      <Half ch={next} top size={size} color={color} />
      <Half ch={current} top={false} size={size} color={color} />
      {p < 0.5 ? <Half ch={current} top size={size} rotate={-180 * p} color={color} /> : null}
      {p >= 0.5 ? <Half ch={next} top={false} size={size} rotate={90 - 180 * (p - 0.5)} color={color} /> : null}
      <div style={{ position: "absolute", left: 0, right: 0, top: size.h / 2 - 1, height: 2, background: C.flapSplit, zIndex: 3 }} />
    </div>
  );
};

export const Flap: React.FC<{
  text: string;
  width: number;
  start: number; // frame the flips begin
  cell: CellSize;
  from?: string;
  align?: "left" | "right" | "center";
  stagger?: number;
  steps?: number;
  stepFrames?: number;
  gap?: number;
  color?: string;
}> = ({ text, width, start, cell, from = "", align = "left", stagger = 1, steps = 5, stepFrames = 2, gap = 4, color }) => {
  const frame = useCurrentFrame();
  const target = fitText(text, width, align);
  const before = fitText(from, width, align);
  return (
    <div style={{ display: "flex", gap }}>
      {target.split("").map((ch, i) => (
        <Cell key={i} path={[before[i], ...drumPath(before[i], ch, steps)]} local={frame - start - i * stagger}
              stepFrames={stepFrames} size={cell} color={color} />
      ))}
    </div>
  );
};
