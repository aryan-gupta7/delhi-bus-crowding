import { useEffect, useRef, useState } from "react";
import { Pressable, TextInput, View } from "react-native";
import type { StopRef } from "../api/types";
import { useApp } from "../state/AppState";
import { useTheme } from "../theme/ThemeProvider";
import { font, radius, TOUCH } from "../theme/tokens";
import { Text } from "./Text";

type Props = { label: string; placeholder: string; value: StopRef | null; onChange: (s: StopRef | null) => void };

/** Search-as-you-type stop picker. A stop is only accepted when it is chosen from the suggestions. */
export function StopField({ label, placeholder, value, onChange }: Props) {
  const { client } = useApp();
  const { palette } = useTheme();
  const [text, setText] = useState(value?.name ?? "");
  const [options, setOptions] = useState<StopRef[]>([]);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const latest = useRef("");

  useEffect(() => { setText(value?.name ?? ""); setOptions([]); }, [value]);
  useEffect(() => () => clearTimeout(timer.current), []);

  function onType(next: string) {
    setText(next);
    if (value) onChange(null);
    clearTimeout(timer.current);
    if (next.trim().length < 2) { setOptions([]); return; }
    const query = next.trim();
    latest.current = query;   // ignore answers to queries the user has already typed past
    timer.current = setTimeout(() => {
      client.stops(query).then((rows) => latest.current === query && setOptions(rows)).catch(() => latest.current === query && setOptions([]));
    }, 200);
  }

  return (
    <View>
      <View style={{ flexDirection: "row", alignItems: "center", minHeight: 52, paddingHorizontal: 16, gap: 8 }}>
        <Text tone="mut" size={13} style={{ width: 44 }}>{label}</Text>
        <TextInput value={text} onChangeText={onType} placeholder={placeholder} placeholderTextColor={palette.mut}
          accessibilityLabel={label} autoCorrect={false}
          style={{ flex: 1, minHeight: TOUCH, color: palette.ink, fontFamily: font.medium, fontSize: 16 }} />
      </View>
      {options.length > 0 && !value ? (
        <View accessibilityLabel={`${label}: ${placeholder}`} style={{ marginHorizontal: 8, marginBottom: 8, borderRadius: radius.control, borderWidth: 1, borderColor: palette.border, backgroundColor: palette.surf, overflow: "hidden" }}>
          {options.slice(0, 6).map((o) => (
            <Pressable key={o.stop_id} accessibilityRole="button" onPress={() => { onChange(o); setOptions([]); }}
              style={{ minHeight: TOUCH, justifyContent: "center", paddingHorizontal: 12 }}>
              <Text size={15} medium numberOfLines={1}>{o.name}</Text>
            </Pressable>
          ))}
        </View>
      ) : null}
    </View>
  );
}
