# Demo script (about 3 minutes)

Start `make serve` and open http://127.0.0.1:8000. The web page is the demo of record; the phone app (`mobile/`) is
optional and can be shown from a screen recording. Use **weekday peak** queries: off-peak almost everything is
"Lighter" by construction, so the Fastest and More comfortable options rarely differ.

**First sentence.** "Tickets can tell us where a bus route is crowded, but not exactly how crowded one route is
compared with another, so this planner only recommends a calmer bus when the data clearly support it, and tells you
when it can't."

1. **The data and its limits (30 s).** "2.56 million October tickets, about 2.6% of riders, no trip IDs, no
   alighting counts. So we can see *where along a route* people ride in an hour (the pinch point) but not how a route
   compares with another route or one hour with another. We say that on every screen."
2. **Operator view (30 s).** Open *Operator view*, weekday. The grid shows the worst stretch of each route by hour
   (glyph count + word + fill; ringed = medium evidence, hatched = low; dashed = no estimate). Click a busy route and
   hour: the detail panel shows the pressure index and the labelled scenario ("Scenario, not measured").
3. **A card that is shown (50 s).** *Prithvi Raj Road to Supreme Court*, weekday 08:57. Fastest: bus 502DOWN, Very
   busy, 20 min. More comfortable: bus 335UP, Lighter, the same 20 min, "Holds unless these routes' ticket coverage
   differs by more than 4.1×". Say it plainly: "this trip was chosen because it is one of the few where a real
   difference exists; the card appears on well under 1% of random trips." Two more examples that behave the same way:
   *Maharaja Agrasen Hospital to Bank Colony* 18:30 (918DOWN Very busy against 926DOWN Lighter, 6.5×) and
   *Pusa Road Petrol Pump/ Sadhu Vaswani Marg to Om Vihar* 18:01 (85UP Busy against 838UP Lighter, 4.4×).
4. **The common answer (30 s).** *Ali Village to MahaMaya Flyover West*, weekday 09:50: "No clearly calmer option for
   this trip." Explain: a calmer route has to look at least 1.6× lighter to survive our uncertainty about who the
   tickets represent. Open "Along the ride": the strip shows each stretch; tap one that "leans" to see the share of
   scenarios behind it.
5. **Leave later (15 s).** Move the slider: it shows the usual level for each departure up to 60 minutes later, under
   the same rule.
6. **Validation (25 s).** Show `docs/validation_report.md`: held-out days, baselines B0–B5, noise ceilings. The model
   beats the strong per-cell baseline on count log score, ties the raw-flow baseline on crowding levels, and does
   not beat it on overall flow rank. State the weaknesses first.
7. **Phone and live data (10 s, optional).** The phone app uses the same API. The portal's open GTFS-RT bus-position
   feed could add observed supply and arrival times; it carries no occupancy, so crowding stays "usually, October data".
