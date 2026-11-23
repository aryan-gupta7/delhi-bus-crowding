import { Pressable, type PressableProps } from "react-native";
import { radius, TOUCH } from "../theme/tokens";
import { useTheme } from "../theme/ThemeProvider";
import { Text } from "./Text";

type Props = Omit<PressableProps, "children"> & { label: string; kind?: "primary" | "quiet" | "link" };

export function Button({ label, kind = "primary", style, ...rest }: Props) {
  const { palette } = useTheme();
  const primary = kind === "primary";
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      {...rest}
      style={(state) => [
        { minHeight: primary ? 52 : TOUCH, borderRadius: primary ? radius.button : radius.control, alignItems: "center", justifyContent: "center", paddingHorizontal: 16,
          backgroundColor: primary ? palette.ink : "transparent", opacity: state.pressed ? 0.8 : 1 },
        typeof style === "function" ? style(state) : style,
      ]}
    >
      <Text size={primary ? 16 : 14} medium tone={primary ? "ink" : "accent"} style={primary ? { color: palette.bg } : kind === "link" ? { textDecorationLine: "underline" } : undefined}>{label}</Text>
    </Pressable>
  );
}
