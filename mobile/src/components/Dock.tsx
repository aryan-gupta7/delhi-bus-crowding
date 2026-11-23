import type { ReactElement } from "react";
import { Pressable, View } from "react-native";
import Svg, { Circle, Path } from "react-native-svg";
import { useApp } from "../state/AppState";
import { useTheme } from "../theme/ThemeProvider";
import { floatingShadow } from "../theme/shadow";
import { radius, TOUCH } from "../theme/tokens";
import { Text } from "./Text";

export type Tab = "plan" | "map" | "about";
const ICONS: Record<Tab, (c: string) => ReactElement> = {
  plan: (c) => <Path d="M4 12h13M12 6l6 6-6 6" stroke={c} strokeWidth={1.8} fill="none" strokeLinecap="round" strokeLinejoin="round" />,
  map: (c) => <Path d="M3 6l6-2 6 2 6-2v14l-6 2-6-2-6 2zM9 4v14M15 6v14" stroke={c} strokeWidth={1.6} fill="none" strokeLinejoin="round" />,
  about: (c) => (<><Circle cx={12} cy={12} r={8.5} stroke={c} strokeWidth={1.6} fill="none" /><Path d="M12 11v5M12 8v.01" stroke={c} strokeWidth={1.8} strokeLinecap="round" /></>),
};

/** Floating bottom bar. One of the two layers that carry a shadow. */
export function Dock({ tab, onChange }: { tab: Tab; onChange: (t: Tab) => void }) {
  const { t } = useApp();
  const { palette } = useTheme();
  return (
    <View style={[{ position: "absolute", left: 16, right: 16, bottom: 12, flexDirection: "row", padding: 6, borderRadius: radius.card,
      backgroundColor: palette.surf, borderWidth: 1, borderColor: palette.border }, floatingShadow]}>
      {(["plan", "map", "about"] as Tab[]).map((k) => {
        const on = k === tab;
        const label = t(k === "plan" ? "tabPlan" : k === "map" ? "tabMap" : "tabAbout");
        const color = on ? palette.accInk : palette.mut;
        return (
          <Pressable key={k} accessibilityRole="tab" accessibilityState={{ selected: on }} accessibilityLabel={label} onPress={() => onChange(k)}
            style={{ flex: 1, minHeight: TOUCH + 8, borderRadius: radius.inner, alignItems: "center", justifyContent: "center", gap: 2,
              backgroundColor: on ? palette.accSubtle : "transparent" }}>
            <Svg width={22} height={22} viewBox="0 0 24 24">{ICONS[k](color)}</Svg>
            <Text size={12} medium style={{ color }}>{label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}
