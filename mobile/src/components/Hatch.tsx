import { StyleSheet } from "react-native";
import Svg, { Defs, Line, Pattern, Rect } from "react-native-svg";

/** Low-evidence hatching laid over a filled shape: 135 degree stripes, 2px on a 7px period, in the level's hatch colour.
 *  Never the only cue; the tier is also written out. */
export function Hatch({ color, id }: { color: string; id: string }) {
  return (
    <Svg style={StyleSheet.absoluteFill} width="100%" height="100%" pointerEvents="none">
      <Defs>
        <Pattern id={id} width={7} height={7} patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <Line x1={1} y1={0} x2={1} y2={7} stroke={color} strokeWidth={2} />
        </Pattern>
      </Defs>
      <Rect width="100%" height="100%" fill={`url(#${id})`} />
    </Svg>
  );
}
