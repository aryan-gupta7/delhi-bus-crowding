import { View } from "react-native";
import type { Card as CardData } from "../api/types";
import { cardVia, isLeaning, lowestTier, robustText } from "../lib/plan";
import { useApp } from "../state/AppState";
import { Badge } from "./Badge";
import { Button } from "./Button";
import { Card } from "./Card";
import { LevelPill } from "./LevelPill";
import { RouteChip } from "./RouteChip";
import { Text } from "./Text";

type Props = { card: CardData; picked: boolean; onDetails: () => void };

export function OptionCard({ card, picked, onDetails }: Props) {
  const { t } = useApp();
  const leaning = isLeaning(card);
  const last = card.legs[card.legs.length - 1];
  const marks = (
    <>
      {leaning ? <Badge kind="leans" label={t("leans")} /> : null}
      {card.partly_estimated ? <Badge label={t("partly")} /> : null}
    </>
  );
  return (
    <Card variant={picked ? "picked" : "plain"} style={{ gap: 10 }}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
        <View style={{ flexDirection: "row", gap: 6, flexWrap: "wrap", flex: 1 }}>{card.legs.map((l, i) => <RouteChip key={i} route={l.route} />)}</View>
        <Badge kind={picked ? "accent" : "plain"} label={t(picked ? "comfortable" : "fastest")} />
      </View>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
        <LevelPill level={card.level.code} tier={lowestTier(card)} size="lg" />
        <Text size={28} medium>{Math.round(card.minutes)} <Text tone="sec" size={15}>{t("min")}</Text></Text>
      </View>
      <Text tone="sec" size={14}>{card.legs[0].from} → {last.to}, {cardVia(card, t)} {card.depart}–{card.arrive}</Text>
      <View style={{ flexDirection: "row", gap: 6, flexWrap: "wrap" }}>{marks}</View>
      {card.robustness ? (
        <View style={{ flexDirection: "row", gap: 8, alignItems: "flex-start" }}>
          <Badge label={leaning ? t("leans") : t("firm")} />
          <Text tone="sec" size={13} style={{ flex: 1 }}>{robustText(card, t)}</Text>
        </View>
      ) : null}
      <Button kind="quiet" label={t("details")} onPress={onDetails} style={{ alignSelf: "flex-start", paddingHorizontal: 0 }} />
    </Card>
  );
}
