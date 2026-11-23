import type { Card, Tier } from "../api/types";
import type { T } from "../i18n/i18n";

const RANK: Record<Tier, number> = { "No estimate": 0, Low: 1, Medium: 2, High: 3 };

/** A card is only as well evidenced as its weakest leg. */
export function lowestTier(card: Card): Tier {
  return card.legs.reduce<Tier>((worst, leg) => (RANK[leg.tier] < RANK[worst] ? leg.tier : worst), "High");
}

export const isLeaning = (card: Card) => card.legs.some((l) => !l.robust_in_range);

export function robustText(card: Card, t: T): string {
  const r = card.robustness;
  if (!r) return "";
  if (r.status === "finite" && r.gamma_star != null) return t("robust", { n: r.gamma_star.toFixed(1) });
  if (r.status === "beyond_max") return t("robustBeyond", { n: 10 });
  return r.status === "not_applicable" ? t("robustNA") : "";
}

export function cardVia(card: Card, t: T): string {
  if (card.transfers === 0) return t("direct");
  return t(card.transfers === 1 ? "transfer" : "transfers", { n: card.transfers });
}
