import Svg, { Circle, Path } from "react-native-svg";

/** One rider: a head and shoulders. A level shows 1, 2 or 3 of these next to its word. */
export function PersonGlyph({ color, size = 14 }: { color: string; size?: number }) {
  return (
    <Svg width={size * 0.8} height={size} viewBox="0 0 12 15" accessibilityElementsHidden importantForAccessibility="no">
      <Circle cx={6} cy={3.5} r={3} fill={color} />
      <Path d="M0.5 14.5 C0.5 9.5 3 8 6 8 C9 8 11.5 9.5 11.5 14.5 Z" fill={color} />
    </Svg>
  );
}
