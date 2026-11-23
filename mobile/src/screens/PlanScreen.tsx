import { useEffect, useState } from "react";
import { Pressable, ScrollView, View } from "react-native";
import Svg, { Path } from "react-native-svg";
import { ApiError } from "../api/client";
import type { DayType, Example, StopRef } from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Logo } from "../components/Logo";
import { MapPicker } from "../components/MapPicker";
import { Segmented } from "../components/Segmented";
import { StopField } from "../components/StopField";
import { TimeField, nowValue, type TimeValue } from "../components/TimeField";
import { Text } from "../components/Text";
import type { Lang } from "../i18n/i18n";
import { useApp } from "../state/AppState";
import { useTheme } from "../theme/ThemeProvider";
import { radius, TOUCH } from "../theme/tokens";
import type { ResultsView } from "./types";

const defaultDay = (): DayType => ([0, 6].includes(new Date().getDay()) ? "weekend" : "weekday");   // today, by the phone's calendar

const Icon = ({ d, color, size = 18 }: { d: string; color: string; size?: number }) => (
  <Svg width={size} height={size} viewBox="0 0 24 24"><Path d={d} stroke={color} strokeWidth={1.75} fill="none" strokeLinecap="round" strokeLinejoin="round" /></Svg>
);

export function PlanScreen({ onResults }: { onResults: (v: ResultsView) => void }) {
  const { t, client, saveResult, lastResult, lang, setLang } = useApp();
  const { palette } = useTheme();
  const [from, setFrom] = useState<StopRef | null>(null);
  const [to, setTo] = useState<StopRef | null>(null);
  const [when, setWhen] = useState<TimeValue>(nowValue);
  const [day, setDay] = useState<DayType>(defaultDay);
  const [picking, setPicking] = useState(false);   // a stop list is open: hide the swap button so it does not float over it
  const [mapFor, setMapFor] = useState<"from" | "to" | null>(null);
  const [examples, setExamples] = useState<Example[]>([]);
  const [status, setStatus] = useState<{ text: string; error: boolean } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let current = true;   // a slow answer from a previous server address must not overwrite the new one
    client.examples().then((rows) => current && setExamples(rows)).catch(() => current && setExamples([]));
    return () => { current = false; };
  }, [client]);

  async function search(f: StopRef, tt: StopRef, at: string, d: DayType) {
    setBusy(true); setStatus({ text: t("searching"), error: false });
    try {
      const plan = await client.plan(f.stop_id, tt.stop_id, at, d);
      const view = { plan, fromName: f.name, toName: tt.name, dayType: d, time: at };
      if (Object.keys(plan.cards).length) saveResult(view);
      setStatus(null);
      onResults({ ...view, cached: false });
    } catch (e) {
      if (e instanceof ApiError && e.offline && lastResult) {
        setStatus({ text: t("offlineCached"), error: false });
        onResults({ ...lastResult, cached: true });
      } else {
        setStatus({ text: t("error"), error: true });
      }
    } finally { setBusy(false); }
  }

  function submit() {
    if (!from || !to) { setStatus({ text: t("pickBoth"), error: true }); return; }
    const at = when.isNow ? nowValue().time : when.time;   // "Now" is read again when you press the button
    void search(from, to, at, day);
  }

  function pickExample(e: Example) {
    setFrom(e.from); setTo(e.to); setWhen({ time: e.time, isNow: false }); setDay("weekday");
    void search(e.from, e.to, e.time, "weekday");
  }

  return (
    <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 130 }} keyboardShouldPersistTaps="handled">
      <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", minHeight: TOUCH }}>
        <Logo />
        <View style={{ width: 104 }}>
          <Segmented<Lang> options={[{ key: "en", label: "EN" }, { key: "hi", label: "हिं" }]} value={lang} onChange={setLang} />
        </View>
      </View>

      <Text size={36} display accessibilityRole="header" style={{ marginTop: 28 }}>{t("heroTitle")}</Text>
      <Text tone="sec" style={{ marginTop: 8 }}>{t("heroSub")}</Text>

      <Card style={{ padding: 0, marginTop: 24 }}>
        <StopField label={t("from")} placeholder={t("fromPh")} value={from} onChange={setFrom} onPickOnMap={() => setMapFor("from")} onOpenChange={setPicking} />
        <View style={{ height: 1, backgroundColor: palette.border, marginHorizontal: 16 }} />
        <StopField label={t("to")} placeholder={t("toPh")} value={to} onChange={setTo} onPickOnMap={() => setMapFor("to")} onOpenChange={setPicking} />
        {!picking ? <Pressable accessibilityRole="button" accessibilityLabel={t("swap")} onPress={() => { setFrom(to); setTo(from); }}
          style={{ position: "absolute", right: 12, top: "50%", marginTop: -22, width: TOUCH, height: TOUCH, borderRadius: radius.control, alignItems: "center", justifyContent: "center",
            backgroundColor: palette.surf, borderWidth: 1, borderColor: palette.border }}>
          <Icon color={palette.ink} d="M7 4v16M7 20l-4-4M7 20l4-4M17 20V4M17 4l-4 4M17 4l4 4" />
        </Pressable> : null}
      </Card>

      <View style={{ marginTop: 12 }}><TimeField value={when} onChange={setWhen} /></View>
      <View style={{ marginTop: 12 }}>
        <Segmented<DayType> options={[{ key: "weekday", label: t("weekday") }, { key: "weekend", label: t("weekend") }]} value={day} onChange={setDay} />
      </View>

      <View style={{ marginTop: 16 }}>
        <Pressable accessibilityRole="button" accessibilityLabel={t("show")} disabled={busy} onPress={submit}
          style={{ height: 52, borderRadius: radius.button, backgroundColor: palette.ink, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8, opacity: busy ? 0.7 : 1 }}>
          <Text size={16} medium style={{ color: palette.bg }}>{t("show")}</Text>
          <Icon color={palette.bg} d="M5 12h14M13 6l6 6-6 6" />
        </Pressable>
      </View>
      <Text tone="mut" size={13} style={{ textAlign: "center", marginTop: 6 }}>{t("noSignup")}</Text>
      {status ? <Text size={13} tone={status.error ? "ink" : "sec"} style={[{ marginTop: 8 }, status.error ? { color: palette.levels[3].border } : null]} accessibilityLiveRegion="polite">{status.text}</Text> : null}

      {examples.length > 0 ? (
        <View style={{ marginTop: 20 }}>
          <Text tone="sec" size={13} medium>{t("tryPeak")}</Text>
          <Card inner style={{ marginTop: 8, padding: 0, overflow: "hidden" }}>
            {examples.map((e, i) => (
              <Pressable key={`${e.from.stop_id}-${e.to.stop_id}`} accessibilityRole="button" onPress={() => pickExample(e)}
                style={{ minHeight: 56, flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 16, paddingVertical: 6,
                  borderTopWidth: i === 0 ? 0 : 1, borderTopColor: palette.border }}>
                <View style={{ flex: 1 }}>
                  <Text medium>{t("fromTo", { from: e.from.name, to: e.to.name })}</Text>
                  <Text tone="mut" size={13}>{t("weekday")}, <Text mono size={13} tone="mut">{e.time}</Text></Text>
                </View>
                <Icon color={palette.mut} size={16} d="M9 6l6 6-6 6" />
              </Pressable>
            ))}
          </Card>
        </View>
      ) : null}

      {lastResult ? (
        <Button kind="quiet" label={`${t("lastResult")}: ${t("fromTo", { from: lastResult.fromName, to: lastResult.toName })}`} onPress={() => onResults({ ...lastResult, cached: true })}
          style={{ alignSelf: "flex-start", paddingHorizontal: 0, marginTop: 8 }} />
      ) : null}
      <Text tone="mut" size={12} style={{ textAlign: "center", marginTop: 16 }}>{t("sample")}</Text>
      <MapPicker visible={mapFor !== null} focus={mapFor === "to" ? from : to} onClose={() => setMapFor(null)} onSelect={(s) => (mapFor === "from" ? setFrom(s) : setTo(s))} />
    </ScrollView>
  );
}
