import type { DayType, Example, Plan, StopRef, StretchCollection } from "./types";

export class ApiError extends Error {
  constructor(message: string, readonly offline: boolean) {
    super(message);
  }
}

/** Thin wrapper over the planner's HTTP API (crowd/api/app.py). It computes nothing. */
export function createClient(baseUrl: string) {
  const root = baseUrl.replace(/\/+$/, "");
  async function get<T>(path: string, params: Record<string, string | number> = {}): Promise<T> {
    const query = new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString();
    let res: Response;
    try {
      res = await fetch(`${root}${path}${query ? `?${query}` : ""}`);
    } catch {
      throw new ApiError("network", true);
    }
    if (!res.ok) throw new ApiError(res.statusText, false);
    return (await res.json()) as T;
  }
  return {
    stops: (q: string) => get<StopRef[]>("/stops", { q }),
    examples: () => get<Example[]>("/examples"),
    plan: (from: string, to: string, time: string, day: DayType) =>
      get<Plan>("/plan", { from_stop: from, to_stop: to, time, day }),
    stretches: (route: string, hour: number, day: DayType) =>
      get<StretchCollection>("/operator/stretches", { route, hour, day }),
  };
}
export type Client = ReturnType<typeof createClient>;
