import { DateTimePickerAndroid } from "@react-native-community/datetimepicker";
import { createElement } from "react";
import { Platform, Pressable, View } from "react-native";
import { useApp } from "../state/AppState";
import { useTheme } from "../theme/ThemeProvider";
import { font, radius, TOUCH } from "../theme/tokens";
import { Card } from "./Card";
import { Text } from "./Text";

export type TimeValue = { time: string; isNow: boolean };

const pad = (n: number) => String(n).padStart(2, "0");
export const clock = (d: Date) => `${pad(d.getHours())}:${pad(d.getMinutes())}`;
export const nowValue = (): TimeValue => ({ time: clock(new Date()), isNow: true });
const inMinutes = (m: number): TimeValue => ({ time: clock(new Date(Date.now() + m * 60000)), isNow: false });

/** Departure time without typing: defaults to Now, quick chips, and the phone's own clock picker. */
export function TimeField({ value, onChange }: { value: TimeValue; onChange: (v: TimeValue) => void }) {
  const { t } = useApp();
  const { palette } = useTheme();

  function openPicker() {
    const [h, m] = value.time.split(":").map(Number);
    const start = new Date(); start.setHours(h, m, 0, 0);
    DateTimePickerAndroid.open({
      value: start, mode: "time", is24Hour: true,
      onChange: (event, date) => { if (event.type === "set" && date) onChange({ time: clock(date), isNow: false }); },
    });
  }

  const chip = (label: string, on: boolean, onPress: () => void) => (
    <Pressable key={label} accessibilityRole="button" accessibilityState={{ selected: on }} onPress={onPress}
      style={{ minHeight: TOUCH, paddingHorizontal: 14, borderRadius: radius.control, justifyContent: "center", backgroundColor: on ? palette.surf2 : palette.surf,
        borderWidth: 1, borderColor: on ? palette.ink : palette.border }}>
      <Text size={14} medium tone={on ? "ink" : "sec"}>{label}</Text>
    </Pressable>
  );

  return (
    <Card inner style={{ gap: 10 }}>
      <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
        <Text tone="mut" size={13}>{t("at")}</Text>
        {Platform.OS === "web" ? createElement("input", {
          type: "time", value: value.time, "aria-label": t("at"),
          onChange: (e: { target: { value: string } }) => e.target.value && onChange({ time: e.target.value, isNow: false }),
          style: { fontFamily: font.mono, fontSize: 22, color: palette.ink, background: "transparent", border: 0, textAlign: "right" },
        }) : (
          <Pressable accessibilityRole="button" accessibilityLabel={`${t("at")} ${value.time}`} onPress={openPicker} style={{ minHeight: TOUCH, justifyContent: "center" }}>
            <Text mono size={26}>{value.time}</Text>
          </Pressable>
        )}
      </View>
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
        {chip(t("timeNow"), value.isNow, () => onChange(nowValue()))}
        {chip(t("timeIn30"), false, () => onChange(inMinutes(30)))}
        {chip(t("timeIn60"), false, () => onChange(inMinutes(60)))}
        {Platform.OS !== "web" ? chip(t("pickTime"), false, openPicker) : null}
      </View>
    </Card>
  );
}
