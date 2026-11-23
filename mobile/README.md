# Mobile app (Expo / React Native)

A phone app for the same planner. It has no logic of its own: it calls the HTTP API (`/stops`, `/plan`,
`/examples`, `/operator/stretches`) and draws what comes back, with the wording rules in `web/i18n.js` (always "usually", never "now" for crowding, never "seats available").

Screens: **Plan a trip** · **Results** (with a calmer option, or "No clearly calmer option" plus the leave-later chip) ·
**Journey detail** (per-stretch strip, "leans" tooltip, stepped leave-later control Now, +10 … +60) ·
**Map** (the planned stretches, schematic) and a stop picker with a street map · **How to read this** (weekday/weekend, settings).
No account. Light and dark follow the system and can be overridden; English and Hindi (the Hindi is a first pass).

## Run it

Needs [bun](https://bun.sh) (or Node 20+ with npm) and the planner API running (`make serve` in the repo root,
listening on `0.0.0.0` if a phone should reach it: `uv run python -m crowd serve --host 0.0.0.0`).

```bash
cd mobile
bun install
bun run start            # then press a (Android emulator) or scan the QR code with Expo Go
```

The API address is set in the app under **About → Settings → Server address** and is remembered; a saved address
overrides the default, so check it first if the stop list is empty. Defaults: `http://10.0.2.2:8000` (the Android
emulator's name for the host machine). `EXPO_PUBLIC_API_BASE_URL` overrides the default when Metro starts.

**On a real phone, over Wi-Fi** (same network as the computer):
1. Start the planner so other devices can reach it: `uv run python -m crowd serve --host 0.0.0.0 --port 8000`.
2. `bun run start`, then in Expo Go choose "Enter URL manually" and enter `exp://<computer address>:8081`.
3. In the app: About → Settings → Server address → `http://<computer address>:8000` → Save.

**Over USB** (no shared network): turn on USB debugging, then
`adb reverse tcp:8000 tcp:8000 && adb reverse tcp:8081 tcp:8081`, use `exp://127.0.0.1:8081` and the address
`http://127.0.0.1:8000`. The tunnel disappears when the cable is unplugged.

The planner API is read-only and has no login: use `--host 0.0.0.0` only on a network you trust.

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
* **Low-end Android.** No blur, no gradients inside components, no map tiles outside the stop picker, one font family (Geist 400/500, plus Geist Mono 500 for route plates, clock times and slider ticks: three font files in total), no shadow on
  cards (only the dock and the tooltip float), last result cached in AsyncStorage so a dropped connection still shows something.

## Choices to know about

* Hindi text uses the phone's own Devanagari font (Noto Sans Devanagari on Android) instead of a bundled copy, to keep the bundle small.
* The look is the revised design: paper and graphite neutrals, one cobalt accent, ink primary buttons, no livery stripe or illustrations.
* The Map tab is a schematic of the planned stretches (width follows sampled riders). The stop picker ("Pick on map") is a street map of every stop; it loads MapLibre and OpenStreetMap tiles from the internet, so it needs a connection. The rest of the app does not.
* The rank-stability view of the operator mock-up ("Rank held 9 of 10") is not built: the pipeline does not store per-draw rankings.
* The operator view is web-only; the phone app is for riders.
