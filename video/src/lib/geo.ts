// The map plate (video/public/basemap.png) and a camera over it. The plate is a Web Mercator image of the
// city; the camera tilts, turns and zooms it with CSS 3D transforms, and `project` repeats the same math so
// labels drawn flat on screen sit exactly over their places on the tilted plate.
import basemap from "../data/basemap.json";

export const PLATE = { w: basemap.width, h: basemap.height };
const merc = (lon: number, lat: number): [number, number] =>
  [(lon * Math.PI) / 180, Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360))];
const [X0, Y0] = merc(basemap.lon0, basemap.lat0);
const [X1, Y1] = merc(basemap.lon1, basemap.lat1);

/** Plate pixel of a lon/lat. */
export function toPlate(lon: number, lat: number): [number, number] {
  const [x, y] = merc(lon, lat);
  return [((x - X0) / (X1 - X0)) * PLATE.w, ((Y1 - y) / (Y1 - Y0)) * PLATE.h];
}

export interface Camera {
  fx: number; // plate pixel under the view centre
  fy: number;
  zoom: number;
  tilt: number; // degrees; the top of the plate recedes
  bearing: number; // degrees, clockwise
}

export function mixCamera(a: Camera, b: Camera, t: number): Camera {
  const lerp = (p: number, q: number) => p + (q - p) * t;
  return {
    fx: lerp(a.fx, b.fx),
    fy: lerp(a.fy, b.fy),
    zoom: Math.exp(lerp(Math.log(a.zoom), Math.log(b.zoom))),
    tilt: lerp(a.tilt, b.tilt),
    bearing: lerp(a.bearing, b.bearing),
  };
}

/** Screen position of a plate pixel for a camera centred at (cx, cy) with CSS perspective `d`. */
export function project(cam: Camera, cx: number, cy: number, d: number, px: number, py: number): [number, number] {
  let x = (px - cam.fx) * cam.zoom;
  let y = (py - cam.fy) * cam.zoom;
  const b = (cam.bearing * Math.PI) / 180;
  [x, y] = [x * Math.cos(b) - y * Math.sin(b), x * Math.sin(b) + y * Math.cos(b)];
  const t = (cam.tilt * Math.PI) / 180;
  const z = y * Math.sin(t);
  const k = d / (d - z);
  return [cx + x * k, cy + y * Math.cos(t) * k];
}

/** Camera that fits a plate-pixel box into a w x h screen area (flat view), with a margin. */
export function fit(box: [number, number, number, number], w: number, h: number, margin = 0.1): Camera {
  const [x0, y0, x1, y1] = box;
  const zoom = Math.min((w * (1 - 2 * margin)) / (x1 - x0), (h * (1 - 2 * margin)) / (y1 - y0));
  return { fx: (x0 + x1) / 2, fy: (y0 + y1) / 2, zoom, tilt: 0, bearing: 0 };
}

export type TimedPoint = [number, number, number];

/** The part of a timed path travelled by minute t, in plate pixels, ending at the interpolated head. */
export function travelled(path: TimedPoint[], t: number): [number, number][] {
  const out: [number, number][] = [];
  for (let i = 0; i < path.length; i++) {
    const [lon, lat, m] = path[i];
    if (m <= t) {
      out.push(toPlate(lon, lat));
      continue;
    }
    if (i > 0) {
      const [lon0, lat0, m0] = path[i - 1];
      const f = m > m0 ? (t - m0) / (m - m0) : 1;
      out.push(toPlate(lon0 + (lon - lon0) * f, lat0 + (lat - lat0) * f));
    }
    break;
  }
  return out;
}

/** Adjust a tilted, turned camera so the given plate points fill a w x h area (centre cx, cy) with a margin. */
export function fitTilted(cam: Camera, points: [number, number][], cx: number, cy: number, w: number, h: number,
                          d: number, margin = 0.08): Camera {
  let c = { ...cam };
  for (let i = 0; i < 6; i++) {
    const proj = points.map(([x, y]) => project(c, cx, cy, d, x, y));
    const xs = proj.map((p) => p[0]), ys = proj.map((p) => p[1]);
    const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    const scale = Math.min((w * (1 - 2 * margin)) / Math.max(1, x1 - x0), (h * (1 - 2 * margin)) / Math.max(1, y1 - y0));
    const dx = (x0 + x1) / 2 - cx, dy = (y0 + y1) / 2 - cy; // screen offset of the points' centre
    const b = (-c.bearing * Math.PI) / 180, t = (c.tilt * Math.PI) / 180;
    const ux = dx / c.zoom, uy = dy / (c.zoom * Math.cos(t));
    c = { ...c, fx: c.fx + ux * Math.cos(b) - uy * Math.sin(b), fy: c.fy + ux * Math.sin(b) + uy * Math.cos(b),
          zoom: c.zoom * Math.pow(scale, 0.8) };
  }
  return c;
}
