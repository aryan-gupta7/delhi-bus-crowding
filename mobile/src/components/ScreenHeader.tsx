import { Pressable, View } from "react-native";
import Svg, { Path } from "react-native-svg";
import { useApp } from "../state/AppState";
import { useTheme } from "../theme/ThemeProvider";
import { TOUCH } from "../theme/tokens";
import { Text } from "./Text";

export function ScreenHeader({ title, subtitle, onBack }: { title: string; subtitle?: string; onBack?: () => void }) {
  const { t } = useApp();
  const { palette } = useTheme();
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 8, paddingHorizontal: 8, paddingTop: 8 }}>
      {onBack ? (
        <Pressable accessibilityRole="button" accessibilityLabel={t("back")} onPress={onBack}
          style={{ width: TOUCH, height: TOUCH, borderRadius: 14, alignItems: "center", justifyContent: "center", backgroundColor: palette.surf, borderWidth: 1, borderColor: palette.border }}>
          <Svg width={18} height={18} viewBox="0 0 24 24"><Path d="M15 6l-6 6 6 6" stroke={palette.ink} strokeWidth={1.75} fill="none" strokeLinecap="round" strokeLinejoin="round" /></Svg>
        </Pressable>
      ) : <View style={{ width: 8 }} />}
      <View style={{ flex: 1 }}>
        <Text size={20} display numberOfLines={2} accessibilityRole="header">{title}</Text>
        {subtitle ? <Text size={13} tone="mut" numberOfLines={1}>{subtitle}</Text> : null}
      </View>
    </View>
  );
}
