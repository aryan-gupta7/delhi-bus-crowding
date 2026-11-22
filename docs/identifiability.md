# What the data can and cannot tell us

The tickets are a **sample** of Delhi bus riders: about 2.6% of an approximate 40.8 lakh daily riders
(the ridership base is a press figure, unverified), no free or pass travel, and 99.3% of per-passenger
fares equal to 0.9 × a ₹5/10/15/20/25 slab — so they look like one *channel* (app/QR tickets), not a
random sample. There are no trip identifiers, no alighting counts, and 48.5% of tickets have no
vehicle number. We therefore observe

> Q(route, segment, hour, day-type) = sampled passengers crossing a segment of a route-direction in an hour,

while what a rider experiences is passengers per seat, `PS = κ · Π`, with

* **Π = Q / Z**, the *pressure index*: sampled passengers per **scheduled seat** passing that segment
  in that hour (`Z` = scheduled buses × seats per bus, so a 9 m and a 12 m bus are not treated alike);
* **κ(route, hour) = capture / operated-vs-scheduled**, a scale the data cannot reveal.

## Which comparisons are identified

| Comparison a planner needs | Identified? | Why |
|---|---|---|
| Segments of **one route in one hour** (where is the pinch point?) | **Yes**, if capture is constant along the route in that hour | κ cancels in the ratio |
| **One route, different hours** ("leave later") | **No** | Sampled passengers peak about 5.8× over the midday trough while the timetable is flat in trips per hour; capture, supply error and genuine crowding cannot be separated |
| **Different routes, same hour** ("take the other bus") | **No** | Route-level volume per scheduled trip spans a 9× range that is only "true demand" if capture is uniform across routes |
| Weekday vs weekend | **No** | One GTFS service runs all seven days |

A percentile band of Π is invariant to a **common** scale error only (ρ, ω, κ0 and a common seat scale
all cancel). It is *not* invariant to anything that varies by hour or route, which is exactly what a
"leave later" or "take the other bus" recommendation depends on.

## What the system does about it

* Levels are **relative bands** (Lighter / Busy / Very busy) of Π, never "seats available".
* A **scenario ensemble** perturbs the two unidentified things that matter — an hour tilt θ and a route
  effect ε — and a level is marked *robust in range* only if it holds in at least 80% of the draws.
  This is a sensitivity analysis over an assumed family, not a posterior probability.
* A "More comfortable" card is shown only if its advantage survives the same ensemble. Each card also
  carries a **robustness value Γ\***: the smallest difference in ticket coverage between the two
  options' routes that would erase the advantage.
* Validation checks the estimator of the *sampled* process on held-out days. It cannot show crowding
  truth, and the technical note says so.
