// Types, loaders and formatting for the benchmark's own JSON (written by `llmuni site-data`).

export type XY = [number, number];
export type TimedPoint = [number, number, number]; // lon, lat, minute of the day

export interface Stop {
  category: string;
  name: string;
  at: XY | null;
  arrive: number | null;
  done: number | null;
  failed?: string | null;
  match?: string;
  reason?: string | null;
}

export interface Plan {
  model: string;
  mode: string;
  baseline: boolean;
  status: string;
  kind: string;
  failure: string | null;
  gap: number | null;
  finish: number | null;
  end_arrive: number | null;
  stops: Stop[];
  path?: TimedPoint[];
}

export interface OraclePlan {
  finish: number;
  end_arrive: number | null;
  stops: Stop[];
  path?: TimedPoint[];
}

export interface TaskInfo {
  id: string;
  tier: "easy" | "medium" | "hard";
  weekday: string;
  date: string;
  prompt: string;
  infeasible: boolean;
  reason: string | null;
  start: { label: string; at: XY; depart: number };
  end: { label: string; at: XY; arrive_by: number | null } | null;
  errands: { category: string; brand: string | null; deadline: number | null }[];
}

export interface Summary {
  tasks: number;
  feasible_pct: number | null;
  impossible_plan_pct: number | null;
  unverifiable_pct: number | null;
  mean_gap: number | null;
  median_gap: number | null;
  hallucination_pct: number | null;
  wrong_address_pct?: number | null;
  not_in_osm_pct?: number | null;
  correct_infeasible_pct: number | null;
  false_infeasible_pct: number | null;
  invalid_json_pct: number | null;
  cost_usd: number;
  avg_tokens: number;
  by_tier?: Record<string, Summary>;
}

export interface Results {
  benchmark_version: string;
  n_tasks_by_tier: Record<string, number>;
  per_model: Record<string, Record<string, Summary>>;
  baselines: Record<string, Summary>;
  headline: {
    pct_impossible_best_model_closed_book: number | null;
    best_model_closed_book: string | null;
    best_gap_open_book: number | null;
    best_model_open_book: string | null;
  };
  spend_usd_total?: number;
}

export interface Meta {
  run: string;
  benchmark_version: string;
  osm_date: string;
  gtfs_versions: Record<string, [string, string]>;
  tasks: number;
  tasks_by_tier: Record<string, number>;
  feasible_tasks: number;
  models: string[];
  registry_date: string | null;
  spend_usd_total: number | null;
  routed_hops: [number, number];
  hero_task: string | null;
}

export interface Bundle {
  meta: Meta;
  results: Results;
  tasks: TaskInfo[];
  plans: Record<string, { optimal: OraclePlan | null; optimal_all_sf: OraclePlan | null; plans: Plan[] }>;
  failures: Record<string, Record<string, Record<string, number>>>;
}

export async function loadBundle(): Promise<Bundle> {
  const get = async (name: string) => {
    const res = await fetch(`${import.meta.env.BASE_URL}data/${name}.json`);
    if (!res.ok) throw new Error(`data/${name}.json: HTTP ${res.status}`);
    return res.json();
  };
  const [meta, results, tasks, plans, failures] = await Promise.all(
    ["meta", "results", "tasks", "plans", "failures"].map(get),
  );
  return { meta, results, tasks, plans, failures };
}

// Model identity: display name and a route color that stays clear of gold (optimal) and red (failure).
const MODEL_NAMES: Record<string, string> = {
  "openai/gpt-6-astra": "GPT-6 Astra",
  "anthropic/claude-fable-5.1": "Claude Fable 5.1",
  "google/gemini-3.1-pro-preview": "Gemini 3.1 Pro",
  "x-ai/grok-4.7": "Grok 4.7",
  "deepseek/deepseek-v4-pro-0813": "DeepSeek V4 Pro",
  "qwen/qwen3.8-max-prime": "Qwen 3.8 Max",
  "meta-llama/llama-4-maverick": "Llama 4 Maverick",
  "baseline:greedy": "Greedy baseline",
  "baseline:random": "Random baseline",
  greedy: "Greedy baseline",
  random: "Random baseline",
};
const SERIES = ["#72c3f0", "#e394d6", "#54d1bd", "#a9afff", "#5b8cff", "#9ad36a", "#cdb9a0"];

export function modelName(id: string): string {
  return MODEL_NAMES[id] ?? id.replace(/^.*\//, "").replace(/-/g, " ");
}

export function modelColor(id: string, models: string[]): string {
  const k = models.indexOf(id);
  return k >= 0 ? SERIES[k % SERIES.length] : "#8a9c95";
}

export function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export const MODE_LABEL: Record<string, string> = {
  open_book: "Open book",
  closed_book: "Closed book",
  tool_use: "Travel tool",
};

export const CATEGORY: Record<string, string> = {
  pharmacy: "pharmacy",
  post_office: "post office",
  supermarket: "groceries",
  hardware: "hardware store",
  bank_atm: "bank or ATM",
  library: "library",
  coffee: "coffee",
  bakery: "bakery",
  dry_cleaning: "dry cleaner",
  bookstore: "bookstore",
  florist: "florist",
  bike_shop: "bike shop",
};

/** 13:05 -> "1:05 PM"; the benchmark's prompts speak 12-hour time. */
export function clock(m: number | null | undefined, withSuffix = true): string {
  if (m == null || !Number.isFinite(m)) return "—";
  const total = Math.round(m);
  const h24 = Math.floor(total / 60) % 24;
  const mm = String(total % 60).padStart(2, "0");
  const h12 = h24 % 12 === 0 ? 12 : h24 % 12;
  return withSuffix ? `${h12}:${mm} ${h24 < 12 ? "AM" : "PM"}` : `${h12}:${mm}`;
}

export const pct = (v: number | null | undefined) => (v == null ? "—" : `${Math.round(v)}%`);
export const gap = (v: number | null | undefined) =>
  v == null ? "—" : `+${(v * 100).toFixed(v < 0.1 ? 1 : 0)}%`;

export function dateLabel(iso: string): string {
  const d = new Date(`${iso}T12:00:00`);
  return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}

export function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}
