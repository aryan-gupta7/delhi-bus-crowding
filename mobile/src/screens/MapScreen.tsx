import { useEffect, useMemo, useState } from "react";
import { ScrollView, View } from "react-native";
import Svg, { G, Polyline } from "react-native-svg";
import type { Level, StretchCollection } from "../api/types";
import { Card } from "../components/Card";
import { LevelPill } from "../components/LevelPill";
import { ScreenHeader } from "../components/ScreenHeader";
import { Segmented } from "../components/Segmented";
import { Text } from "../components/Text";
import { projector, type Pt } from "../lib/project";
import { useApp } from "../state/AppState";
import { useTheme } from "../theme/ThemeProvider";
import type { ResultsView } from "./types";

type Item = { coords: Pt[]; level: Level["code"]; flow: number; route: string; pi: number; id: string };
const W = 340, H = 340;

/** Schematic map of the planned journey. No tiles are loaded, so it works offline and stays light on a low-end phone. */
export function MapScreen({ view }: { view: ResultsView | null }) {
  const { t, client } = useApp();
  const { palette } = useTheme();
  // The hour the plan's stretches were scored for (the bus is usually boarded after the requested time).
  const planHour = view ? (Object.values(view.plan.cards)[0]?.legs[0]?.stretches[0]?.hour ?? Number(view.time.slice(0, 2))) : 0;
  const [hour, setHour] = useState(planHour);
  const [other, setOther] = useState<Record<string, StretchCollection>>({});

  useEffect(() => setHour(planHour), [planHour, view]);

  const planItems = useMemo<Item[]>(() => {
    if (!view) return [];
    const seen = new Set<string>();
    const items: Item[] = [];
    for (const card of Object.values(view.plan.cards)) for (const leg of card.legs) for (const s of leg.stretches) {
      const id = `${leg.route}:${s.stretch_id}`;
      if (seen.has(id)) continue;
      seen.add(id);
      items.push({ coords: s.coords, level: s.level.code, flow: s.flow, route: leg.route, pi: s.pi, id });
    }
    return items;
  }, [view]);

  useEffect(() => {
    if (!view || hour === planHour) return;
    const routes = [...new Set(planItems.map((i) => i.route))];
    let live = true;
    Promise.all(routes.map(async (r) => [`${r}|${hour}`, await client.stretches(r, hour, view.dayType)] as const))
      .then((rows) => { if (live) setOther((prev) => ({ ...prev, ...Object.fromEntries(rows) })); })
      .catch(() => undefined);
    return () => { live = false; };
  }, [view, hour, planHour, planItems, client]);

  const items = useMemo<Item[]>(() => {
    if (hour === planHour) return planItems;
    return planItems.map((i) => {
      const f = other[`${i.route}|${hour}`]?.features.find((x) => `${i.route}:${x.properties.stretch_id}` === i.id);
      return { ...i, level: f ? f.properties.level.code : 0, flow: f ? f.properties.flow : 0, pi: f ? f.properties.pi : 0 };
    });
  }, [planItems, other, hour, planHour]);

  if (!view || planItems.length === 0) {
    return (
      <View style={{ flex: 1 }}>
        <ScreenHeader title={t("mapTitle")} />
        <View style={{ padding: 16 }}><Card variant="dashed"><Text tone="sec">{t("noPlanYet")}</Text></Card></View>
      </View>
    );
  }

  const project = projector(planItems.flatMap((i) => i.coords), W, H);
  const peak = Math.max(1, ...items.map((i) => i.flow));
  const worst = [...items].filter((i) => i.level > 0).sort((a, b) => b.pi - a.pi)[0];
  const hours = [planHour - 1, planHour, planHour + 1].filter((h) => h >= 0 && h <= 23);
  const points = (i: Item) => i.coords.map(project).map((p) => p.map((n) => n.toFixed(1)).join(",")).join(" ");

  return (
    <View style={{ flex: 1 }}>
      <ScreenHeader title={t("mapTitle")} subtitle={t("fromTo", { from: view.fromName, to: view.toName })} />
      <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 120, gap: 12 }}>
        <Segmented options={hours.map((h) => ({ key: String(h), label: `${String(h).padStart(2, "0")}:00` }))} value={String(hour)} onChange={(k) => setHour(Number(k))} />
        <View style={{ borderRadius: 24, backgroundColor: palette.map, overflow: "hidden", alignItems: "center" }}>
          <Svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} accessibilityLabel={t("mapTitle")}>
            {items.map((i) => {
              const w = 4 + 12 * Math.sqrt(i.flow / peak);
              if (i.level === 0) return <Polyline key={i.id} points={points(i)} fill="none" stroke={palette.mut} strokeWidth={4} strokeDasharray="6 5" strokeLinecap="round" />;
              const tok = palette.levels[i.level];
              return (
                <G key={i.id}>
                  <Polyline points={points(i)} fill="none" stroke={tok.border} strokeWidth={w + 3} strokeLinecap="round" strokeLinejoin="round" />
                  <Polyline points={points(i)} fill="none" stroke={tok.fill} strokeWidth={w} strokeLinecap="round" strokeLinejoin="round" />
                </G>
              );
            })}
          </Svg>
        </View>
        {worst ? (
          <Card inner style={{ padding: 12, gap: 6 }}>
            <Text size={13} medium tone="sec">{t("pinch")}</Text>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <Text medium size={14}>{worst.route}</Text><LevelPill level={worst.level} size="sm" />
              <Text tone="mut" size={13}>{String(hour).padStart(2, "0")}:00</Text>
            </View>
          </Card>
        ) : null}
        <View style={{ flexDirection: "row", gap: 6, flexWrap: "wrap" }}>{([1, 2, 3, 0] as const).map((c) => <LevelPill key={c} level={c} size="sm" />)}</View>
        <Text tone="mut" size={12}>{t("schematicNote")}</Text>
        <Text tone="mut" size={12}>{t("usually", { period: view.plan.period })}</Text>
      </ScrollView>
    </View>
  );
}
