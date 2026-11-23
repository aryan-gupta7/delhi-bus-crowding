import { useEffect, useState } from "react";
import { Pressable, ScrollView, TextInput, View } from "react-native";
import { ApiError } from "../api/client";
import type { DayType, Example, StopRef } from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Segmented } from "../components/Segmented";
import { StopField } from "../components/StopField";
import { Text } from "../components/Text";
import { useApp } from "../state/AppState";
import { useTheme } from "../theme/ThemeProvider";
import { font, radius, TOUCH } from "../theme/tokens";
import type { ResultsView } from "./types";

const TIME_RE = /^([01]\d|2[0-3]):[0-5]\d$/;
const shift = (time: string, minutes: number) => {
  const [h, m] = time.split(":").map(Number);
  const total = (h * 60 + m + minutes + 1440) % 1440;
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
};

export function PlanScreen({ onResults }: { onResults: (v: ResultsView) => void }) {
  const { t, client, saveResult, lastResult } = useApp();
  const { palette } = useTheme();
  const [from, setFrom] = useState<StopRef | null>(null);
  const [to, setTo] = useState<StopRef | null>(null);
  const [time, setTime] = useState("08:30");
  const [day, setDay] = useState<DayType>("weekday");
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
    if (!TIME_RE.test(time)) { setStatus({ text: t("timeInvalid"), error: true }); return; }
    void search(from, to, time, day);
  }

  function pickExample(e: Example) {
    setFrom(e.from); setTo(e.to); setTime(e.time); setDay("weekday");
    void search(e.from, e.to, e.time, "weekday");
  }

  const swap = () => { setFrom(to); setTo(from); };

  return (
    <ScrollView contentContainerStyle={{ padding: 16, paddingBottom: 120, gap: 16 }} keyboardShouldPersistTaps="handled">
      <View style={{ gap: 4, paddingTop: 8 }}>
        <Text size={26} medium accessibilityRole="header">{t("heroTitle")}</Text>
        <Text tone="sec">{t("heroSub")}</Text>
      </View>

      <Card style={{ padding: 0 }}>
        <StopField label={t("from")} placeholder={t("fromPh")} value={from} onChange={setFrom} />
        <View style={{ height: 1, backgroundColor: palette.border, marginHorizontal: 16 }} />
        <StopField label={t("to")} placeholder={t("toPh")} value={to} onChange={setTo} />
      </Card>
      <Button kind="quiet" label={t("swap")} onPress={swap} style={{ alignSelf: "flex-start", paddingHorizontal: 0 }} />

      <Card style={{ gap: 12 }}>
        <Text tone="mut" size={13}>{t("at")}</Text>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
          <Pressable accessibilityRole="button" accessibilityLabel={t("earlier")} onPress={() => TIME_RE.test(time) && setTime(shift(time, -15))}
            style={{ width: TOUCH, height: TOUCH, borderRadius: radius.control, alignItems: "center", justifyContent: "center", backgroundColor: palette.seg }}>
            <Text size={20} medium>−</Text>
          </Pressable>
          <TextInput value={time} onChangeText={setTime} keyboardType="numbers-and-punctuation" maxLength={5} accessibilityLabel={t("at")}
            style={{ flex: 1, minWidth: 0, minHeight: TOUCH, textAlign: "center", color: palette.ink, fontFamily: font.medium, fontSize: 22, borderRadius: radius.control, borderWidth: 1, borderColor: palette.border }} />
          <Pressable accessibilityRole="button" accessibilityLabel={t("laterBy")} onPress={() => TIME_RE.test(time) && setTime(shift(time, 15))}
            style={{ width: TOUCH, height: TOUCH, borderRadius: radius.control, alignItems: "center", justifyContent: "center", backgroundColor: palette.seg }}>
            <Text size={20} medium>+</Text>
          </Pressable>
        </View>
        <Segmented<DayType> options={[{ key: "weekday", label: t("weekday") }, { key: "weekend", label: t("weekend") }]} value={day} onChange={setDay} />
      </Card>

      <Button label={t("show")} onPress={submit} disabled={busy} />
      {status ? <Text size={13} tone={status.error ? "ink" : "sec"} style={status.error ? { color: palette.levels[3].border } : undefined} accessibilityLiveRegion="polite">{status.text}</Text> : null}

      {examples.length > 0 ? (
        <View style={{ gap: 8 }}>
          <Text tone="sec" size={13} medium>{t("tryPeak")}</Text>
          {examples.map((e) => (
            <Pressable key={`${e.from.stop_id}-${e.to.stop_id}`} accessibilityRole="button" onPress={() => pickExample(e)}
              style={{ minHeight: 56, borderRadius: radius.inner, backgroundColor: palette.accSubtle, paddingHorizontal: 16, paddingVertical: 10, justifyContent: "center" }}>
              <Text medium size={15}>{e.from.name} → {e.to.name}</Text>
              <Text tone="mut" size={13}>{t("weekday")}, {e.time}</Text>
            </Pressable>
          ))}
        </View>
      ) : null}

      {lastResult ? (
        <Button kind="quiet" label={`${t("lastResult")}: ${lastResult.fromName} → ${lastResult.toName}`} onPress={() => onResults({ ...lastResult, cached: true })}
          style={{ alignSelf: "flex-start", paddingHorizontal: 0 }} />
      ) : null}
    </ScrollView>
  );
}
