import { View } from "react-native";
import type { Stretch } from "../api/types";
import { useApp } from "../state/AppState";
import { useTheme } from "../theme/ThemeProvider";
import { floatingShadow } from "../theme/shadow";
import { Badge } from "./Badge";
import { LevelPill } from "./LevelPill";
import { Text } from "./Text";

/** The open tooltip for one stretch: firm or leans, the share of scenario draws at each level, the evidence tier. */
export function SegmentTip({ stretch, index }: { stretch: Stretch; index: number }) {
  const { t } = useApp();
  const { palette } = useTheme();
  const box = { marginTop: 10, padding: 14, borderRadius: 16, backgroundColor: palette.surf, borderWidth: 1, borderColor: palette.border, gap: 8 };
  if (stretch.level.code === 0) {
    return (
      <View style={[box, floatingShadow]} accessibilityLiveRegion="polite">
        <LevelPill level={0} size="sm" />
        <Text tone="mut" size={12}>{t("partlyNote")}</Text>
      </View>
    );
  }
  return (
    <View style={[box, floatingShadow]} accessibilityLiveRegion="polite">
      <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
        <Badge kind={stretch.robust_in_range ? "plain" : "leans"} label={t(stretch.robust_in_range ? "firm" : "leans")} />
        <Text medium size={14}>{t("stretchN", { n: index + 1 })}, {t(`L${stretch.level.code}`)}</Text>
      </View>
      <View style={{ flexDirection: "row", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
        {stretch.shares.map((p, i) => (p >= 0.05 ? (
          <View key={i} style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
            <LevelPill level={(i + 1) as 1 | 2 | 3} size="sm" /><Text size={13}>{Math.round(p * 100)}%</Text>
          </View>
        ) : null))}
      </View>
      <Text tone="mut" size={12}>
        {t("draws")} {t(stretch.robust_in_range ? "firmTip" : "leansTip")} · {t("evidence")}: {t(`T_${stretch.tier}`)}
      </Text>
    </View>
  );
}
