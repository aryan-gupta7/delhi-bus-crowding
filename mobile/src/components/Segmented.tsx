import { Pressable, View } from "react-native";
import { radius, TOUCH } from "../theme/tokens";
import { useTheme } from "../theme/ThemeProvider";
import { Text } from "./Text";

type Props<K extends string> = { options: { key: K; label: string }[]; value: K; onChange: (k: K) => void };

export function Segmented<K extends string>({ options, value, onChange }: Props<K>) {
  const { palette } = useTheme();
  return (
    <View style={{ flexDirection: "row", padding: 3, borderRadius: radius.control, backgroundColor: palette.surf2 }}>
      {options.map((o) => {
        const on = o.key === value;
        return (
          <Pressable key={o.key} accessibilityRole="button" accessibilityState={{ selected: on }} onPress={() => onChange(o.key)}
            style={{ flex: 1, minHeight: TOUCH, borderRadius: radius.control - 3, alignItems: "center", justifyContent: "center", paddingHorizontal: 8,
              backgroundColor: on ? palette.surf : "transparent", borderWidth: 1, borderColor: on ? palette.border : "transparent" }}>
            <Text size={14} medium tone={on ? "ink" : "mut"} numberOfLines={1}>{o.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}
