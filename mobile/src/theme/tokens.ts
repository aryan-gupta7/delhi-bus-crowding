/** Design tokens (revised design: paper and graphite neutrals, one cobalt accent, three crowding colours).
 *  web/style.css carries the same values as CSS variables; tests/test_mobile_tokens.py fails if the two drift apart. */
export type LevelCode = 1 | 2 | 3;
export type LevelTokens = { fill: string; ink: string; border: string; hatch: string };

export type Palette = {
  bg: string; surf: string; surf2: string; border: string; track: string;
  ink: string; sec: string; mut: string; accent: string; accInk: string; map: string;
  levels: Record<LevelCode, LevelTokens>;
};

export const light: Palette = {
  bg: "#F6F6F7", surf: "#FFFFFF", surf2: "#EFEFF1", border: "#E1E2E6", track: "#D5D7DD",
  ink: "#121316", sec: "#41444C", mut: "#62656E", accent: "#2F5FE8", accInk: "#2549C7", map: "#E9EAEE",
  levels: {
    1: { fill: "#A7E8C5", ink: "#08321F", border: "#2F9E6A", hatch: "rgba(8,50,31,.22)" },
    2: { fill: "#FFB547", ink: "#2E1A00", border: "#C98410", hatch: "rgba(46,26,0,.22)" },
    3: { fill: "#D1264B", ink: "#FFFFFF", border: "#D1264B", hatch: "rgba(255,255,255,.28)" },
  },
};

export const dark: Palette = {
  bg: "#0E0F11", surf: "#16181B", surf2: "#1D1F23", border: "#2A2D33", track: "#2F3238",
  ink: "#F1F1EF", sec: "#C2C4CB", mut: "#9A9DA6", accent: "#86A6FF", accInk: "#86A6FF", map: "#131518",
  levels: {
    1: { fill: "#A7E8C5", ink: "#08321F", border: "#A7E8C5", hatch: "rgba(8,50,31,.22)" },
    2: { fill: "#FFB547", ink: "#2E1A00", border: "#FFB547", hatch: "rgba(46,26,0,.22)" },
    3: { fill: "#FF5C85", ink: "#2B0011", border: "#FF5C85", hatch: "rgba(43,0,17,.25)" },
  },
};

export const radius = { card: 24, inner: 20, control: 14, button: 16, chip: 999 } as const;
export const TOUCH = 44;
/** One family: Geist 400/500; Geist Mono 500 only for route plates, clock times and slider ticks.
 *  Hindi falls back to the system Devanagari font (Noto Sans Devanagari on Android). */
export const font = { regular: "Geist_400Regular", medium: "Geist_500Medium", mono: "GeistMono_500Medium" } as const;
