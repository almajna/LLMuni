import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import hero from "../data/hero.json";
import { Flap } from "../lib/Flap";
import { C, SIGNAGE, UI, modelName } from "../lib/theme";

// Shot 5: three measurements, each a flap board line with its source underneath. Tool mode was not run in
// this release (it is the optional v2 step), so the third card reports store hallucinations instead.
export const CARD = 70;

const IMPOSSIBLE = new Set(["closed", "deadline", "late", "unreachable", "incomplete", "wrong_address", "no_such_store", "invalid_plan"]);
const NO_PLAN = new Set(["declined", "invalid_json"]);

function closedBook() {
  const byModel = (hero.failures as Record<string, Record<string, Record<string, number>>>).closed_book ?? {};
  let plans = 0, impossible = 0, stores = 0;
  for (const counts of Object.values(byModel)) {
    for (const [kind, n] of Object.entries(counts)) {
      if (NO_PLAN.has(kind)) continue;
      plans += n;
      if (IMPOSSIBLE.has(kind)) impossible += n;
      if (kind === "wrong_address" || kind === "no_such_store") stores += n;
    }
  }
  return { plans, impossible, stores };
}

export function statCards(): { big: string; line: string; source: string }[] {
  const cb = closedBook();
  const h = hero.headline as { best_gap_open_book: number | null; best_model_open_book: string | null };
  const pct = (a: number, b: number) => (b ? Math.round((100 * a) / b) : 0);
  const n = hero.meta.tasks as number;
  return [
    { big: `${pct(cb.impossible, cb.plans)}%`, line: "of AI plans were impossible",
      source: `Closed book (no store list): closed stores, missed times, wrong addresses, invented stores. ${cb.plans} plans, ${n} tasks.` },
    { big: h.best_gap_open_book != null ? `+${(h.best_gap_open_book * 100).toFixed(1)}%` : "—", line: "slower than optimal, at best",
      source: `${h.best_model_open_book ? modelName(h.best_model_open_book) : "Best model"}, open book: median extra time over the provably optimal plan.` },
    { big: `${pct(cb.stores, cb.plans)}%`, line: "sent you to a store that isn't there",
      source: "Closed book: a real store at the wrong address, or one found in neither OpenStreetMap nor the city's business registry." },
  ];
}

export const Stats: React.FC = () => {
  const frame = useCurrentFrame();
  const { width } = useVideoConfig();
  const narrow = width < 1400;
  const cards = statCards();
  const k = Math.min(cards.length - 1, Math.floor(frame / CARD));
  const local = frame - k * CARD;
  const card = cards[k];
  const prev = k > 0 ? cards[k - 1] : null;
  const cell = narrow ? { w: 70, h: 112, fs: 88 } : { w: 88, h: 140, fs: 112 };
  const fade = (a: number, b: number) => interpolate(local, [a, b], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.16, 1, 0.3, 1) });
  return (
    <AbsoluteFill style={{ background: C.ground, alignItems: "center", justifyContent: "center", gap: narrow ? 28 : 34, padding: narrow ? 70 : 120,
      opacity: interpolate(frame, [cards.length * CARD - 12, cards.length * CARD], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>
      <Flap text={card.big} from={prev?.big ?? ""} width={6} align="center" start={k * CARD + 2} cell={cell} stagger={1} steps={6} stepFrames={2} gap={narrow ? 6 : 8} />
      <div style={{ fontFamily: SIGNAGE, fontWeight: 600, fontSize: narrow ? 64 : 76, color: C.ink, textAlign: "center", lineHeight: 1.05,
        letterSpacing: "0.01em", textTransform: "uppercase", opacity: fade(10, 24), translate: `0px ${(1 - fade(10, 24)) * 12}px` }}>{card.line}</div>
      <div style={{ fontFamily: UI, fontSize: narrow ? 28 : 30, color: C.label, textAlign: "center", maxWidth: narrow ? 860 : 1180, lineHeight: 1.35,
        opacity: fade(22, 36) }}>{card.source}</div>
    </AbsoluteFill>
  );
};
