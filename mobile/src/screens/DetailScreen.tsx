import { useState } from "react";
import { ScrollView, View } from "react-native";
import { Card } from "../components/Card";
import { LeaveLater } from "../components/LeaveLater";
import { LevelPill } from "../components/LevelPill";
import { RouteChip } from "../components/RouteChip";
import { ScreenHeader } from "../components/ScreenHeader";
import { SegmentTip } from "../components/SegmentTip";
import { Strip } from "../components/Strip";
import { Text } from "../components/Text";
import { lowestTier } from "../lib/plan";
import { useApp } from "../state/AppState";
import type { ResultsView } from "./types";

type Props = { view: ResultsView; cardKey: "fastest" | "comfortable"; initialOffset?: number; onBack: () => void };

export function DetailScreen({ view, cardKey, initialOffset = 0, onBack }: Props) {
  const { t } = useApp();
  const card = view.plan.cards[cardKey];
  const [open, setOpen] = useState<{ leg: number; stretch: number } | null>(null);
  if (!card) return null;
  return (
    <View style={{ flex: 1 }}>
      <ScreenHeader title={t(cardKey === "fastest" ? "fastest" : "comfortable")} subtitle={`${card.depart}–${card.arrive}`} onBack={onBack} />
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 120, gap: 12 }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
          <LevelPill level={card.level.code} tier={lowestTier(card)} size="lg" />
          <Text size={22} medium>{Math.round(card.minutes)} <Text tone="sec" size={14}>{t("min")}</Text></Text>
        </View>
        {card.legs.map((leg, li) => {
          const hour = leg.stretches[0]?.hour ?? 0;
          const chosen = open?.leg === li ? leg.stretches[open.stretch] : null;
          return (
            <Card key={li} style={{ gap: 8 }}>
              <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
                <RouteChip route={leg.route} />
                <Text size={13} medium tone="sec" style={{ flex: 1 }}>{t("alongRide", { h: String(hour).padStart(2, "0") })}</Text>
              </View>
              <Strip leg={leg} selected={open?.leg === li ? open.stretch : null} onSelect={(i) => setOpen({ leg: li, stretch: i })} />
              {chosen && open ? <SegmentTip stretch={chosen} index={open.stretch} /> : null}
              <Text tone="mut" size={12}>{t("hatchedKey")}</Text>
            </Card>
          );
        })}
        <Card>{view.plan.leave_later ? <LeaveLater later={view.plan.leave_later} initialOffset={initialOffset} /> : null}</Card>
        <Text tone="mut" size={12}>{t("usually", { period: view.plan.period })}</Text>
      </ScrollView>
    </View>
  );
}
