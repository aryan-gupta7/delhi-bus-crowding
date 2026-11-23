import { ScrollView, View } from "react-native";
import Svg, { Circle, Path } from "react-native-svg";
import { Badge } from "../components/Badge";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { LevelPill } from "../components/LevelPill";
import { OptionCard } from "../components/OptionCard";
import { RouteChip } from "../components/RouteChip";
import { ScreenHeader } from "../components/ScreenHeader";
import { Text } from "../components/Text";
import { useApp } from "../state/AppState";
import { useTheme } from "../theme/ThemeProvider";
import { radius } from "../theme/tokens";
import { Pressable } from "react-native";
import type { ResultsView } from "./types";

type Props = { view: ResultsView; onBack: () => void; onDetails: (key: "fastest" | "comfortable", offset?: number) => void; onAbout: () => void };

export function ResultsScreen({ view, onBack, onDetails, onAbout }: Props) {
  const { t } = useApp();
  const { palette } = useTheme();
  const { plan } = view;
  const cards = plan.cards;
  const count = Object.keys(cards).length;
  const chip = plan.leave_later?.chip ?? null;
  const rough = plan.query.day_type === "weekend" ? ` ${t("roughWeekend")}` : "";
  const footer = `${t("usually", { period: plan.period })} ${t(plan.query.day_type === "weekend" ? "basisWeekend" : "basisWeekday")}${rough} ${t("sample")}`;

  return (
    <View style={{ flex: 1 }}>
      <ScreenHeader title={t("fromTo", { from: view.fromName, to: view.toName })} subtitle={count ? t("optionsFor", { n: count, day: t(`day_${plan.query.day_type}`), time: plan.query.time }) : undefined} onBack={onBack} />
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 120, gap: 12 }}>
        {view.cached ? <Badge label={t("lastResult")} /> : null}
        {count === 0 ? (
          <Card variant="dashed"><Text size={20} medium>{t("noService")}</Text></Card>
        ) : cards.comfortable && cards.fastest ? (
          <>
            <OptionCard card={cards.fastest} picked={false} onDetails={() => onDetails("fastest")} />
            <OptionCard card={cards.comfortable} picked onDetails={() => onDetails("comfortable")} />
          </>
        ) : (
          <>
            <Card variant="dashed" style={{ gap: 6 }}>
              <Text size={24} display accessibilityRole="header">{t("noCalmer")}</Text>
              <Text tone="sec" size={14}>{t("noCalmerWhy", { r: (plan.evidence?.route_switch_ratio ?? 1.6).toFixed(1) })}</Text>
              <Button kind="link" label={t("whyCant")} onPress={onAbout} style={{ alignSelf: "flex-start", paddingHorizontal: 0 }} />
            </Card>
            {cards.fastest ? <OptionCard card={cards.fastest} picked={false} onDetails={() => onDetails("fastest")} /> : null}
            {chip ? (
              <Pressable accessibilityRole="button" onPress={() => onDetails("fastest", chip.offset)}
                style={{ minHeight: 64, borderRadius: radius.inner, backgroundColor: palette.surf2, paddingHorizontal: 16, paddingVertical: 12, flexDirection: "row", alignItems: "center", gap: 12 }}>
                <Svg width={20} height={20} viewBox="0 0 24 24"><Circle cx={12} cy={12} r={9} stroke={palette.accInk} strokeWidth={1.75} fill="none" /><Path d="M12 7v5l3 2" stroke={palette.accInk} strokeWidth={1.75} fill="none" strokeLinecap="round" /></Svg>
                <View style={{ flex: 1 }}>
                  <Text medium>{t("later", { n: chip.offset })}</Text>
                  <Text tone="sec" size={13}>{t("laterSub", { h: `${chip.depart.slice(0, 2)}:00`, n: Math.round(chip.arrives_later_by) })}</Text>
                </View>
              </Pressable>
            ) : null}
            {plan.compared ? (
              <Card inner style={{ padding: 14, gap: 8 }}>
                <Text size={13} medium tone="sec">{t("compared")}</Text>
                <View style={{ flexDirection: "row", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                  {plan.compared.routes.map((r) => <RouteChip key={r} route={r} small />)}
                  <LevelPill level={plan.compared.level.code} size="sm" />
                </View>
                {plan.compared.partly_estimated ? (
                  <View style={{ flexDirection: "row", gap: 8, alignItems: "center" }}><Badge label={t("partly")} /><Text tone="mut" size={12} style={{ flex: 1 }}>{t("partlyNote")}</Text></View>
                ) : null}
              </Card>
            ) : null}
          </>
        )}
        <Text tone="mut" size={12}>{footer}</Text>
      </ScrollView>
    </View>
  );
}
