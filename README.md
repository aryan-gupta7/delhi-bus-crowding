# Delhi bus crowding planner

A **decision-support tool under partial identification**. From ~2.56 million October e-ticket records
(a ~2.6% sample of riders, no trip IDs, no alighting counts) plus static GTFS, it estimates *where along a
bus route, and when, riders are relatively crowded*, and helps a commuter choose between a faster and a
calmer option — **without claiming more than the data can support**. When the data cannot tell whether a
calmer option is really calmer, the planner says "No clearly calmer option for this trip".

Read [docs/identifiability.md](docs/identifiability.md) first: it explains what the tickets can and cannot
tell us (one route within one hour: yes; across routes or hours: no) and what we do about it.

## Quick start

Requires [uv](https://docs.astral.sh/uv/) (it installs the pinned Python 3.12 and the dependencies).

```bash
# 1. put the two inputs where config.yaml expects them (they are not in the repo)
#      data/October-Delhi.csv     the ticket file (schema below)
#      data/gtfs/*.txt            Delhi buses static GTFS (routes, trips, stops, stop_times, ...)
make setup       # uv sync
make all         # pipeline S0-S8, ~1.5 min on 16 cores; writes out/ and out/run_manifest.json
make gates       # gates G1-G7 (non-zero exit on a blocking failure)
make test        # 40+ fast unit and mini end-to-end tests
make serve       # planner + operator view at http://127.0.0.1:8000
make validate    # held-out validation -> out/validation/report.md (about 10 minutes; see below)
```

Ticket CSV columns: `passenger_count, amount, vehicle_number, ticket_type_id, end_stop_name, route,
start_stop_name, created_at (IST, ISO 8601), is_ac`. `route` equals GTFS `route_short_name` (e.g. `102ADOWN`).

**Rerunning on another ticket file or month:** change `paths.tickets` in `config.yaml` (or copy the file and
pass `--config other.yaml`) and run `make all`; `python -m crowd run --frozen-cuts out/cuts.json` scores a new file against a reference run's band cuts. Nothing in the code names a date, route or stop; the
eligibility rule (which days and hours count) is data-driven. `crowd validate --only v3` runs the pipeline
on two time slices and checks that frozen thresholds and GTFS-only artefacts carry over.

`make all` twice gives the same `reproducibility_hash` (config + every data output; timings are not hashed).
Stages whose inputs, config sections and source files are unchanged are skipped.

## What you get (`out/`)

| File | What it is |
|---|---|
| `crowding_cells.parquet` | The main table, one row per (route, direction, stretch, hour, day-type): `level` (1 Lighter, 2 Busy, 3 Very busy, 0 No estimate), `robust_in_range`, evidence `tier`, `pi_central` (pressure index), `N` buses/hour, `n_tickets_eff`, flags |
| `levels.npy` | Per-draw levels `uint8[n_cells, K]`, row-aligned with the table (used by the planner) |
| `stretches.geojson`, `route_hour_matrix.csv` | Map geometry and the route × hour grid for the operator view |
| `cuts.json` | The frozen band cuts (central + per draw) and the scenario grid |
| `run_manifest.json` | Input/output hashes, config hash, git commit, ingest report, timings |
| `gates.json`, `validation/report.md` | Gate results and the held-out validation report |
| `estimator_fit.json` | Fitted α, φ, Dirichlet strengths and the shrinkage multiplier chosen on the inner split |

Command line: `python -m crowd query --route 8UP --from "Ali Village" --to "Mahamaya Flyover West" --time 09:30`
returns the crowding along one bus ride. The HTTP API (`/stops`, `/plan`, `/crowding`, `/operator/*`,
`/gates`, interactive docs at `/api/docs`) reads `out/` once and never writes.

## How it works (eight lines)

1. **S0** eligibility: day-type first; two ticket streams (NULL-vehicle / tagged) checked against their own day-type medians; stream-fault days and outage hours dropped.
2. **S1** GTFS canonical pattern per route (longest trip), scheduled offsets, segments, frozen GTFS-only stretches.
3. **S2** ticket stop names → stops by a cascade: normalise, exact, composite split, on-route fuzzy with an ambiguity guard, coordinate fallback; loop-aware pair constraint.
4. **S3** counts and OD pairs per (route, hour, day); observed passage-hour flows for validation.
5. **S4** scheduled buses N per segment-hour and seats → `Z`.
6. **S5** volume: Poisson-gamma with zero days, day-dispersion φ; spatial profile: hierarchical Dirichlet (length class → route → band → hour); closed-form passage-hour convolution → `Q̂`.
7. **S6/S7** pressure index `Π = Q̂ / Z` per **seat**; relative bands from exposure-weighted percentiles; a scenario ensemble (hour tilt θ, route effect ε) decides whether a level is `robust_in_range`.
8. **Planner:** direct and one-transfer journeys on scheduled GTFS; discomfort-adjusted time; "More comfortable" only if its advantage holds in ≥ 80% of draws; each card carries the robustness value Γ\*.

The design documents are in [design/](design/): `mechanism.md` (method, validation, gates),
`business-logic.md` (rules for levels, tiers and the planner), `development-plan.md` (engineering plan and
the log of deviations made while building, §16b).

## Repository map

```
crowd/            the package: one module per stage (ingest, eligibility, gtfs, matching, flows, supply,
                  estimator, index, tiers, ensemble, outputs), pipeline.py (stage runner + manifest),
                  stages.py (I/O glue + registry), gates.py, tuning.py, planner/, api/, validation/
config.yaml       every parameter (no constants in code)
web/              single-page UI (MapLibre)       tests/   unit + mini end-to-end + real-data goldens
design/ docs/ reviews/   design docs, short docs, independent reviews of the design and the code
```

## Honest limitations

* The tickets cannot identify cross-route or cross-hour scale (see `docs/identifiability.md`). Levels are
  **relative** bands, never "seats available"; the planner only recommends a calmer option when the advantage
  survives the scenario ensemble, and says how much capture error it can absorb (Γ\*). The ensemble is a
  sensitivity analysis over an assumed family (θ, ε), **not a posterior probability**.
* Seat counts per bus (39 AC / 35 non-AC) are an assumption: the tickets carry no bus length. Gate G3 stays open.
* The planner uses the static timetable: travel times are scheduled, crowding is "usually", never live.
* About 12% of ticket stop-name weight (and 20% of passengers have at least one end unmatched) remains unmatched, concentrated at hubs, so pinch points are biased away from hubs.
* Weekend/holiday results are rougher (one all-days GTFS service; evidence tier capped at Low).
* Validation checks the estimator of the sampled process on held-out days. It cannot show crowding truth.
  See `out/validation/report.md` for what was measured, including where the model does **not** beat a baseline.
