export type Level = { code: 0 | 1 | 2 | 3; word: string; glyph: string };
export type Tier = "High" | "Medium" | "Low" | "No estimate";
export type DayType = "weekday" | "weekend";

export type Stretch = {
  hour: number; minutes: number; tier: Tier; robust_in_range: boolean; shares: number[];
  flow: number; pi: number; stretch_id: number; level: Level; coords: [number, number][];
};
export type Leg = {
  route: string; from: string; to: string; board: string; alight: string; minutes: number;
  level: Level; tier: Tier; robust_in_range: boolean; stretches: Stretch[];
};
export type Robustness = { gamma_star: number | null; status: string; note: string };
export type Card = {
  title: string; depart: string; arrive: string; minutes: number; adjusted_minutes: number;
  transfers: number; walk_minutes: number; level: Level; partly_estimated: boolean;
  legs: Leg[]; robustness?: Robustness;
};
export type LaterRow = {
  offset: number; depart: string; routes: string[]; level_code: 0 | 1 | 2 | 3;
  partly_estimated: boolean; arrives_later_by: number; advantage_min: number; holds: boolean;
};
export type LaterChip = { offset: number; depart: string; arrives_later_by: number };
export type Compared = { routes: string[]; level: Level; minutes: number; partly_estimated: boolean };

export type Plan = {
  query: { from: string; to: string; time: string; day_type: DayType };
  period: string;
  cards: { fastest?: Card; comfortable?: Card };
  message: string | null;
  compared: Compared | null;
  leave_later: { chip: LaterChip | null; offsets: LaterRow[] };
  evidence: { route_switch_ratio: number };
};

export type StopRef = { stop_id: string; name: string; lat: number; lon: number };
export type Example = { from: StopRef; to: StopRef; time: string };

export type StretchFeature = {
  properties: { stretch_id: number; level: Level; flow: number; pi: number };
  geometry: { coordinates: [number, number][] };
};
export type StretchCollection = { features: StretchFeature[] };

/** What the app remembers about the last successful plan, so it can be shown without a connection. */
export type SavedResult = { plan: Plan; fromName: string; toName: string; dayType: DayType; time: string };
