import { View } from "react-native";
import { useApp } from "../state/AppState";
import { useTheme } from "../theme/ThemeProvider";
import { PersonGlyph } from "./PersonGlyph";
import { Text } from "./Text";

/** Logo mark: three person glyphs in ink, ascending in size, then the wordmark. */
export function Logo() {
  const { t } = useApp();
  const { palette } = useTheme();
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 10 }} accessibilityRole="header">
      <View style={{ flexDirection: "row", alignItems: "flex-end", gap: 2 }}>
        {[0.8, 1, 1.2].map((scale) => <PersonGlyph key={scale} color={palette.ink} scale={scale} />)}
      </View>
      <Text size={17} display>{t("appTitle")}</Text>
    </View>
  );
}
