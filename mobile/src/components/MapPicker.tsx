import { useEffect, useMemo, useRef, useState } from "react";
import { ActivityIndicator, Modal, Pressable, SafeAreaView, View } from "react-native";
import { WebView, type WebViewMessageEvent } from "react-native-webview";
import type { StopRef, StopTuple } from "../api/types";
import { useApp } from "../state/AppState";
import { useTheme } from "../theme/ThemeProvider";
import { radius, TOUCH } from "../theme/tokens";
import { Button } from "./Button";
import { Text } from "./Text";

type Props = { visible: boolean; focus: StopRef | null; onClose: () => void; onSelect: (s: StopRef) => void };

/** Every bus stop as a dot on a street map (MapLibre in a WebView, OpenStreetMap tiles). Tap a dot, then "Select this stop".
 *  Needs an internet connection for the map tiles; the stop list itself comes from the planner API. */
const PAGE = (dark: boolean, bg: string, ink: string) => `<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<link rel="stylesheet" href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css">
<style>html,body,#m{margin:0;height:100%;background:${bg}}.maplibregl-ctrl-attrib{font-size:10px}</style></head>
<body><div id="m"></div><script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<script>
const send = (o) => window.ReactNativeWebView.postMessage(JSON.stringify(o));
const map = new maplibregl.Map({container:"m", center:[77.2,28.62], zoom:10, attributionControl:{compact:true},
  style:{version:8, sources:{osm:{type:"raster", tileSize:256, attribution:"© OpenStreetMap contributors", tiles:["https://tile.openstreetmap.org/{z}/{x}/{y}.png"]}},
         layers:[{id:"base", type:"raster", source:"osm", paint:{"raster-saturation":-1, "raster-brightness-max":${dark ? 0.4 : 1}}}]}});
let ready = false, pending = null;
map.on("style.load", () => {
  map.addSource("stops", {type:"geojson", data:{type:"FeatureCollection", features:[]}});
  map.addSource("picked", {type:"geojson", data:{type:"FeatureCollection", features:[]}});
  map.addLayer({id:"dots", type:"circle", source:"stops", paint:{"circle-radius":["interpolate",["linear"],["zoom"],9,2.5,14,6],
    "circle-color":"${ink}", "circle-stroke-color":"${bg}", "circle-stroke-width":1}});
  map.addLayer({id:"pick", type:"circle", source:"picked", paint:{"circle-radius":11, "circle-color":"#2F5FE8", "circle-stroke-color":"#fff", "circle-stroke-width":3}});
  ready = true; if (pending) { apply(pending); pending = null; }
});
function apply(d) {
  map.getSource("stops").setData({type:"FeatureCollection", features:d.stops.map((s) => ({type:"Feature", properties:{id:s[0], name:s[1]}, geometry:{type:"Point", coordinates:[s[3], s[2]]}}))});
  if (d.focus) map.jumpTo({center:[d.focus.lon, d.focus.lat], zoom:14});
}
window.setStops = (d) => { ready ? apply(d) : (pending = d); };
map.on("click", (e) => {
  const r = 14, box = [[e.point.x - r, e.point.y - r], [e.point.x + r, e.point.y + r]];
  const hits = map.queryRenderedFeatures(box, {layers:["dots"]});
  if (!hits.length) return;
  hits.sort((a, b) => dist(a, e.lngLat) - dist(b, e.lngLat));
  const f = hits[0];
  map.getSource("picked").setData({type:"FeatureCollection", features:[f]});
  send({id:f.properties.id, name:f.properties.name, lon:f.geometry.coordinates[0], lat:f.geometry.coordinates[1]});
});
const dist = (f, p) => Math.hypot(f.geometry.coordinates[0] - p.lng, f.geometry.coordinates[1] - p.lat);
</script></body></html>`;

export function MapPicker({ visible, focus, onClose, onSelect }: Props) {
  const { client, t } = useApp();
  const { palette, isDark } = useTheme();
  const web = useRef<WebView>(null);
  const [stops, setStops] = useState<StopTuple[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [picked, setPicked] = useState<StopRef | null>(null);

  useEffect(() => {
    if (!visible || stops) return;
    client.allStops().then(setStops).catch(() => setFailed(true));
  }, [visible, stops, client]);
  useEffect(() => { if (!visible) { setPicked(null); setLoaded(false); } }, [visible]);

  useEffect(() => {
    if (!loaded || !stops) return;
    web.current?.injectJavaScript(`window.setStops(${JSON.stringify({ stops, focus })}); true;`);
  }, [loaded, stops, focus]);

  const html = useMemo(() => PAGE(isDark, palette.map, palette.ink), [isDark, palette.map, palette.ink]);

  function onMessage(ev: WebViewMessageEvent) {
    try {
      const m = JSON.parse(ev.nativeEvent.data) as { id: string; name: string; lat: number; lon: number };
      setPicked({ stop_id: m.id, name: m.name, lat: m.lat, lon: m.lon });
    } catch { /* ignore malformed messages */ }
  }

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      <SafeAreaView style={{ flex: 1, backgroundColor: palette.bg }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 12, padding: 12 }}>
          <View style={{ flex: 1 }}>
            <Text size={20} display accessibilityRole="header">{t("mapPickTitle")}</Text>
            <Text size={13} tone="mut">{t("mapPickHint")}</Text>
          </View>
          <Pressable accessibilityRole="button" accessibilityLabel={t("close")} onPress={onClose}
            style={{ width: TOUCH, height: TOUCH, borderRadius: radius.control, alignItems: "center", justifyContent: "center", backgroundColor: palette.surf, borderWidth: 1, borderColor: palette.border }}>
            <Text size={20} medium>×</Text>
          </Pressable>
        </View>
        <View style={{ flex: 1 }}>
          {!failed ? (
            <WebView ref={web} originWhitelist={["*"]} source={{ html, baseUrl: "https://localhost" }} onLoadEnd={() => setLoaded(true)} onMessage={onMessage}
              javaScriptEnabled domStorageEnabled style={{ flex: 1, backgroundColor: palette.map }} />
          ) : <Text tone="sec" style={{ padding: 16 }}>{t("error")}</Text>}
          {!stops && !failed ? (
            <View pointerEvents="none" style={{ position: "absolute", top: 12, alignSelf: "center", flexDirection: "row", gap: 8, padding: 10, borderRadius: radius.control, backgroundColor: palette.surf }}>
              <ActivityIndicator color={palette.accInk} /><Text size={13}>{t("mapLoading")}</Text>
            </View>
          ) : null}
        </View>
        {picked ? (
          <View style={{ padding: 12, gap: 8, backgroundColor: palette.surf, borderTopWidth: 1, borderTopColor: palette.border }}>
            <Text size={16} medium numberOfLines={2}>{picked.name}</Text>
            <Button label={t("selectStop")} onPress={() => { onSelect(picked); onClose(); }} />
          </View>
        ) : null}
      </SafeAreaView>
    </Modal>
  );
}
