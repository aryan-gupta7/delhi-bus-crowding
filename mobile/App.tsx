import { Inter_400Regular } from "@expo-google-fonts/inter/400Regular";
import { Inter_500Medium } from "@expo-google-fonts/inter/500Medium";
import { useFonts } from "expo-font";
import { StatusBar } from "expo-status-bar";
import { useCallback, useEffect, useState } from "react";
import { BackHandler, View } from "react-native";
import { Dock, type Tab } from "./src/components/Dock";
import { Stripe } from "./src/components/Stripe";
import { AboutScreen } from "./src/screens/AboutScreen";
import { DetailScreen } from "./src/screens/DetailScreen";
import { MapScreen } from "./src/screens/MapScreen";
import { PlanScreen } from "./src/screens/PlanScreen";
import { ResultsScreen } from "./src/screens/ResultsScreen";
import type { ResultsView } from "./src/screens/types";
import { AppStateProvider, useApp } from "./src/state/AppState";
import { ThemeProvider, useTheme } from "./src/theme/ThemeProvider";

type Detail = { key: "fastest" | "comfortable"; offset: number };

function Shell() {
  const { ready } = useApp();
  const { palette, isDark } = useTheme();
  const [tab, setTab] = useState<Tab>("plan");
  const [results, setResults] = useState<ResultsView | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);

  // Android back: detail -> results -> plan form, and any other tab -> plan.
  const goBack = useCallback(() => {
    if (tab !== "plan") { setTab("plan"); return true; }
    if (detail) { setDetail(null); return true; }
    if (results) { setResults(null); return true; }
    return false;
  }, [tab, detail, results]);
  useEffect(() => {
    const sub = BackHandler.addEventListener("hardwareBackPress", goBack);
    return () => sub.remove();
  }, [goBack]);

  if (!ready) return <View style={{ flex: 1, backgroundColor: palette.bg }} />;
  return (
    <View style={{ flex: 1, backgroundColor: palette.bg }}>
      <StatusBar style={isDark ? "light" : "dark"} />
      <View style={{ paddingTop: 36, backgroundColor: palette.surf }}><Stripe /></View>
      <View style={{ flex: 1 }}>
        {tab === "plan" && !results ? <PlanScreen onResults={setResults} /> : null}
        {tab === "plan" && results && !detail ? (
          <ResultsScreen view={results} onBack={() => setResults(null)} onDetails={(key, offset = 0) => setDetail({ key, offset })} onAbout={() => setTab("about")} />
        ) : null}
        {tab === "plan" && results && detail ? <DetailScreen view={results} cardKey={detail.key} initialOffset={detail.offset} onBack={() => setDetail(null)} /> : null}
        {tab === "map" ? <MapScreen view={results} /> : null}
        {tab === "about" ? <AboutScreen /> : null}
      </View>
      <Dock tab={tab} onChange={setTab} />
    </View>
  );
}

export default function App() {
  const [fontsLoaded] = useFonts({ Inter_400Regular, Inter_500Medium });
  return (
    <AppStateProvider>
      {(theme) => (
        <ThemeProvider mode={theme}>{fontsLoaded ? <Shell /> : null}</ThemeProvider>
      )}
    </AppStateProvider>
  );
}
