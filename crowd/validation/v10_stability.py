"""V10: does a recommendation made from training days still hold on held-out days?

The planner is run with levels from the model fitted on the training weekdays. For every query
where a "More comfortable" card is shown, the same two options are re-scored with the levels the
held-out days' empirical flows imply (using the training band cuts) and we check whether the
calmer option still has the lower adjusted time. Candidates that were *suppressed* despite a
central advantage give the comparison: the robust rule should select advantages that hold more
often than the ones it throws away.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from crowd import stages, supply as supply_mod
from crowd.ensemble import run_ensemble
from crowd.index import hour_profile_z
from crowd.outputs import CrowdingTable
from crowd.pipeline import Context
from crowd.planner.cards import margin_minutes, pick_cards
from crowd.planner.scoring import ScoredOption, Scorer
from crowd.planner.service import Planner
from crowd.validation import metrics
from crowd.validation.queries import Query
from crowd.validation.v1_holdout import FlowInputs


def _heldout_table(table: CrowdingTable, inp: FlowInputs, cuts: np.ndarray) -> CrowdingTable:
    """The crowding table with each weekday level replaced by the held-out empirical level where the
    held-out days observed flow on that stretch-hour; ``observed`` marks those cells (others keep their
    training level and are not used to judge a recommendation)."""
    geo = inp.geo
    level_grid, _, minutes, has = inp.levels(inp.target, cuts)                 # [n_stretch, 24]
    seen = has & (minutes > 0)
    stretch_row = {(geo.names[r], int(geo.stretch_id[s])): g
                   for g, (r, s) in enumerate(zip(geo.stretch_route, geo.stretch_starts))}
    cells = table.cells.copy()
    g = np.array([stretch_row[(r, sid)] for r, sid in zip(cells["route"], cells["stretch_id"])])
    hour = cells["hour"].to_numpy(np.int64)
    usable = (cells["day_type"] == "weekday").to_numpy() & seen[g, hour] & (cells["tier"] != "No estimate").to_numpy()
    cells["level"] = np.where(usable, level_grid[g, hour], cells["level"]).astype(np.int8)
    cells["observed"] = usable
    levels = np.repeat(cells["level"].to_numpy()[:, None].astype(np.uint8), table.levels.shape[1], axis=1)
    return CrowdingTable.load(cells, levels)


def _fully_judged(scored: ScoredOption, held_table: CrowdingTable) -> bool:
    """Every stretch of the scored option has an estimate in training and was observed on the held-out days."""
    return all(s.row is not None and bool(held_table.cells.at[s.row, "observed"]) for leg in scored.legs for s in leg.stretches)


def _summarise(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for group, sub in df.groupby("group"):
        n, lower, margin = len(sub), int(sub["calmer still lower"].sum()), int(sub["holds on held-out days"].sum())
        ci = metrics.clopper_pearson(lower, n)
        rows.append({"group": group, "queries": n,
                     "calmer still lower on held-out days": f"{lower}/{n} ({lower / n:.0%}; 95% CI {ci[0]:.0%}-{ci[1]:.0%})",
                     "advantage still >= margin": f"{margin}/{n} ({margin / n:.0%})"})
    return pd.DataFrame(rows)


def run_v10(ctx: Context, planner: Planner, est_train, inp: FlowInputs, train: np.ndarray, queries: list[Query]) -> pd.DataFrame:
    """Held-out holding rate of calmer-option advantages, by whether the robust rule showed them.

    Only queries whose two options are estimated on every stretch (training) *and* observed on the
    held-out days are judged; the rest are counted and dropped. This tests week-to-week stability of
    a recommendation under the same unidentified scale assumption: it cannot show that it is right.
    """
    st, cfg, geo = ctx.store, ctx.cfg, stages.geometry(ctx)
    dense = {"weekday": supply_mod.dense_supply(st.read_table("supply.parquet"), geo)["weekday"]}   # training days are weekdays
    counts = st.read_table("counts.parquet")
    z = {"weekday": hour_profile_z(counts[counts["date"].isin(train)], "weekday")}
    result = run_ensemble(est_train, dense, st.read_table("route_seats.parquet"), stages.route_coverage_array(ctx),
                          st.read_table("route_info.parquet"), z, cfg)
    cuts = {k: {"central": v["central"]} for k, v in result.cuts.items()}
    train_planner = planner.rebind(CrowdingTable.load(result.cells, result.levels), cuts, cfg)
    held_table = _heldout_table(train_planner.table, inp, np.asarray(cuts["weekday"]["central"]))
    held_scorer = Scorer(held_table, geo, cuts, cfg)

    rows, dropped = [], {"fewer than two options": 0, "no central advantage": 0, "stretch without estimate or held-out flow": 0}
    for q in queries:
        options = train_planner.options(q.from_stop, q.to_stop, q.time)
        if len(options) < 2:
            dropped["fewer than two options"] += 1
            continue
        scored = [train_planner.scorer.score(o, "weekday") for o in options]
        picked = pick_cards(scored, train_planner.scorer, "weekday", cfg)
        cand, fast = picked["candidate"], picked["fastest"]
        if cand is None or picked["advantage"] < margin_minutes(fast.t_adj, cfg):
            dropped["no central advantage"] += 1
            continue
        if fast.partly_estimated or cand.partly_estimated or not (_fully_judged(fast, held_table) and _fully_judged(cand, held_table)):
            dropped["stretch without estimate or held-out flow"] += 1
            continue
        fast_h, cand_h = held_scorer.score(fast.option, "weekday"), held_scorer.score(cand.option, "weekday")
        advantage_held = fast_h.t_adj - cand_h.t_adj
        rows.append({"group": "shown (robust in range)" if picked["calmer"] is not None else
                     "suppressed (central advantage, not robust)",
                     "holds on held-out days": advantage_held >= margin_minutes(fast_h.t_adj, cfg),
                     "calmer still lower": advantage_held > 0})
    summary = _summarise(pd.DataFrame(rows, columns=["group", "holds on held-out days", "calmer still lower"]))
    summary.attrs["dropped"] = dropped
    return summary
