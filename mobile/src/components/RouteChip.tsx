import { View } from "react-native";
import { useTheme } from "../theme/ThemeProvider";
import { Text } from "./Text";

export function RouteChip({ route, small = false }: { route: string; small?: boolean }) {
  const { palette } = useTheme();
  return (
    <View style={{ height: small ? 24 : 28, paddingHorizontal: 10, borderRadius: 8, backgroundColor: palette.ink, justifyContent: "center", alignSelf: "flex-start" }}>
      <Text size={small ? 12 : 13} mono style={{ color: palette.bg }}>{route}</Text>
    </View>
  );
}
