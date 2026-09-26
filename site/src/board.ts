// The standings as a split-flap departure board: one row per model, every value a run of flap cells that
// flips through the drum when the mode or tier changes.
import { Flaps } from "./flaps";
import { type Bundle, type Summary, gap, modelColor, modelName, pct } from "./data";

interface Column {
  key: string;
  label: string;
  width: number;
  align: "left" | "right";
  value: (row: Row) => string;
  sr: (row: Row) => string;
}

interface Row {
  id: string;
  rank: number;
  baseline: boolean;
  s: Summary;
}

const COLUMNS: Column[] = [
  { key: "pos", label: "Pos", width: 2, align: "right", value: (r) => (r.baseline ? "" : String(r.rank)), sr: (r) => (r.baseline ? "baseline" : `rank ${r.rank}`) },
  { key: "model", label: "Model", width: 16, align: "left", value: (r) => modelName(r.id), sr: (r) => modelName(r.id) },
  { key: "feasible", label: "Feasible", width: 4, align: "right", value: (r) => pct(r.s.feasible_pct), sr: (r) => `${pct(r.s.feasible_pct)} feasible` },
  { key: "gap", label: "Vs optimal", width: 6, align: "right", value: (r) => gap(r.s.median_gap), sr: (r) => `median ${gap(r.s.median_gap)} slower than optimal` },
  { key: "impossible", label: "Impossible", width: 4, align: "right", value: (r) => pct(r.s.impossible_plan_pct), sr: (r) => `${pct(r.s.impossible_plan_pct)} impossible plans` },
  { key: "invented", label: "No such store", width: 4, align: "right", value: (r) => pct(r.s.hallucination_pct), sr: (r) => `${pct(r.s.hallucination_pct)} name a store that does not exist` },
  { key: "wrong", label: "Wrong address", width: 4, align: "right", value: (r) => pct(r.s.wrong_address_pct), sr: (r) => `${pct(r.s.wrong_address_pct)} give a wrong address` },
  { key: "calls", label: "Spots impossible", width: 4, align: "right", value: (r) => pct(r.s.correct_infeasible_pct), sr: (r) => `${pct(r.s.correct_infeasible_pct)} of impossible tasks called impossible` },
  { key: "cost", label: "$ / task", width: 5, align: "right", value: (r) => (r.baseline ? "0" : r.s.tasks ? (r.s.cost_usd / r.s.tasks).toFixed(r.s.cost_usd / r.s.tasks < 0.1 ? 3 : 2) : "—"), sr: (r) => (r.baseline ? "free" : `${r.s.tasks ? (r.s.cost_usd / r.s.tasks).toFixed(3) : "—"} dollars per task`) },
];

export class Board {
  private readonly body: HTMLTableSectionElement;
  private readonly rows: { tr: HTMLTableRowElement; lamp: HTMLSpanElement; cells: Flaps[]; sr: HTMLSpanElement[]; line: Flaps }[] = [];
  private readonly caption: HTMLElement;

  constructor(private readonly data: Bundle, table: HTMLTableElement, caption: HTMLElement) {
    this.caption = caption;
    const head = table.createTHead().insertRow();
    for (const c of COLUMNS) {
      const th = document.createElement("th");
      th.scope = "col";
      th.className = `col-${c.key}`;
      th.textContent = c.label;
      head.append(th);
    }
    this.body = table.createTBody();
    const n = data.meta.models.length + Object.keys(data.results.baselines).length;
    for (let i = 0; i < n; i++) {
      const tr = this.body.insertRow();
      const lamp = document.createElement("span");
      lamp.className = "key";
      const line = new Flaps(16, { size: "s" }); // phones: the key numbers under the name
      line.el.classList.add("mline");
      const cells: Flaps[] = [], sr: HTMLSpanElement[] = [];
      COLUMNS.forEach((c, k) => {
        const td = tr.insertCell();
        td.className = `col-${c.key}`;
        if (k === 0) td.append(lamp);
        const flaps = new Flaps(c.width, { align: c.align, size: "m" });
        const hidden = document.createElement("span");
        hidden.className = "sr-only";
        td.append(flaps.el, hidden);
        if (c.key === "model") td.append(line.el);
        cells.push(flaps);
        sr.push(hidden);
      });
      this.rows.push({ tr, lamp, cells, sr, line });
    }
  }

  show(mode: string, tier: string, animate = true) {
    const pick = (s: Summary | undefined) => (s && tier !== "all" ? s.by_tier?.[tier] : s);
    const rows: Row[] = [];
    for (const m of this.data.meta.models) {
      const s = pick(this.data.results.per_model[m]?.[mode]);
      if (s) rows.push({ id: m, rank: 0, baseline: false, s });
    }
    rows.sort((a, b) => (b.s.feasible_pct ?? -1) - (a.s.feasible_pct ?? -1)
      || (a.s.median_gap ?? 9) - (b.s.median_gap ?? 9)
      || (a.s.impossible_plan_pct ?? 101) - (b.s.impossible_plan_pct ?? 101)
      || (a.s.hallucination_pct ?? 101) - (b.s.hallucination_pct ?? 101));
    rows.forEach((r, i) => (r.rank = i + 1));
    if (mode === "open_book") {
      for (const [name, s] of Object.entries(this.data.results.baselines)) {
        const t = pick(s);
        if (t) rows.push({ id: `baseline:${name}`, rank: 0, baseline: true, s: t });
      }
    }
    this.rows.forEach((slot, i) => {
      const row = rows[i];
      slot.tr.hidden = !row;
      slot.tr.classList.toggle("is-baseline", !!row?.baseline);
      slot.tr.classList.toggle("first-baseline", !!row?.baseline && !rows[i - 1]?.baseline);
      slot.lamp.style.setProperty("--unit", row && !row.baseline ? modelColor(row.id, this.data.meta.models) : "transparent");
      COLUMNS.forEach((c, k) => {
        const text = row ? c.value(row) : "";
        slot.cells[k].set(text, animate ? { delay: i * 55, stagger: 11, steps: 4, stepMs: 64 } : { stepMs: 0 });
        slot.sr[k].textContent = row ? c.sr(row) : "";
      });
      const perTask = row && !row.baseline && row.s.tasks ? row.s.cost_usd / row.s.tasks : null; // same precision as the $ column
      const cost = perTask == null ? "" : `$${perTask.toFixed(perTask < 0.1 ? 3 : 2).replace(/^0/, "")}`;
      slot.line.set(row ? `${pct(row.s.feasible_pct)} ${gap(row.s.median_gap)} ${cost}`.trim() : "",
        animate ? { delay: i * 55 + 200, stagger: 11, steps: 3, stepMs: 64 } : { stepMs: 0 });
    });
    const tierTasks = tier === "all" ? this.data.meta.tasks : this.data.meta.tasks_by_tier[tier] ?? 0;
    const feasible = this.data.tasks.filter((t) => (tier === "all" || t.tier === tier) && !t.infeasible).length;
    const noneWork = rows.filter((r) => !r.baseline).every((r) => !r.s.feasible_pct);
    this.caption.textContent = `${tierTasks} tasks (${feasible} feasible, ${tierTasks - feasible} impossible by design)`
      + `${this.data.meta.run === "final" ? " · final run" : ` · ${this.data.meta.run} run`}`
      + (noneWork ? ". No model produced a working plan here, so rows are ordered by fewest impossible plans, then fewest stores that don't exist." : "");
  }
}
