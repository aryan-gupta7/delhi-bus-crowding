# Mobile app (Expo / React Native)

A phone app for the same planner. It has no logic of its own: it calls the HTTP API (`/stops`, `/plan`,
`/examples`, `/operator/stretches`) and draws what comes back, with the wording rules of `design/business-logic.md` §9.

Screens: **Plan a trip** · **Results** (with a calmer option, or "No clearly calmer option" plus the leave-later chip) ·
**Journey detail** (per-stretch strip, "leans" tooltip, stepped leave-later control Now, +10 … +60) ·
**Map** (schematic, no tiles) · **How to read this** (weekday/weekend, settings).
No account. Light and dark follow the system and can be overridden; English and Hindi (the Hindi is a first pass).

## Run it

Needs [bun](https://bun.sh) (or Node 20+ with npm) and the planner API running (`make serve` in the repo root,
listening on `0.0.0.0` if a phone should reach it: `uv run python -m crowd serve --host 0.0.0.0`).

```bash
cd mobile
bun install
bun run start            # then press a (Android emulator) or scan the QR code with Expo Go
```

The API address is set in the app under **About → Settings → Server address** and is remembered.
Defaults: `http://10.0.2.2:8000` (the Android emulator's name for the host machine); on a real phone use the
computer's LAN address, e.g. `http://192.168.1.20:8000`. `EXPO_PUBLIC_API_BASE_URL` overrides the default at build time.

| Command | What it does |
|---|---|
| `bun run typecheck` | TypeScript, strict |
| `bun run check:strings` | Fails if `src/i18n/strings.json` is out of date with `web/i18n.js` |
| `bun run sync:strings` | Regenerates `src/i18n/strings.json` from `web/i18n.js` (the one source of UI text) |
| `bun run export:web`, `bun run export:android` | Production bundles (a smoke test that everything compiles) |

## One design, two front ends

* **Tokens.** `src/theme/tokens.ts` holds the same colours as `web/style.css`; `tests/test_mobile_tokens.py` fails if they differ.
* **Strings.** `src/i18n/strings.json` is generated from `web/i18n.js`; `src/i18n/i18n.ts` adds the few app-only strings.
* **Encodings that carry meaning, never colour alone.** A level is person glyphs + word + fill. Evidence tier: High solid,
  Medium ringed, Low hatched. "leans" is a dashed badge, "Firm" a plain one. A stretch without an estimate is a dashed
  "? No estimate".
* **Low-end Android.** No blur, no gradients inside components, no map tiles, one font family (Geist 400/500, plus Geist Mono 500 for route plates, clock times and slider ticks: three font files in total), no shadow on
  cards (only the dock and the tooltip float), last result cached in AsyncStorage so a dropped connection still shows something.

## Choices to know about

* Hindi text uses the phone's own Devanagari font (Noto Sans Devanagari on Android) instead of a bundled copy, to keep the bundle small.
* The look is the revised design: paper and graphite neutrals, one cobalt accent, ink primary buttons, no livery stripe or illustrations.
* The map is a schematic of the planned stretches (width follows sampled riders), not a street map; the web UI has the street map.
* The rank-stability view of the operator mock-up ("Rank held 9 of 10") is not built: the pipeline does not store per-draw rankings.
* The operator view is web-only; the phone app is for riders.
