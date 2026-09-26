// How plans fail: for each model, what became of its plans on the feasible tasks, as one 100% bar.
import { type Bundle, modelColor, modelName } from "./data";

export const KINDS: { key: string; label: string; members: string[] }[] = [
  { key: "feasible", label: "Works on the timetable", members: ["feasible"] },
  { key: "closed", label: "Arrives at a closed store", members: ["closed"] },
  { key: "late", label: "Misses a deadline or the meet-up", members: ["deadline", "late", "unreachable", "incomplete"] },
  { key: "wrong", label: "Real store, wrong address", members: ["wrong_address"] },
  { key: "invented", label: "Store that doesn't exist", members: ["no_such_store"] },
  { key: "unverifiable", label: "Can't be checked (store missing from OSM or hours unknown)", members: ["unverifiable"] },
  { key: "none", label: "No plan (declined, invalid answer)", members: ["declined", "invalid_json", "invalid_plan"] },
];

export function renderFailures(data: Bundle, mode: string, figure: HTMLElement, legend: HTMLElement) {
  const byModel = data.failures[mode] ?? {};
  const models = data.meta.models.filter((m) => byModel[m]);
  const rows = models.map((m) => {
    const counts = byModel[m];
    const total = Object.values(counts).reduce((a, b) => a + b, 0);
    const parts = KINDS.map((k) => ({ ...k, n: k.members.reduce((a, key) => a + (counts[key] ?? 0), 0) }));
    return { m, total, parts };
  }).sort((a, b) => b.parts[0].n / (b.total || 1) - a.parts[0].n / (a.total || 1));
  figure.innerHTML = rows.map(({ m, total, parts }) => `
    <div class="fail-row" role="listitem">
      <span class="fail-name"><span class="swatch" style="--unit:${modelColor(m, data.meta.models)}"></span>${modelName(m)}</span>
      <span class="fail-bar" role="img" aria-label="${parts.filter((p) => p.n).map((p) => `${p.n} of ${total}: ${p.label}`).join("; ")}">
        ${parts.filter((p) => p.n).map((p) => `<span class="seg seg-${p.key}" style="flex:${p.n}" title="${p.label}: ${p.n} of ${total}"></span>`).join("")}
      </span>
      <span class="fail-count">${parts[0].n}/${total}</span>
    </div>`).join("");
  const totals = KINDS.map((k) => ({ ...k, n: rows.reduce((a, r) => a + r.parts.find((p) => p.key === k.key)!.n, 0) }));
  legend.innerHTML = totals.map((k) => `<li class="${k.n ? "" : "is-zero"}"><span class="key seg-${k.key}"></span>${k.label}<b>${k.n}</b></li>`).join("");
}
