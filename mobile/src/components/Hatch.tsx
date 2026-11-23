import Svg, { Defs, Line, Pattern, Rect } from "react-native-svg";
import { StyleSheet } from "react-native";

/** Diagonal hatching laid over a filled shape: "Low evidence". Never the only cue, the tier is also written out. */
export function Hatch({ color, id }: { color: string; id: string }) {
  return (
    <Svg style={StyleSheet.absoluteFill} width="100%" height="100%" pointerEvents="none">
      <Defs>
        <Pattern id={id} width={6} height={6} patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <Line x1={0} y1={0} x2={0} y2={6} stroke={color} strokeWidth={2} strokeOpacity={0.45} />
        </Pattern>
      </Defs>
      <Rect width="100%" height="100%" fill={`url(#${id})`} />
    </Svg>
  );
}
