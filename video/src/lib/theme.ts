// The site's world, carried into the video: matte slate, warm flap ink, gold = optimal, red = failure.
import { loadFont } from "@remotion/fonts";
import { staticFile } from "remotion";

export const C = {
  ground: "#0b1110",
  panel: "#111918",
  panel2: "#172120",
  rule: "#26332f",
  ink: "#ebe8de",
  ink2: "#b9c1bb",
  label: "#8d9f98",
  gold: "#f0a500",
  alert: "#e5484d",
  alertInk: "#ff8f8a",
  ok: "#8fcf9c",
  flapTop: "#1e201d",
  flapBottom: "#191b18",
  flapSplit: "#060706",
  flapInk: "#f3efe2",
};

export const SIGNAGE = "Barlow Condensed";
export const UI = "Barlow";

const MODELS: Record<string, [string, string]> = {
  "openai/gpt-6-astra": ["GPT-6 Astra", "#72c3f0"],
  "anthropic/claude-fable-5.1": ["Claude Fable 5.1", "#e394d6"],
  "google/gemini-3.1-pro-preview": ["Gemini 3.1 Pro", "#54d1bd"],
  "x-ai/grok-4.7": ["Grok 4.7", "#a9afff"],
  "deepseek/deepseek-v4-pro-0813": ["DeepSeek V4 Pro", "#5b8cff"],
  "qwen/qwen3.8-max-prime": ["Qwen 3.8 Max", "#9ad36a"],
  "meta-llama/llama-4-maverick": ["Llama 4 Maverick", "#cdb9a0"],
};

export const modelName = (id: string) => MODELS[id]?.[0] ?? id.replace(/^.*\//, "");

// Short names for narrow flap rows (11 cells).
const SHORT: Record<string, string> = {
  "openai/gpt-6-astra": "GPT-6 Astra", "anthropic/claude-fable-5.1": "Fable 5.1", "google/gemini-3.1-pro-preview": "Gemini 3.1",
  "x-ai/grok-4.7": "Grok 4.7", "deepseek/deepseek-v4-pro-0813": "DeepSeek V4", "qwen/qwen3.8-max-prime": "Qwen 3.8",
  "meta-llama/llama-4-maverick": "Llama 4 Mav",
};
export const shortName = (id: string) => SHORT[id] ?? modelName(id);
export const modelColor = (id: string) => MODELS[id]?.[1] ?? C.label;

export function clock(m: number | null | undefined): string {
  if (m == null) return "—";
  const total = Math.round(m);
  const h24 = Math.floor(total / 60) % 24;
  const h12 = h24 % 12 === 0 ? 12 : h24 % 12;
  return `${h12}:${String(total % 60).padStart(2, "0")} ${h24 < 12 ? "AM" : "PM"}`;
}

for (const [file, family, weight] of [
  ["barlow-condensed-latin-500-normal.woff2", SIGNAGE, "500"],
  ["barlow-condensed-latin-600-normal.woff2", SIGNAGE, "600"],
  ["barlow-condensed-latin-700-normal.woff2", SIGNAGE, "700"],
  ["barlow-latin-400-normal.woff2", UI, "400"],
  ["barlow-latin-500-normal.woff2", UI, "500"],
  ["barlow-latin-600-normal.woff2", UI, "600"],
] as const) {
  loadFont({ family, url: staticFile(`fonts/${file}`), weight, display: "block" });
}
