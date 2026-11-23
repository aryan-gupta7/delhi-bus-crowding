import { useId } from "react";
import { StyleSheet, View } from "react-native";
import type { Level, Tier } from "../api/types";
import { useApp } from "../state/AppState";
import { useTheme } from "../theme/ThemeProvider";
import { Hatch } from "./Hatch";
import { PersonGlyph } from "./PersonGlyph";
import { Text } from "./Text";

type Props = { level: Level["code"]; tier?: Tier; size?: "sm" | "md" | "lg" };
const HEIGHT = { sm: 26, md: 32, lg: 40 } as const;
const GLYPH = { sm: 1, md: 1, lg: 1.3 } as const;   // glyphs are scaled 1.3 on the big chip

/** A crowding level: glyph count + word + fill, never colour alone.
 *  Tier: High is solid, Medium has a ring (2px gap + 1px ink), Low is hatched. Level 0 is a dashed outline. */
export function LevelPill({ level, tier = "High", size = "md" }: Props) {
  const { t } = useApp();
  const { palette } = useTheme();
  const hatchId = `hatch${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  const h = HEIGHT[size];
  const textSize = size === "lg" ? 17 : size === "md" ? 15 : 13;

  if (level === 0) {
    return (
      <View accessible accessibilityLabel={t("L0")}
        style={[s.base, { height: h, borderStyle: "dashed", borderColor: palette.mut, borderWidth: 1 }]}>
        <Text size={textSize} medium tone="sec">? {t("L0")}</Text>
      </View>
    );
  }
  const tok = palette.levels[level];
  const word = t(`L${level}`);
  const pill = (
    <View style={[s.base, { height: h, backgroundColor: tok.fill, borderColor: tok.border, borderWidth: 1, overflow: "hidden" }]}>
      {tier === "Low" ? <Hatch color={tok.hatch} id={hatchId} /> : null}
      <View style={s.glyphs}>{Array.from({ length: level }, (_, i) => <PersonGlyph key={i} color={tok.ink} scale={GLYPH[size]} />)}</View>
      <Text size={textSize} medium style={{ color: tok.ink }}>{word}</Text>
    </View>
  );
  const label = `${word}, ${t(`T_${tier}`)}`;
  if (tier === "Medium") {
    return (
      <View accessible accessibilityLabel={label}
        style={{ padding: 2, borderRadius: 999, borderWidth: 1, borderColor: palette.ink, backgroundColor: palette.surf, alignSelf: "flex-start" }}>
        {pill}
      </View>
    );
  }
  return <View accessible accessibilityLabel={label} style={{ alignSelf: "flex-start" }}>{pill}</View>;
}

const s = StyleSheet.create({
  base: { flexDirection: "row", alignItems: "center", gap: 6, paddingHorizontal: 12, borderRadius: 999, alignSelf: "flex-start" },
  glyphs: { flexDirection: "row", gap: 1 },
});
