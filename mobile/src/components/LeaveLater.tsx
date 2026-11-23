import { useState } from "react";
import { Pressable, View } from "react-native";
import type { Plan } from "../api/types";
import { useApp } from "../state/AppState";
import { useTheme } from "../theme/ThemeProvider";
import { floatingShadow } from "../theme/shadow";
import { TOUCH } from "../theme/tokens";
import { LevelPill } from "./LevelPill";
import { Text } from "./Text";

type Props = { later: Plan["leave_later"]; initialOffset?: number };
const HALF_TICK = TOUCH / 2;

/** Stepped slider: Now, +10 ... +60. The fill and the bead border are the accent; the selected tick label and the
 *  readout are ink / accent text; tick labels are Geist Mono. Each step shows the usual level if you left that much later. */
export function LeaveLater({ later, initialOffset = 0 }: Props) {
  const { t } = useApp();
  const { palette } = useTheme();
  const [offset, setOffset] = useState(initialOffset);
  if (!later.offsets.length) return null;
  const steps = [0, ...later.offsets.map((r) => r.offset)];
  const index = Math.max(0, steps.indexOf(offset));
  const pct = (100 * index) / (steps.length - 1);
  const row = later.offsets.find((r) => r.offset === offset);
  return (
    <View style={{ gap: 6 }}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "baseline" }}>
        <Text medium tone="sec" size={13}>{t("laterTitle")}</Text>
        {row ? <Text mono size={13} tone="accent">{`+${offset} ${t("min")}, ${row.depart}`}</Text> : null}
      </View>
      <View style={{ marginTop: 22 }}>
        <View style={{ marginHorizontal: HALF_TICK, height: 28, justifyContent: "center" }}>
          <View style={{ height: 8, borderRadius: 4, backgroundColor: palette.track }} />
          <View style={{ position: "absolute", left: 0, width: `${pct}%`, height: 8, borderRadius: 4, backgroundColor: palette.accent }} />
          <View style={[{ position: "absolute", left: `${pct}%`, marginLeft: -14, width: 28, height: 28, borderRadius: 14, backgroundColor: palette.surf, borderWidth: 2, borderColor: palette.accent }, floatingShadow]} />
          {row ? (
            <View style={{ position: "absolute", left: `${pct}%`, top: -22, width: 160, marginLeft: -80, alignItems: "center" }}>
              <Text size={12} medium>{`${row.depart.slice(0, 2)}:00 ${t("hourWord")}: ${t(`L${row.level_code}`)}`}</Text>
            </View>
          ) : null}
        </View>
        <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
          {steps.map((o) => (
            <Pressable key={o} accessibilityRole="button" accessibilityState={{ selected: o === offset }}
              accessibilityLabel={o === 0 ? t("now") : t("leavingIn", { n: o })} onPress={() => setOffset(o)}
              style={{ width: TOUCH, minHeight: TOUCH, alignItems: "center", paddingTop: 4 }}>
              <Text mono size={12} tone={o === offset ? "ink" : "mut"}>{o === 0 ? t("now") : `+${o}`}</Text>
            </Pressable>
          ))}
        </View>
      </View>
      {row ? (
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <LevelPill level={row.level_code} size="sm" />
          <Text tone="mut" size={12}>{t("arrivesLater", { n: Math.round(row.arrives_later_by) })}</Text>
        </View>
      ) : null}
    </View>
  );
}
