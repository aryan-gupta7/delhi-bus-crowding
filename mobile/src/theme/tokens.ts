/** Design tokens. web/style.css carries the same values as CSS variables; tests/test_mobile_tokens.py
 *  fails if the two drift apart. */
export type LevelCode = 1 | 2 | 3;
export type LevelTokens = { fill: string; ink: string; border: string };

export type Palette = {
  bg: string; surf: string; border: string; ink: string; sec: string; mut: string;
  accent: string; accSubtle: string; accInk: string; onAccent: string; seg: string;
  levels: Record<LevelCode, LevelTokens>;
};

export const light: Palette = {
  bg: "#F4F7FE", surf: "#FFFFFF", border: "#D8DFEF", ink: "#0E1530", sec: "#3A4566", mut: "#56607F",
  accent: "#1F5FE0", accSubtle: "#E3ECFF", accInk: "#1646B8", onAccent: "#FFFFFF", seg: "#E6ECF8",
  levels: {
    1: { fill: "#86E3B8", ink: "#05301F", border: "#1E9E6A" },
    2: { fill: "#FFA41B", ink: "#2B1600", border: "#C86F00" },
    3: { fill: "#C8174A", ink: "#FFFFFF", border: "#C8174A" },
  },
};

export const dark: Palette = {
  bg: "#0A0F1F", surf: "#131A31", border: "#2A3556", ink: "#EEF2FF", sec: "#BAC4E4", mut: "#9AA6CC",
  accent: "#5B94FF", accSubtle: "#1B2B57", accInk: "#A9C6FF", onAccent: "#06122E", seg: "#1B2340",
  levels: {
    1: { fill: "#86E3B8", ink: "#05301F", border: "#86E3B8" },
    2: { fill: "#FFA41B", ink: "#2B1600", border: "#FFA41B" },
    3: { fill: "#FF4D7E", ink: "#2A0010", border: "#FF4D7E" },
  },
};

/** The five livery colours, left to right. */
export const livery = ["#1FA25A", "#F58220", "#1F5FE0", "#C8174A", "#4CC3F0"] as const;

export const radius = { card: 24, inner: 20, control: 14, chip: 999 } as const;
export const TOUCH = 44;
export const font = { regular: "Inter_400Regular", medium: "Inter_500Medium" } as const;
