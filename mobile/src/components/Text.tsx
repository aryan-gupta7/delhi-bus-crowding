import { Text as RNText, type TextProps } from "react-native";
import { font } from "../theme/tokens";
import { useApp } from "../state/AppState";
import { useTheme } from "../theme/ThemeProvider";

type Tone = "ink" | "sec" | "mut" | "accent";
type Props = TextProps & { tone?: Tone; size?: number; medium?: boolean; mono?: boolean; display?: boolean };

/** The only text primitive. Geist 400/500; `mono` is Geist Mono 500 for plates, clock times and ticks;
 *  `display` is the heading style (500, tight tracking, line height 1.08). */
export function Text({ tone = "ink", size = 15, medium = false, mono = false, display = false, style, ...rest }: Props) {
  const { palette } = useTheme();
  const { lang } = useApp();
  const color = tone === "accent" ? palette.accInk : palette[tone];
  const family = mono ? font.mono : medium || display ? font.medium : font.regular;
  return (
    <RNText
      {...rest}
      style={[
        { color, fontSize: size, lineHeight: Math.round(size * (display ? 1.08 : 1.4)), fontFamily: family, fontVariant: ["tabular-nums"],
          letterSpacing: mono || lang === "hi" ? 0 : display ? -0.035 * size : -0.01 * size },   // tight tracking breaks Devanagari conjuncts
        style,
      ]}
    />
  );
}
