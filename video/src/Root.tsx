import React from "react";
import { AbsoluteFill, Composition, Folder, Sequence } from "remotion";
import hero from "./data/hero.json";
import { EndCard } from "./scenes/EndCard";
import { FLY, HOLD, MapStory, RACE } from "./scenes/MapStory";
import { CARD, Stats } from "./scenes/Stats";
import { Title } from "./scenes/Title";
import { C } from "./lib/theme";

// Shot list (brief section 9), 30 fps. Every number on screen is read from video/src/data/hero.json, which
// `llmuni site-data` writes from the benchmark's own results; the hero task is config.yaml site.hero_task.
const FPS = 30;
const TITLE = 105;
const MAP = FLY + RACE + HOLD;
const STATS = 3 * CARD;
const END = 150;
export const DURATION = TITLE + MAP + STATS + END;

const models = Object.keys(hero.results).length;

export const LLMuni: React.FC = () => (
  <AbsoluteFill style={{ background: C.ground }}>
    <Sequence name="Title" durationInFrames={TITLE}><Title models={models} /></Sequence>
    <Sequence name="Map: fly-in, race, arrivals" from={TITLE} durationInFrames={MAP}><MapStory /></Sequence>
    <Sequence name="Stat cards" from={TITLE + MAP} durationInFrames={STATS}><Stats /></Sequence>
    <Sequence name="End card" from={TITLE + MAP + STATS} durationInFrames={END}><EndCard /></Sequence>
  </AbsoluteFill>
);

export const Root: React.FC = () => (
  <>
    <Composition id="LLMuni-4x5" component={LLMuni} durationInFrames={DURATION} fps={FPS} width={1080} height={1350} />
    <Composition id="LLMuni-16x9" component={LLMuni} durationInFrames={DURATION} fps={FPS} width={1920} height={1080} />
    <Folder name="Scenes">
      <Composition id="Title" component={() => <Title models={models} />} durationInFrames={TITLE} fps={FPS} width={1920} height={1080} />
      <Composition id="MapStory" component={MapStory} durationInFrames={MAP} fps={FPS} width={1920} height={1080} />
      <Composition id="Stats" component={Stats} durationInFrames={STATS} fps={FPS} width={1920} height={1080} />
      <Composition id="EndCard" component={EndCard} durationInFrames={END} fps={FPS} width={1920} height={1080} />
    </Folder>
  </>
);
