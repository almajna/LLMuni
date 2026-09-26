import "@fontsource/barlow/400.css";
import "@fontsource/barlow/500.css";
import "@fontsource/barlow/600.css";
import "@fontsource/barlow-condensed/500.css";
import "@fontsource/barlow-condensed/600.css";
import "@fontsource/barlow-condensed/700.css";
import "maplibre-gl/dist/maplibre-gl.css";
import "./styles.css";
import { Board } from "./board";
import { renderFailures } from "./failures";
import { Flaps } from "./flaps";
import { Replay } from "./replay";
import { type Bundle, MODE_LABEL, gap, loadBundle, modelName, pct } from "./data";

interface State {
  task: string;
  mode: string;
  tier: string;
}

const MODE_HELP: Record<string, string> = {
  open_book: "Open book: the request lists candidate stores with their addresses, opening hours and coordinates. The model still has to work out travel times itself.",
  closed_book: "Closed book: the request names only the errands. The model has to know real San Francisco stores, their addresses and their hours.",
};
const TOOL_NOTE = " A third mode, with a travel-time tool, is planned for v2 and was not run in this release.";

const $ = <T extends HTMLElement = HTMLElement>(sel: string) => document.querySelector<T>(sel)!;

async function start() {
  const plate = new Flaps(6, { size: "s" });
  $(".plate").append(plate.el);
  plate.set("LLMUNI", { stagger: 40, steps: 5, stepMs: 60 });

  let data: Bundle;
  try {
    data = await loadBundle();
  } catch (err) {
    document.body.classList.add("is-error");
    $(".lede").textContent = `The results could not be loaded (${(err as Error).message}). Run \`npm run data\` in site/ to export them.`;
    return;
  }
  // deck.gl bakes its label atlas from whatever is loaded when a layer first draws: load the weights it uses.
  await Promise.all([document.fonts.ready, document.fonts.load("700 13px 'Barlow Condensed'"),
    document.fonts.load("600 12px 'Barlow Condensed'")]);

  const m = data.meta;
  $(".stamp").textContent = `${m.run === "final" ? "Final run" : `${m.run[0].toUpperCase()}${m.run.slice(1)} run`} · ${m.tasks} tasks · ${m.benchmark_version} · OSM ${m.osm_date}`;
  const message = new Flaps(34, { size: "s" });
  $(".message").append(message.el);
  const messageRows = [new Flaps(20, { size: "s" }), new Flaps(20, { size: "s" })]; // phones: two rows of 20 cells
  $(".message-rows").append(...messageRows.map((f) => f.el));
  const setMessage = (text: string, delay: number) => {
    message.set(text, { stagger: 16, steps: 4, stepMs: 60, delay });
    const [a, b] = splitLine(text, 20);
    messageRows[0].set(a, { stagger: 16, steps: 4, stepMs: 60, delay });
    messageRows[1].set(b, { stagger: 16, steps: 4, stepMs: 60, delay: delay + 120 });
  };
  const tasks = data.tasks.slice().sort((a, b) => ["easy", "medium", "hard"].indexOf(a.tier) - ["easy", "medium", "hard"].indexOf(b.tier) || a.id.localeCompare(b.id));
  $<HTMLSelectElement>(".task-select").innerHTML = ["easy", "medium", "hard"].map((tier) => `<optgroup label="${tier[0].toUpperCase()}${tier.slice(1)}">${
    tasks.filter((t) => t.tier === tier).map((t) => `<option value="${t.id}">${t.id.replace(/^v[\d.]+-/, "")} · ${t.weekday.slice(0, 3)} · ${t.errands.length} errands${t.infeasible ? " · impossible" : ""}</option>`).join("")
  }</optgroup>`).join("");

  const board = new Board(data, $<HTMLTableElement>(".board"), $(".board-caption"));
  const replay = new Replay(data, $("#replay"), (task, mode) => go({ ...state, task, mode }));
  const hero = data.meta.hero_task && data.plans[data.meta.hero_task] ? data.meta.hero_task : tasks[0].id;
  let state: State = { task: hero, mode: "open_book", tier: "all", ...readHash(data) };
  let boardSeen = false;
  let first = true;

  function readHash(d: Bundle): Partial<State> {
    const q = new URLSearchParams(location.hash.slice(1).replace(/^[^=]*$/, ""));
    const out: Partial<State> = {};
    const task = q.get("task");
    if (task && d.plans[task]) out.task = task;
    else if (task && d.plans[`${d.meta.benchmark_version}-${task}`]) out.task = `${d.meta.benchmark_version}-${task}`;
    if (q.get("mode") && MODE_LABEL[q.get("mode")!]) out.mode = q.get("mode")!;
    if (["all", "easy", "medium", "hard"].includes(q.get("tier") ?? "")) out.tier = q.get("tier")!;
    return out;
  }

  function go(next: State) {
    const params = new URLSearchParams({ task: next.task.replace(`${data.meta.benchmark_version}-`, ""), mode: next.mode, tier: next.tier });
    history.replaceState(null, "", `#${params}`);
    apply(next);
  }

  function apply(next: State) {
    const replayChanged = first || next.task !== state.task || next.mode !== state.mode;
    const boardChanged = first || next.mode !== state.mode || next.tier !== state.tier;
    state = next;
    if (replayChanged) replay.show(state.task, state.mode, first);
    if (boardChanged && boardSeen) board.show(state.mode, state.tier);
    document.querySelectorAll<HTMLButtonElement>("[data-mode]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.mode === state.mode)));
    document.querySelectorAll<HTMLButtonElement>("[data-tier]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.tier === state.tier)));
    $(".mode-help").textContent = (MODE_HELP[state.mode] ?? "") + TOOL_NOTE;
    renderFailures(data, state.mode, $(".fail-figure"), $(".fail-legend"));
    $(".fail-caption").textContent = `${MODE_LABEL[state.mode]}, ${data.meta.feasible_tasks} feasible tasks per model. What became of each plan when it was replayed.`;
    const headline = headlineFor(data, state.mode);
    $(".headline-text").textContent = `${headline.text}. ${headline.note}`;
    setMessage(headline.text, first ? 400 : 0);
    $(".message-note").textContent = headline.note;
    first = false;
  }

  document.querySelectorAll<HTMLButtonElement>(".standings [data-mode]").forEach((b) =>
    b.addEventListener("click", () => go({ ...state, mode: b.dataset.mode! })));
  document.querySelectorAll<HTMLButtonElement>("[data-tier]").forEach((b) =>
    b.addEventListener("click", () => go({ ...state, tier: b.dataset.tier! })));

  new IntersectionObserver((entries, obs) => {
    if (entries.some((e) => e.isIntersecting)) {
      boardSeen = true;
      board.show(state.mode, state.tier);
      obs.disconnect();
    }
  }, { threshold: 0.25 }).observe($(".board-frame"));

  addEventListener("hashchange", () => apply({ ...state, ...readHash(data) }));
  apply(state);
  renderFacts(data);
}

function splitLine(text: string, width: number): [string, string] {
  if (text.length <= width) return [text, ""];
  const cut = text.lastIndexOf(" ", width);
  return cut > 0 ? [text.slice(0, cut), text.slice(cut + 1)] : [text.slice(0, width), text.slice(width)];
}

function headlineFor(data: Bundle, mode: string): { text: string; note: string } {
  const scope = `${data.meta.run === "final" ? "Final run" : `${data.meta.run} run`}, ${data.meta.tasks} tasks.`;
  const rows = Object.entries(data.results.per_model).filter(([, m]) => m[mode]).map(([id, m]) => ({ id, s: m[mode] }));
  if (mode === "closed_book") {
    const best = Math.max(...rows.map((r) => r.s.feasible_pct ?? 0));
    const worked = rows.filter((r) => (r.s.feasible_pct ?? 0) > 0).length;
    return {
      text: best > 0 ? `Closed book: best model ${pct(best)} feasible` : `Closed book: 0 working plans`,
      note: `${worked} of ${rows.length} models produced any plan that works without a store list. ${scope}`,
    };
  }
  const feasible = rows.filter((r) => r.s.median_gap != null).sort((a, b) =>
    (b.s.feasible_pct ?? 0) - (a.s.feasible_pct ?? 0) || (a.s.median_gap ?? 9) - (b.s.median_gap ?? 9));
  const top = feasible[0];
  if (!top) return { text: "No feasible plans yet", note: "" };
  return {
    text: `${modelName(top.id)}: ${pct(top.s.feasible_pct)} feasible, ${gap(top.s.median_gap)}`,
    note: `Top of the open-book standings: ${Math.round(((top.s.feasible_pct ?? 0) / 100) * data.meta.feasible_tasks)} of ${data.meta.feasible_tasks} feasible tasks planned right, median extra time over the optimal plan. ${scope}`,
  };
}

function renderFacts(data: Bundle) {
  const m = data.meta;
  const days = (r: [string, string]) => `${r[0]} to ${r[1]}`;
  const facts: [string, string][] = [
    ["Run", m.run === "final" ? "Final" : `${m.run[0].toUpperCase()}${m.run.slice(1)}`],
    ["Tasks", `${m.tasks} (${Object.entries(m.tasks_by_tier).map(([t, n]) => `${n} ${t}`).join(", ")})`],
    ["Models", `${m.models.length}, plus greedy and random baselines`],
    ["Model spend", m.spend_usd_total != null ? `$${m.spend_usd_total.toFixed(2)} in total` : "—"],
    ["Timetables", Object.entries(m.gtfs_versions).map(([k, v]) => `${k.toUpperCase()} ${days(v)}`).join("; ")],
    ["Map data", `OpenStreetMap, ${m.osm_date}`],
  ];
  $(".run-facts").innerHTML = facts.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join("");
  $(".provenance").textContent = `LLMuni ${m.benchmark_version}. Results from the ${m.run} run over ${m.tasks} tasks; OpenStreetMap of ${m.osm_date}${m.registry_date ? `; business registry of ${m.registry_date}` : ""}.`;
}

start();
