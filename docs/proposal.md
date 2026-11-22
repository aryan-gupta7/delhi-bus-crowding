# Proposal: crowding-aware journey planner for Delhi buses (Problem 2, Phase 1)

**Problem.** Show commuters how crowded a bus is next to its travel time, and let them trade speed for comfort,
using ~2.56 million October e-ticket records and static GTFS. The tickets are a ~2.6% digital-ticket sample with
no trip identifiers and no alighting counts.

**Approach.** A rerunnable pipeline (one config, one manifest, deterministic) estimates a *pressure index* (sampled
passengers per scheduled seat) by route, direction, stretch, hour and day-type, turns it into relative bands
(Lighter / Busy / Very busy) and tests, with a scenario ensemble, which levels and which "calmer option"
recommendations survive uncertainty about who the tickets represent. A planner (direct and one-transfer, scheduled
GTFS) shows travel time and crowding side by side, offers a "More comfortable" option only when its advantage holds,
and says "No clearly calmer option" otherwise. Each recommendation carries a robustness value: the smallest
difference in ticket coverage between the two options' routes that would erase the advantage.

**What is new.** Treating the tickets as partially identified (within a route-hour yes; across routes or hours no)
and making that the operational rule of the planner, rather than scaling the sample up with an unverifiable factor.

**Validation.** Held-out whole weekdays with proper scoring rules on counts and OD pairs against explicit baselines,
a like-for-like flow target with noise ceilings, week-to-week stability, known-pattern checks, planner robustness,
a rerun on time-sliced files with frozen thresholds, and gates for the data assumptions
(`docs/validation_report.md`, `docs/technical_note.md`).

**Deliverables.** Repository with README (`make setup && make all`), technical note, validation report, planner demo
(`make serve`), demo video script (`docs/demo_script.md`).

**Honest limits.** Relative levels only; seat counts are an assumption; static timetable ("usually", not live);
weekends rougher; the model ties, but does not beat, the unsmoothed pooled flow on level agreement.
