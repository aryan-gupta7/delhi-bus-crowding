import { View, type ViewProps } from "react-native";
import { radius } from "../theme/tokens";
import { useTheme } from "../theme/ThemeProvider";

type Props = ViewProps & { variant?: "plain" | "picked" | "dashed"; inner?: boolean };

/** Cards use a border and no shadow. */
export function Card({ variant = "plain", inner = false, style, ...rest }: Props) {
  const { palette } = useTheme();
  const border =
    variant === "picked" ? { borderColor: palette.accent, borderWidth: 2 }
    : variant === "dashed" ? { borderColor: palette.mut, borderWidth: 1, borderStyle: "dashed" as const }
    : { borderColor: palette.border, borderWidth: 1 };
  return (
    <View
      {...rest}
      style={[{ backgroundColor: variant === "dashed" ? "transparent" : palette.surf, borderRadius: inner ? radius.inner : radius.card, padding: 16 }, border, style]}
    />
  );
}
