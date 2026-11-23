import * as Location from "expo-location";
import type { Client } from "../api/client";
import type { NearbyStop } from "../api/types";

/** "330 m" below a kilometre, "12.5 km" above. */
export const distanceText = (m: number) => (m < 1000 ? `${m} m` : `${(m / 1000).toFixed(1)} km`);
/** Further than this from every stop and you are probably outside Delhi: show the stop but do not pick it for you. */
export const FAR_METRES = 20000;

export type LocateResult = { ok: true; stops: NearbyStop[] } | { ok: false; reason: "denied" | "failed" };

/** Ask for permission once, read one position, and return the nearest stops. The position is never stored or sent anywhere
 *  except to the planner's /stops/nearby endpoint. */
export async function nearestStops(client: Client, limit = 5): Promise<LocateResult> {
  try {
    const { status } = await Location.requestForegroundPermissionsAsync();
    if (status !== "granted") return { ok: false, reason: "denied" };
    const { coords } = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
    return { ok: true, stops: await client.nearby(coords.latitude, coords.longitude, limit) };
  } catch {
    return { ok: false, reason: "failed" };
  }
}
