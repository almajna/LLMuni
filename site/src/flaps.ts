// Split-flap display: every character is a physical flap cell. Changing a value drops the upper leaf and
// raises the lower one, stepping through a few glyphs of the drum on the way, the way a station board does.

const DRUM = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+-%.:$/·—";
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");

interface Half {
  box: HTMLSpanElement;
  glyph: HTMLSpanElement;
}

function half(className: string): Half {
  const box = document.createElement("span");
  box.className = `half ${className}`;
  const glyph = document.createElement("span");
  glyph.className = "g";
  box.append(glyph);
  return { box, glyph };
}

class Cell {
  readonly el = document.createElement("span");
  private readonly top = half("top");
  private readonly bottom = half("bottom");
  private readonly leafTop = half("top leaf");
  private readonly leafBottom = half("bottom leaf");
  private char = " ";
  private run = 0;

  constructor() {
    this.el.className = "flap";
    this.leafTop.box.hidden = this.leafBottom.box.hidden = true;
    this.el.append(this.top.box, this.bottom.box, this.leafTop.box, this.leafBottom.box);
    this.show(" ");
  }

  private show(ch: string) {
    this.char = ch;
    this.top.glyph.textContent = this.bottom.glyph.textContent = ch;
  }

  /** Flip to `target` after `delay` ms, stepping through at most `steps` drum glyphs. */
  async flip(target: string, delay: number, steps: number, stepMs: number): Promise<void> {
    const token = ++this.run;
    if (target === this.char) return;
    if (reduceMotion.matches || stepMs <= 0) return this.show(target);
    if (delay) await new Promise((r) => setTimeout(r, delay));
    for (const next of path(this.char, target, steps)) {
      if (token !== this.run) return; // a newer value took over mid-flip
      await this.step(next, stepMs);
    }
  }

  private async step(next: string, ms: number) {
    const current = this.char;
    this.top.glyph.textContent = next; // revealed behind the falling leaf
    this.leafTop.glyph.textContent = current;
    this.leafBottom.glyph.textContent = next;
    this.leafTop.box.hidden = this.leafBottom.box.hidden = false;
    const fall = this.leafTop.box.animate([{ transform: "rotateX(0deg)" }, { transform: "rotateX(-90deg)" }],
      { duration: ms * 0.5, easing: "cubic-bezier(0.55, 0, 1, 0.45)", fill: "forwards" });
    await fall.finished.catch(() => undefined);
    const land = this.leafBottom.box.animate([{ transform: "rotateX(90deg)" }, { transform: "rotateX(0deg)" }],
      { duration: ms * 0.5, easing: "cubic-bezier(0, 0.55, 0.45, 1)", fill: "forwards" });
    await land.finished.catch(() => undefined);
    this.bottom.glyph.textContent = next;
    this.char = next;
    this.leafTop.box.hidden = this.leafBottom.box.hidden = true;
    fall.cancel();
    land.cancel();
  }
}

function path(from: string, to: string, steps: number): string[] {
  const a = Math.max(0, DRUM.indexOf(from)), b = DRUM.indexOf(to);
  if (b < 0) return [to];
  const run: string[] = [];
  for (let k = (a + 1) % DRUM.length; ; k = (k + 1) % DRUM.length) {
    run.push(DRUM[k]);
    if (k === b) break;
  }
  return run.slice(-Math.max(1, steps));
}

export interface FlapOptions {
  align?: "left" | "right";
  size?: "s" | "m" | "l";
}

/** A fixed-width run of flap cells showing one value (uppercased, padded or clipped to its width). */
export class Flaps {
  readonly el = document.createElement("span");
  private readonly cells: Cell[] = [];
  private readonly align: "left" | "right";
  private text = "";

  constructor(readonly width: number, opts: FlapOptions = {}) {
    this.align = opts.align ?? "left";
    this.el.className = `flaps flaps-${opts.size ?? "m"}`;
    this.el.setAttribute("aria-hidden", "true");
    for (let i = 0; i < width; i++) {
      const cell = new Cell();
      this.cells.push(cell);
      this.el.append(cell.el);
    }
  }

  get value(): string {
    return this.text;
  }

  /** Show `text`; cells flip left to right, `delay` ms after the call plus `stagger` ms per cell. */
  set(text: string, { delay = 0, stagger = 14, steps = 4, stepMs = 70 } = {}): Promise<void> {
    this.text = text;
    const shown = fit(text.toUpperCase(), this.width, this.align);
    return Promise.all(this.cells.map((cell, i) => cell.flip(shown[i], delay + i * stagger, steps, stepMs))).then(() => undefined);
  }
}

function fit(text: string, width: number, align: "left" | "right"): string {
  const clipped = text.length > width ? text.slice(0, width - 1) + "·" : text;
  return align === "right" ? clipped.padStart(width, " ") : clipped.padEnd(width, " ");
}
