import { Pressable, View } from "react-native";
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
          style={{ width: TOUCH, height: TOUCH, alignItems: "center", justifyContent: "center" }}>
          <Text size={24} medium style={{ color: palette.accInk }}>‹</Text>
        </Pressable>
      ) : <View style={{ width: 8 }} />}
      <View style={{ flex: 1 }}>
        <Text size={18} medium numberOfLines={1} accessibilityRole="header">{title}</Text>
        {subtitle ? <Text size={13} tone="mut" numberOfLines={1}>{subtitle}</Text> : null}
      </View>
    </View>
  );
}
