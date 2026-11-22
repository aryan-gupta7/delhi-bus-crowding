# Technical note: a crowding-aware journey planner for Delhi buses

**What this is.** A decision-support tool under partial identification, not a crowding-truth predictor. From ~2.6% of
riders' tickets it shows *where along a route, and when, riders are relatively crowded*, and recommends a calmer option
**only when the advantage survives stated uncertainty about who the tickets represent**. Most trips have no clearly
calmer alternative, and the tool says so. Every number below is from `docs/validation_report.md`
(regenerate with `make validate`), which also holds the full tables, V3, V7–V11 and the gates.

## 1. Data and what it can identify

2,559,899 e-tickets (October 2026; fields `passenger_count, amount, vehicle_number, ticket_type_id, start/end stop,
route, created_at, is_ac`) and static GTFS v32. The tickets look like one digital channel (fares are 0.9 × a slab, no
free travel), 48.5% have no vehicle number, and there are no trip IDs or alighting counts.

The data identify *the shape of load along one route within one hour* (the pinch point). They do **not** identify the
scale that converts sampled passengers to real riders, so comparisons **across routes**, **across hours** and
**weekday vs weekend** are unidentified (`docs/identifiability.md`): sampled passengers peak 5.8× over the midday
trough while the timetable is flat. A percentile band of the pressure index survives a *common* scale error only; an
hour tilt of θ = ±0.2 already moves 9% of passenger exposure to another level.

## 2. Method

1. **Eligibility.** Day-type first; two ticket streams checked against their own day-type medians; stream-fault days and
   outage hours dropped. *Its thresholds were chosen on October to reproduce the known anomalies, so gate G1 is a
   regression test, not evidence it generalises.*
2. **GTFS and matching.** Canonical pattern per route (0 of 80,357 trips unmapped; 67 loop routes handled); per-route stop
   matching cascade (exact → composite split → fuzzy with an ambiguity guard → coordinates). Both-ends coverage 80.1%
   (exact matching alone: 51%); fuzzy matches show the same fare-vs-distance correlation as exact ones (0.864 vs 0.858).
   About 12% of ticket-stop weight stays unmatched, concentrated at hubs, so pinch points are biased away from hubs.
3. **Volume.** Boarding tickets per route-hour: Poisson-gamma with zero days counted, a direction-class prior, day
   dispersion φ; every route-resolved ticket counts, so volume does not depend on the match rate.
4. **Spatial profile.** Hierarchical Dirichlet over board→alight pairs (length class → route → hour band → hour), with a
   shrinkage multiplier **chosen on an inner day-blocked split of the training days for the flow objective** (optimum
   0.001, interior of the grid): the flow objective prefers almost no shrinkage. A closed-form passage-hour convolution
   converts boarding hours to passage hours (27.8% of passenger-segments cross an hour boundary).
5. **Index and levels.** Pressure `Π = Q̂/Z`, sampled passengers per **scheduled seat**. Levels (Lighter / Busy / Very busy)
   are exposure-weighted percentile bands (50th, 85th) per day-type, frozen in `cuts.json`. A scenario ensemble (hour tilt
   θ × route effect ε, 33 draws) marks a level `robust_in_range` if it holds in ≥ 80% of draws: **a sensitivity analysis
   over an assumed family, not a posterior probability.** Cells with no evidence are "No estimate".
6. **Planner.** Direct and one-transfer journeys on the scheduled timetable; discomfort-adjusted time with ordinal
   multipliers (1.0, 1.5, 2.3) borrowed from other cities. Stretches with no estimate are scored twice (crowded as
   possible for display, comfortable as possible for the worst case). A "More comfortable" card needs its advantage
   ≥ max(5 min, 10%) centrally **and** in ≥ 80% of draws **even in that worst case**; without the worst-case rule, most
   cards were an artefact of missing data on the fastest option (found in review). Each card carries a **robustness
   value Γ\***: the smallest difference in ticket coverage between the two options' routes that would erase the advantage.

## 3. Assumptions and where it is least reliable

Capture is constant along a route within an hour; declared destination ≈ true alighting; unmatched tickets share the
matched spatial profile (ride length supported by fares, location biased toward non-hubs); seats 39 AC / 35 non-AC
(assumed, no bus-length field); hour-tilt range and route-effect spread are invented priors. Least reliable:
cross-route and cross-hour comparisons, weekends (rougher timetable proxy, tiers capped at Low), stretches near hubs,
routes with few tickets (the evidence tier shows this).

## 4. Results (held-out weekdays: 11 train, 8 test; nothing fitted on test days)

* **Counts** (NB log score per cell-day): model −0.883, strong per-cell baseline B5 −0.895, citywide prior −1.116; better
  in every volume tier. 80% intervals cover 82.3% (B5 81.6%).
* **Flows and levels.** Against a like-for-like empirical test-day flow: rank agreement model 0.819 vs the unsmoothed
  pooled flow B2 0.833 (noise-free ceiling 0.938); where along a route the load peaks, model 0.842 vs B2 0.836; **level
  agreement κ 0.830 vs B2 0.830, a tie**. For flows and levels the model is statistically indistinguishable from the
  unsmoothed estimate; its gains are on counts, intervals and the evidence tiers.
* **OD pairs.** As fitted by marginal likelihood the profile scores −5.26 per held-out ticket (route all-day profile
  −5.67, uniform −6.94); the flow-tuned production profile scores −5.93, worse than the route all-day profile on the busier
  tiers. This is the trade-off between OD likelihood and flow shape, reported rather than hidden.
* **The comfortable card is rare.** 0 of 200 random queries and 20 of 2,500 peak queries show one, because it must hold under
  uncertainty. When shown, it is a real contrast with full data (e.g. Prithvi Raj Road → Supreme Court, 08:57: bus 502DOWN
  "Very busy" vs bus 335UP "Lighter", same 20 minutes, Γ\* 4.1×). Most trips have no clearly calmer option.
* **Do recommendations hold on held-out days (V10)?** Shown cards: 10 of 10 (95% interval 69–100%); suppressed candidates:
  38 of 44 (86%, 73–95%). **The intervals overlap, so the data cannot yet show that the robust rule selects better advantages
  than it suppresses**; V10 tests week-to-week stability under the same unidentified scale, not correctness.
* **Stability and checks.** Week-to-week (V11): Spearman 0.90–0.91, level κ 0.82–0.85 (two pairs of full weeks). Known
  patterns (V7) hold, the hub check is weak. A rerun on two time slices with frozen thresholds (V3) agrees at κ 0.93–0.94 and a
  fresh-directory rerun reproduces the reference hash. Gates G1, G2 (81.8%), G2b, G5 pass; G3 stays open. **G6 was changed after
  its first version failed** (segment-flow Spearman 0.91 under a −2 stop shift against an uncalibrated 0.95 target) to the
  stretch-level agreement a commuter sees (κ 0.94–0.97); both are reported.

**What validation cannot show:** crowding truth, absolute loads, cross-route or cross-hour scale, true alighting, or seat
availability. It checks the estimator of the *sampled* process on days it did not see.

## 5. Rerun

`make setup && make all && make gates && make validate && make serve` (README). One config, one manifest, frozen
thresholds, deterministic seeds; a fresh clone reproduces the same output hash.
