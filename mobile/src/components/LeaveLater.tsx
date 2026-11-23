import { useState } from "react";
import { Pressable, ScrollView, View } from "react-native";
import type { Plan } from "../api/types";
import { useApp } from "../state/AppState";
import { useTheme } from "../theme/ThemeProvider";
import { TOUCH } from "../theme/tokens";
import { LevelPill } from "./LevelPill";
import { Text } from "./Text";

type Props = { later: Plan["leave_later"]; initialOffset?: number };

/** Stepped slider: Now, +10 ... +60. Each step shows the usual level if you left that much later. */
export function LeaveLater({ later, initialOffset = 0 }: Props) {
  const { t } = useApp();
  const { palette } = useTheme();
  const [offset, setOffset] = useState(initialOffset);
  if (!later.offsets.length) return null;
  const row = later.offsets.find((r) => r.offset === offset);
  const steps = [0, ...later.offsets.map((r) => r.offset)];
  return (
    <View style={{ gap: 8 }}>
      <Text medium tone="sec" size={14}>{t("laterTitle")}</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6 }}>
        {steps.map((o) => {
          const on = o === offset;
          return (
            <Pressable key={o} accessibilityRole="button" accessibilityState={{ selected: on }}
              accessibilityLabel={o === 0 ? t("now") : t("leavingIn", { n: o })} onPress={() => setOffset(o)}
              style={{ minWidth: TOUCH, minHeight: TOUCH, borderRadius: 12, alignItems: "center", justifyContent: "center", paddingHorizontal: 10,
                backgroundColor: on ? palette.accSubtle : palette.surf, borderWidth: on ? 0 : 1, borderColor: palette.border }}>
              <Text size={13} medium tone={on ? "accent" : "mut"}>{o === 0 ? t("now") : `+${o}`}</Text>
            </Pressable>
          );
        })}
      </ScrollView>
      {row ? (
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <Text size={14}>{row.depart}</Text>
          <LevelPill level={row.level_code} size="sm" />
          <Text tone="mut" size={12}>{t("arrivesLater", { n: Math.round(row.arrives_later_by) })}</Text>
        </View>
      ) : null}
    </View>
  );
}
