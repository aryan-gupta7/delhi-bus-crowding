import { createContext, useContext, useMemo, type ReactNode } from "react";
import { useColorScheme } from "react-native";
import { dark, light, type Palette } from "./tokens";

export type ThemeMode = "auto" | "light" | "dark";
type Theme = { palette: Palette; isDark: boolean };

const ThemeContext = createContext<Theme>({ palette: light, isDark: false });

export function ThemeProvider({ mode, children }: { mode: ThemeMode; children: ReactNode }) {
  const system = useColorScheme();
  const isDark = mode === "auto" ? system === "dark" : mode === "dark";
  const value = useMemo(() => ({ palette: isDark ? dark : light, isDark }), [isDark]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export const useTheme = () => useContext(ThemeContext);
