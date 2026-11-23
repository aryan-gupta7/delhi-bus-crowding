import { useId } from "react";
import { Pressable, ScrollView, View } from "react-native";
import type { Leg } from "../api/types";
import { useApp } from "../state/AppState";
import { useTheme } from "../theme/ThemeProvider";
import { TOUCH } from "../theme/tokens";
import { Hatch } from "./Hatch";
import { PersonGlyph } from "./PersonGlyph";
import { Text } from "./Text";

type Props = { leg: Leg; selected: number | null; onSelect: (i: number) => void };

/** One tappable segment per stretch of the ride. Same encoding as the level pill: glyphs + fill, hatch for Low,
 *  ring for Medium, a dashed outline when the level only "leans". */
export function Strip({ leg, selected, onSelect }: Props) {
  const { t } = useApp();
  const { palette } = useTheme();
  const base = useId().replace(/[^a-zA-Z0-9]/g, "");
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ flexGrow: 1, gap: 4, paddingVertical: 4 }}>
      {leg.stretches.map((s, i) => {
        const code = s.level.code;
        const tok = code ? palette.levels[code] : null;
        const label = `${t("stretchN", { n: i + 1 })}, ${t(`L${code}`)}${s.robust_in_range || !code ? "" : `, ${t("leans")}`}`;
        const chosen = selected === i;
        return (
          <Pressable key={i} accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ selected: chosen }} onPress={() => onSelect(i)}
            style={{ flexGrow: 1, minWidth: TOUCH, height: 52, borderRadius: 10, overflow: "visible", alignItems: "center", justifyContent: "center",
              backgroundColor: tok ? tok.fill : "transparent",
              borderWidth: chosen ? 2 : 1, borderColor: chosen ? palette.ink : tok ? tok.border : palette.mut, borderStyle: tok ? "solid" : "dashed" }}>
            {tok && s.tier === "Low" ? <Hatch color={tok.hatch} id={`${base}h${i}`} /> : null}
            {tok ? (
              <View style={{ flexDirection: "row", gap: 1 }}>{Array.from({ length: code }, (_, k) => <PersonGlyph key={k} color={tok.ink} />)}</View>
            ) : <Text size={14} medium tone="sec">?</Text>}
            {tok && !s.robust_in_range ? (
              <View pointerEvents="none" style={{ position: "absolute", left: -5, right: -5, top: -5, bottom: -5, borderRadius: 14, borderWidth: 1.5, borderStyle: "dashed", borderColor: palette.ink }} />
            ) : null}
            {tok && s.tier === "Medium" ? (
              <View pointerEvents="none" style={{ position: "absolute", left: -2, right: -2, top: -2, bottom: -2, borderRadius: 12, borderWidth: 1, borderColor: palette.ink }} />
            ) : null}
          </Pressable>
        );
      })}
    </ScrollView>
  );
}
