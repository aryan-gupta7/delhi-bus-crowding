import { View } from "react-native";
import { useTheme } from "../theme/ThemeProvider";
import { Text } from "./Text";

type Props = { label: string; kind?: "plain" | "leans" | "inv" };

/** "leans" is a dashed-border badge, "Firm" is a plain one; the inverted kind (ink fill) marks the recommended card. */
export function Badge({ label, kind = "plain" }: Props) {
  const { palette } = useTheme();
  const style =
    kind === "leans" ? { borderStyle: "dashed" as const, borderColor: palette.ink, borderWidth: 1, backgroundColor: "transparent" }
    : kind === "inv" ? { backgroundColor: palette.ink, borderWidth: 0 }
    : { backgroundColor: palette.surf, borderColor: palette.border, borderWidth: 1 };
  return (
    <View style={[{ height: 24, paddingHorizontal: 10, borderRadius: 999, justifyContent: "center", alignSelf: "flex-start" }, style]}>
      <Text size={12} medium tone={kind === "leans" ? "ink" : "sec"} style={kind === "inv" ? { color: palette.bg } : undefined}>{label}</Text>
    </View>
  );
}
