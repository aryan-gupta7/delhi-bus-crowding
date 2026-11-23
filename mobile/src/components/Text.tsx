import { Text as RNText, type TextProps } from "react-native";
import { font } from "../theme/tokens";
import { useTheme } from "../theme/ThemeProvider";

type Tone = "ink" | "sec" | "mut" | "accent";
type Props = TextProps & { tone?: Tone; size?: number; medium?: boolean };

/** The only text primitive: Inter 400 or 500, tabular figures, colour from the theme. */
export function Text({ tone = "ink", size = 15, medium = false, style, ...rest }: Props) {
  const { palette } = useTheme();
  const color = tone === "accent" ? palette.accInk : palette[tone];
  return (
    <RNText
      {...rest}
      style={[{ color, fontSize: size, lineHeight: Math.round(size * 1.4), fontFamily: medium ? font.medium : font.regular, fontVariant: ["tabular-nums"] }, style]}
    />
  );
}
