import { useEffect, useRef, useState } from "react";
import { ActivityIndicator, Platform, Pressable, ScrollView, TextInput, View } from "react-native";
import Svg, { Circle, Path } from "react-native-svg";
import type { NearbyStop, StopRef } from "../api/types";
import { FAR_METRES, distanceText, nearestStops } from "../lib/location";
import { useApp } from "../state/AppState";
import { useTheme } from "../theme/ThemeProvider";
import { font, radius, TOUCH } from "../theme/tokens";
import { Text } from "./Text";

type Props = {
  label: string; placeholder: string; value: StopRef | null; onChange: (s: StopRef | null) => void;
  onPickOnMap: () => void; onOpenChange?: (open: boolean) => void;
};
const PAGE = 40;

/** Stop picker. Tapping the field opens a list straight away (your location, the map, then every stop A to Z);
 *  typing narrows it. A stop is only accepted when chosen from the list. */
export function StopField({ label, placeholder, value, onChange, onPickOnMap, onOpenChange }: Props) {
  const { client, t } = useApp();
  const { palette } = useTheme();
  const [text, setText] = useState(value?.name ?? "");
  const [open, setOpen] = useState(false);
  const [found, setFound] = useState<StopRef[]>([]);
  const [alpha, setAlpha] = useState<StopRef[]>([]);
  const [more, setMore] = useState(true);
  const [near, setNear] = useState<NearbyStop[]>([]);
  const [hint, setHint] = useState<{ text: string; error: boolean } | null>(null);
  const [locating, setLocating] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const latest = useRef("");

  useEffect(() => { setText(value?.name ?? ""); if (value) setOpen(false); }, [value]);
  useEffect(() => () => clearTimeout(timer.current), []);
  useEffect(() => { setAlpha([]); setMore(true); }, [client]);
  useEffect(() => { onOpenChange?.(open && !value); }, [open, value, onOpenChange]);

  const query = value ? "" : text.trim();
  useEffect(() => {
    if (!open || query.length >= 2 || alpha.length || !more) return;
    client.stops("", PAGE, 0).then((rows) => { setAlpha(rows); setMore(rows.length === PAGE); }).catch(() => undefined);
  }, [open, query, alpha.length, more, client]);

  function onType(next: string) {
    setText(next); setOpen(true);
    if (value) onChange(null);
    clearTimeout(timer.current);
    const q = next.trim();
    latest.current = q;
    if (q.length < 2) { setFound([]); return; }
    timer.current = setTimeout(() => {
      client.stops(q, 12).then((rows) => latest.current === q && setFound(rows)).catch(() => latest.current === q && setFound([]));
    }, 200);
  }

  function choose(s: StopRef) { onChange(s); setOpen(false); }

  function showMore() {
    client.stops("", PAGE, alpha.length).then((rows) => { setAlpha((prev) => [...prev, ...rows]); setMore(rows.length === PAGE); }).catch(() => undefined);
  }

  async function locate() {
    setLocating(true); setHint({ text: t("locating"), error: false });
    const res = await nearestStops(client, 5);
    setLocating(false);
    if (!res.ok) { setHint({ text: t(res.reason === "denied" ? "locationDenied" : "locationFailed"), error: true }); return; }
    if (!res.stops.length) { setHint({ text: t("locationFailed"), error: true }); return; }
    setNear(res.stops);
    const d = distanceText(res.stops[0].distance_m);
    if (res.stops[0].distance_m > FAR_METRES) { setHint({ text: t("nearestFar", { d }), error: false }); return; }   // outside Delhi: let the user choose
    choose(res.stops[0]);
    setHint({ text: t("nearestHint", { d }), error: false });
  }

  const showingSearch = query.length >= 2;
  const rows = showingSearch ? found : alpha;
  const row = (s: StopRef, suffix?: string) => (
    <Pressable key={s.stop_id} accessibilityRole="button" accessibilityLabel={s.name} onPress={() => choose(s)}
      style={{ minHeight: TOUCH, justifyContent: "center", paddingHorizontal: 12, paddingVertical: 4 }}>
      <Text size={15} medium numberOfLines={2}>{s.name}</Text>
      {suffix ? <Text size={12} tone="mut">{suffix}</Text> : null}
    </Pressable>
  );
  const action = (title: string, d: string, onPress: () => void, busy = false) => (
    <Pressable accessibilityRole="button" accessibilityLabel={title} onPress={onPress} disabled={busy}
      style={{ minHeight: TOUCH, flexDirection: "row", alignItems: "center", gap: 10, paddingHorizontal: 12 }}>
      {busy ? <ActivityIndicator color={palette.accInk} /> : (
        <Svg width={18} height={18} viewBox="0 0 24 24"><Path d={d} stroke={palette.accInk} strokeWidth={1.75} fill="none" strokeLinecap="round" strokeLinejoin="round" />
          {d.startsWith("M12 2") ? <Circle cx={12} cy={9} r={2.5} stroke={palette.accInk} strokeWidth={1.75} fill="none" /> : null}</Svg>
      )}
      <Text size={15} medium tone="accent">{title}</Text>
    </Pressable>
  );

  return (
    <View>
      <View style={{ flexDirection: "row", alignItems: "center", minHeight: 52, paddingLeft: 16, paddingRight: 64, gap: 8 }}>
        <Text tone="mut" size={13} style={{ width: 44 }}>{label}</Text>
        <TextInput value={text} onChangeText={onType} onFocus={() => setOpen(true)} placeholder={placeholder} placeholderTextColor={palette.mut}
          accessibilityLabel={label} autoCorrect={false} selectTextOnFocus
          style={{ flex: 1, minHeight: TOUCH, color: palette.ink, fontFamily: font.medium, fontSize: 16 }} />
      </View>
      {hint && !open ? <Text size={12} tone={hint.error ? "ink" : "mut"} style={[{ paddingHorizontal: 16, paddingBottom: 8 }, hint.error ? { color: palette.levels[3].border } : null]}>{hint.text}</Text> : null}
      {open && !value ? (
        <View style={{ marginHorizontal: 8, marginBottom: 8, borderRadius: radius.control, borderWidth: 1, borderColor: palette.border, backgroundColor: palette.surf, overflow: "hidden" }}>
          {!showingSearch ? (
            <>
              {action(t("useLocation"), "M12 2a7 7 0 0 0-7 7c0 5 7 13 7 13s7-8 7-13a7 7 0 0 0-7-7z", locate, locating)}
              {Platform.OS !== "web" ? action(t("pickOnMap"), "M3 6l6-3 6 3 6-3v15l-6 3-6-3-6 3zM9 3v15M15 6v15", () => { setOpen(false); onPickOnMap(); }) : null}
              {hint ? <Text size={12} tone={hint.error ? "ink" : "mut"} style={[{ paddingHorizontal: 12, paddingBottom: 8 }, hint.error ? { color: palette.levels[3].border } : null]}>{hint.text}</Text> : null}
              {near.length ? <Text size={12} medium tone="mut" style={{ paddingHorizontal: 12, paddingTop: 6 }}>{t("nearYou")}</Text> : null}
              {near.map((s) => row(s, distanceText(s.distance_m)))}
              <Text size={12} medium tone="mut" style={{ paddingHorizontal: 12, paddingTop: 8, paddingBottom: 2 }}>{t("allStops")}</Text>
            </>
          ) : null}
          <ScrollView nestedScrollEnabled keyboardShouldPersistTaps="handled" style={{ maxHeight: 280 }}>
            {rows.map((s) => row(s))}
            {showingSearch && !rows.length ? <Text size={14} tone="mut" style={{ padding: 12 }}>{t("noMatch")}</Text> : null}
            {!showingSearch && more && alpha.length ? (
              <Pressable accessibilityRole="button" onPress={showMore} style={{ minHeight: TOUCH, justifyContent: "center", paddingHorizontal: 12 }}>
                <Text size={14} medium tone="accent">{t("loadMore")}</Text>
              </Pressable>
            ) : null}
          </ScrollView>
          <Pressable accessibilityRole="button" accessibilityLabel={t("close")} onPress={() => setOpen(false)}
            style={{ minHeight: TOUCH, justifyContent: "center", paddingHorizontal: 12, borderTopWidth: 1, borderTopColor: palette.border }}>
            <Text size={14} medium tone="mut">{t("close")}</Text>
          </Pressable>
        </View>
      ) : null}
    </View>
  );
}
