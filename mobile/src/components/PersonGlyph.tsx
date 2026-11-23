import Svg, { Path } from "react-native-svg";

/** One rider: head and shoulders, drawn in a 9x11 box like the design. `scale` 1 is 9x11 points. */
export function PersonGlyph({ color, scale = 1 }: { color: string; scale?: number }) {
  return (
    <Svg width={9 * scale} height={11 * scale} viewBox="0 0 9 11" accessibilityElementsHidden importantForAccessibility="no">
      <Path d="M4.5 0a2.4 2.4 0 1 1 0 4.8A2.4 2.4 0 0 1 4.5 0zM0 11c0-3 1.9-4.6 4.5-4.6S9 8 9 11z" fill={color} />
    </Svg>
  );
}
