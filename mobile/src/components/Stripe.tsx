import { View } from "react-native";
import { livery } from "../theme/tokens";

/** The five-colour livery stripe under the header. Decorative only. */
export function Stripe() {
  return (
    <View style={{ flexDirection: "row", height: 4 }} accessibilityElementsHidden importantForAccessibility="no">
      {livery.map((c) => <View key={c} style={{ flex: 1, backgroundColor: c }} />)}
    </View>
  );
}
