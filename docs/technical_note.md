# Technical note: a crowding-aware journey planner for Delhi buses

**What this is.** A decision-support tool under partial identification, not a crowding-truth predictor. From
~2.6% of riders' tickets it shows *where along a route, and when, riders are relatively crowded*, and
recommends a calmer option **only when the advantage survives stated uncertainty about who the tickets
represent**. Numbers below are from `out/validation/report.md` (regenerate with `make validate`); every
claim says whether it was measured on held-out days or is an assumption.

## 1. Problem and data

2,559,899 e-tickets (2,753,606 passengers) for October 2026: `passenger_count, amount, vehicle_number,
ticket_type_id, start/end stop name, route, created_at (IST), is_ac`, plus static GTFS v32 (2,574 route
directions, 80,357 trips, 6,862 stops). Facts that shape the method: the tickets are a ~2.6% digital channel
(fares are 0.9 × a slab, no free travel), 48.5% have no vehicle number, there are no trip identifiers and no
alighting counts, and the GTFS has one all-days service.

## 2. What can and cannot be identified

The data identify *the shape of load along one route within one hour* (the pinch point). They do **not**
identify the scale that converts sampled passengers to real riders, so comparisons **across routes**, **across
hours** or **weekday vs weekend** are unidentified (`docs/identifiability.md`). Sampled passengers peak 5.8×
over the midday trough while the timetable is flat; the ticket peak/midday ratio is 6.9× the timetable's
(gate G7). A percentile band of the pressure index is invariant to a common scale error only; ρ, ω, κ0 and a
common seat scale cancel, but an hour tilt θ = ±0.2 moves 9% of passenger exposure to another level.

## 3. Method

* **Eligibility (S0).** Day-type first (weekend, or weekday below 70% of the median weekday total); two
  streams (NULL-vehicle / tagged) checked against their own day-type medians; stream-fault days and outage
  hours dropped. It reproduces every anomaly found by profiling (6 Oct outage, 17–19 Oct stream drop, 29 Oct
  evening dip, holiday-like 2 and 20 Oct, no Sunday peak masked). *The thresholds were chosen on October, so
  gate G1 is a regression test of the rule, not evidence it generalises.*
* **GTFS (S1).** Canonical pattern = longest trip; every trip maps onto it as a stop-id subsequence (0 of 80,357
  unmapped; 67 loop routes handled); scheduled offsets; segments = stop intervals; GTFS-only frozen stretches.
* **Stop matching (S2).** Per-route cascade: exact → composite split → on-route fuzzy with an ambiguity guard →
  coordinates of the same-named stop. Both-ends coverage 80.1% (top-250 routes 81.8%); exact matching alone was
  51%. The fare-vs-distance rank correlation of fuzzy-matched tickets equals that of exact ones (0.864 vs
  0.858; fares are not used in matching), which supports precision. ~12% of ticket-stop weight stays
  unmatched, concentrated at hubs, so pinch points are biased away from hubs.
* **Volume (S5).** Boarding tickets per route-hour: Poisson-gamma with zero days counted, a direction-class
  prior share, no prior mass where the route does not run, and a day-dispersion φ fitted on training days.
  Every route-resolved ticket counts, so volume does not depend on the stop-match rate.
* **Spatial profile (S5).** A hierarchical Dirichlet over board→alight pairs (length class → route → hour band →
  boarding hour), strengths by marginal likelihood per route-volume class, multiplied by a shrinkage factor
  **chosen on an inner day-blocked split of the training days for the flow-shape objective** (see §5, trade-off).
  A closed-form passage-hour convolution turns boarding-hour volumes into flows by passage hour (27.8% of
  passenger-segments are passed in a later hour than boarding).
* **Index and levels (S6/S7).** Pressure `Π = Q̂/Z`, sampled passengers per **scheduled seat** (bus size lives in
  `Z`). Levels are relative bands from exposure-weighted percentiles (50th, 85th) per day-type, frozen in the
  run manifest. A scenario ensemble (33 draws: posterior volumes × hour tilt θ ∈ {−0.4,−0.2,0} × route effect
  ε ~ N(0, 0.4²)) marks a level `robust_in_range` if it holds in ≥ 80% of draws. **It is a sensitivity analysis
  over an assumed family, not a posterior probability.** Cells with no evidence carry level 0 ("No estimate").
* **Planner.** Direct and one-transfer journeys on scheduled GTFS; discomfort-adjusted time with ordinal
  multipliers (1.0, 1.5, 2.3) borrowed from stated-preference studies; "More comfortable" appears only if its
  advantage ≥ max(5 min, 10%) in the central scenario **and** in ≥ 80% of draws. Each card carries the
  **robustness value Γ\***: the smallest difference in ticket coverage between the two options' routes that
  would erase the advantage (the E-value / robustness-value idea of sensitivity analysis, applied to sampling capture).

## 4. Assumptions and where the estimate is least reliable

Capture is constant along a route within an hour (A-3); declared destination ≈ true alighting (A-4; gate G6);
unmatched tickets share the matched spatial profile (A-5: ride length supported by fares, location biased
toward non-hubs); seat counts 39 AC / 35 non-AC (A-9, unverified, the tickets carry no bus length); the hour-tilt
range and σ_r = 0.4 are invented priors (A-10); weekend supply = weekday supply and weekend tiers are capped at
Low. Least reliable: cross-route and cross-hour comparisons; weekends; stretches near hubs; routes with few
tickets (evidence tier shows this).

## 5. Validation (held-out weekdays: 11 train, 8 test; nothing fitted on test days)

* **Counts** (NB log score per cell-day, higher is better): model −0.883 vs the strong per-cell baseline B5
  −0.895, Poisson B0 −0.939, citywide-prior −1.116; better in every volume tier. 80% intervals cover 82.3%
  (B5 81.6%) with a lower interval score.
* **OD pairs** (log score per held-out ticket): with strengths as fitted by marginal likelihood −5.26, a plain
  route all-day profile −5.67, the raw band profile −6.05, uniform −6.94.
* **The trade-off, stated plainly.** The strengths that maximise the OD-pair likelihood blur where along a route
  the load peaks (within-route-hour shape Spearman 0.796). The shrinkage factor chosen for the flow objective
  restores it (0.842, B2 0.836) but costs OD likelihood (−5.93, worse than the route all-day profile on the
  busier tiers). The planner uses the flow-tuned model.
* **Flow rank agreement** against a like-for-like empirical test-day flow (rescaled for unmatched tickets): all
  cells model 0.819 vs the unsmoothed pooled flow B2 0.833 (replicate ceiling 0.879, noise-free ceiling
  0.938). Level with B2 in the busiest tier (0.943 vs 0.944), ahead in the middle tier (0.831 vs 0.826),
  behind in the sparsest tier (0.587 vs 0.602). **The model does not beat B2 on overall rank agreement.**
* **Levels** (weighted kappa against the held-out target, same cells for every predictor, each with its own training cuts): model 0.830, B2 0.830, model with strengths as fitted 0.807. A tie with B2: the levels a commuter sees are as good as the unsmoothed estimate and smoother in sparse cells.
* **Known patterns (V7):** all assertions hold (two weekday peaks; inbound routes busier in the AM and outbound
  in the PM; weekends lighter). The hub check is weak (the hub list is an assumption).
* **Planner (V8):** 200 random queries, 98.5% answered, no crashes, p95 latency 0.32 s.
* **Do advice-level results carry to held-out days (V10)?** Of 34 shown "More comfortable" cards, all 34 still
  had the lower adjusted time on held-out days (and still cleared the margin); of 9 candidates the robust rule
  suppressed, 78% did and 44% cleared the margin. Small samples.
* **Rerun (V3):** two time slices run end to end, GTFS-only artefacts bit-identical to the reference,
  weekday level agreement under frozen thresholds κ 0.93–0.94; a fresh-directory rerun reproduces the
  reference hash. Slices are subsets of the data, so this tests determinism, not generalisation.
* **Sensitivity (V9):** the discomfort multipliers move recommendations most (3.5–8%); the hour tilt and route
  effect barely move them. About half of exposure is robust in range at σ_r = 0.4 (77% at σ_r = 0).
* **Gates:** G1, G2 (81.8% ≥ 65%), G2b, G5 pass. **G6 fails**: moving declared destinations 2 stops upstream
  drops segment-flow rank correlation to 0.911 (0.987 at +1, 0.975 at +2); the 0.95 target was never
  calibrated, so it is reported as sensitivity. G3 stays open (no bus-length table).

**What validation cannot show:** crowding truth, absolute loads, cross-route or cross-hour scale, true alighting,
or seat availability. It checks the estimator of the *sampled* process on days it did not see.

## 6. Rerun

`make setup && make all && make gates && make validate && make serve` (README). One config, one manifest,
frozen thresholds, deterministic seeds; `make all` twice gives the same hash.
