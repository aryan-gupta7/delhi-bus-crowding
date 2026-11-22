# Demo script (about 3 minutes)

Start `make serve` and open http://127.0.0.1:8000. Use **peak** queries: off-peak almost everything is
"Lighter" by construction, so the Fastest and More comfortable options rarely differ.

1. **The data and its limits (30 s).** "2.56 million October tickets, about 2.6% of riders, no trip IDs, no
   alighting counts. So we can see *where along a route* people ride in an hour — the pinch point — but
   not how a route compares with another route or one hour with another. We say that on every screen."
2. **Operator view (40 s).** Open *Operator view*, weekday. Heat grid = worst stretch of each route by hour
   (glyph count + word + fill; hatched = low evidence; dashed = no estimate). Click a busy route, choose 09:00:
   the stretch lines on the map show the pinch point.
3. **A peak commute (50 s).** Plan *Ali Village → MahaMaya Flyover West*, 09:00. Show the Fastest card:
   legs, per-leg level, evidence tier, a "leans" mark where the level depends on assumptions.
4. **A trip where the answer is "No clearly calmer option" (30 s).** Same query. Explain why: a calmer
   route has to look ≥ 1.6× lighter to survive our uncertainty about who the tickets represent. Show the
   robustness value on a card that *is* shown ("holds unless coverage differs by more than 2.4×").
5. **Validation in 20 s.** Show `out/validation/report.md`: held-out days, baselines B0–B5, noise ceilings;
   the model beats the strong per-cell baseline on count log score and by a wide margin on OD profiles, and the
   honest weaknesses (flow rank vs the unsmoothed baseline; the ±2-stop destination shift).
