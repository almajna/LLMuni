import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Flap } from "../lib/Flap";
import { C, SIGNAGE, UI } from "../lib/theme";

// Shot 1: a departure board flips to the question; one line of setup underneath.
export const Title: React.FC<{ models: number }> = ({ models }) => {
  const frame = useCurrentFrame();
  const { width } = useVideoConfig();
  const narrow = width < 1400;
  const cell = narrow ? { w: 64, h: 100, fs: 78 } : { w: 84, h: 132, fs: 104 };
  const out = interpolate(frame, [92, 105], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ background: C.ground, alignItems: "center", justifyContent: "center", gap: narrow ? 26 : 34, opacity: out }}>
      <div style={{ display: "grid", gap: narrow ? 12 : 16, justifyItems: "center" }}>
        <Flap text="CAN AI" width={narrow ? 8 : 12} align="center" start={4} cell={cell} stagger={2} steps={6} stepFrames={2} gap={narrow ? 6 : 8} />
        <Flap text="RIDE MUNI?" width={narrow ? 11 : 12} align="center" start={16} cell={cell} stagger={2} steps={6} stepFrames={2} gap={narrow ? 6 : 8} />
      </div>
      <div
        style={{
          fontFamily: UI,
          fontWeight: 500,
          fontSize: narrow ? 34 : 38,
          color: C.ink2,
          textAlign: "center",
          maxWidth: narrow ? 880 : 1300,
          lineHeight: 1.3,
          opacity: interpolate(frame, [48, 64], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.16, 1, 0.3, 1) }),
          translate: interpolate(frame, [48, 64], ["0px 14px", "0px 0px"], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(0.16, 1, 0.3, 1) }),
        }}
      >
        I gave {models} frontier AI models real San Francisco errand days on{" "}
        <span style={{ fontFamily: SIGNAGE, fontWeight: 600, color: C.ink, letterSpacing: "0.02em" }}>Muni</span>,{" "}
        <span style={{ fontFamily: SIGNAGE, fontWeight: 600, color: C.ink, letterSpacing: "0.02em" }}>BART</span> and foot.
      </div>
    </AbsoluteFill>
  );
};
