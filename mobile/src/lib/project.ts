export type Pt = [number, number];

/** Equirectangular projection of lon/lat points into a width x height box, keeping the aspect ratio. */
export function projector(all: Pt[], width: number, height: number, pad = 24) {
  const lats = all.map((p) => p[1]);
  const k = Math.cos((((Math.min(...lats) + Math.max(...lats)) / 2) * Math.PI) / 180);
  const xs = all.map((p) => p[0] * k), ys = all.map((p) => -p[1]);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const scale = Math.min((width - 2 * pad) / Math.max(x1 - x0, 1e-9), (height - 2 * pad) / Math.max(y1 - y0, 1e-9));
  const offX = (width - scale * (x1 - x0)) / 2, offY = (height - scale * (y1 - y0)) / 2;
  return ([lon, lat]: Pt): [number, number] => [offX + scale * (lon * k - x0), offY + scale * (-lat - y0)];
}
