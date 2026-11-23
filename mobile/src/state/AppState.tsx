import AsyncStorage from "@react-native-async-storage/async-storage";
import Constants from "expo-constants";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { createClient, type Client } from "../api/client";
import type { SavedResult } from "../api/types";
import { translate, type Lang, type T } from "../i18n/i18n";
import type { ThemeMode } from "../theme/ThemeProvider";

const KEYS = { lang: "lang", theme: "theme", baseUrl: "baseUrl", last: "lastResult" } as const;
const DEFAULT_BASE_URL: string =
  process.env.EXPO_PUBLIC_API_BASE_URL ?? (Constants.expoConfig?.extra?.apiBaseUrl as string | undefined) ?? "http://10.0.2.2:8000";

async function read(key: string): Promise<string | null> {
  try { return await AsyncStorage.getItem(key); } catch { return null; }
}
async function write(key: string, value: string): Promise<void> {
  try { await AsyncStorage.setItem(key, value); } catch { /* storage unavailable: keep going in memory */ }
}

type AppState = {
  ready: boolean;
  lang: Lang; setLang: (l: Lang) => void;
  theme: ThemeMode; setTheme: (m: ThemeMode) => void;
  baseUrl: string; setBaseUrl: (u: string) => void;
  client: Client;
  t: T;
  lastResult: SavedResult | null; saveResult: (r: SavedResult) => void;
};

const Ctx = createContext<AppState | null>(null);

export function AppStateProvider({ children }: { children: (theme: ThemeMode) => ReactNode }) {
  const [ready, setReady] = useState(false);
  const [lang, setLangState] = useState<Lang>("en");
  const [theme, setThemeState] = useState<ThemeMode>("auto");
  const [baseUrl, setBaseUrlState] = useState(DEFAULT_BASE_URL);
  const [lastResult, setLastResult] = useState<SavedResult | null>(null);

  useEffect(() => {
    (async () => {
      const [l, th, url, last] = await Promise.all([read(KEYS.lang), read(KEYS.theme), read(KEYS.baseUrl), read(KEYS.last)]);
      if (l === "en" || l === "hi") setLangState(l);
      if (th === "auto" || th === "light" || th === "dark") setThemeState(th);
      if (url) setBaseUrlState(url);
      if (last) { try { setLastResult(JSON.parse(last) as SavedResult); } catch { /* corrupt cache: ignore */ } }
      setReady(true);
    })();
  }, []);

  const setLang = useCallback((l: Lang) => { setLangState(l); void write(KEYS.lang, l); }, []);
  const setTheme = useCallback((m: ThemeMode) => { setThemeState(m); void write(KEYS.theme, m); }, []);
  const setBaseUrl = useCallback((u: string) => { setBaseUrlState(u); void write(KEYS.baseUrl, u); }, []);
  const saveResult = useCallback((r: SavedResult) => { setLastResult(r); void write(KEYS.last, JSON.stringify(r)); }, []);

  const client = useMemo(() => createClient(baseUrl), [baseUrl]);
  const t = useCallback<T>((key, vars) => translate(lang, key, vars), [lang]);
  const value = useMemo<AppState>(
    () => ({ ready, lang, setLang, theme, setTheme, baseUrl, setBaseUrl, client, t, lastResult, saveResult }),
    [ready, lang, setLang, theme, setTheme, baseUrl, setBaseUrl, client, t, lastResult, saveResult],
  );
  return <Ctx.Provider value={value}>{children(theme)}</Ctx.Provider>;
}

export function useApp(): AppState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useApp must be used inside AppStateProvider");
  return v;
}
