import { Platform } from "react-native";

/** Shadow for floating layers only (dock, tooltip). Cards never get one. */
export const floatingShadow = Platform.select({
  web: { boxShadow: "0 6px 24px rgba(10,15,31,0.18)" } as object,
  default: { elevation: 6 },
});
