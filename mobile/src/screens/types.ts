import type { DayType, Plan } from "../api/types";

/** What the Results and Detail screens show: one plan plus where it came from. */
export type ResultsView = { plan: Plan; fromName: string; toName: string; dayType: DayType; time: string; cached: boolean };
