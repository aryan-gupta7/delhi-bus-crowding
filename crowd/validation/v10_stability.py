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
from crowd.planner.scoring import Scorer
from crowd.planner.service import Planner
from crowd.validation.queries import Query
from crowd.validation.v1_holdout import FlowInputs


def _heldout_table(table: CrowdingTable, inp: FlowInputs, cuts: np.ndarray) -> CrowdingTable:
    """The crowding table with every weekday level replaced by the held-out empirical level."""
    geo = inp.geo
    level_grid, _, _, has = inp.levels(inp.target, cuts)                       # [n_stretch, 24]
    stretch_row = {(geo.names[r], int(geo.stretch_id[s])): g
                   for g, (r, s) in enumerate(zip(geo.stretch_route, geo.stretch_starts))}
    cells = table.cells.copy()
    g = np.array([stretch_row[(r, sid)] for r, sid in zip(cells["route"], cells["stretch_id"])])
    hour = cells["hour"].to_numpy(np.int64)
    usable = (cells["day_type"] == "weekday").to_numpy() & has[g, hour] & (cells["tier"] != "No estimate").to_numpy()
    cells["level"] = np.where(usable, level_grid[g, hour], cells["level"]).astype(np.int8)
    levels = np.repeat(cells["level"].to_numpy()[:, None].astype(np.uint8), table.levels.shape[1], axis=1)
    return CrowdingTable.load(cells, levels)


def run_v10(ctx: Context, planner: Planner, est_train, inp: FlowInputs, train: np.ndarray, queries: list[Query]) -> pd.DataFrame:
    """Held-out holding rate of calmer-option advantages, by whether the robust rule showed them."""
    st, cfg, geo = ctx.store, ctx.cfg, stages.geometry(ctx)
    dense = {"weekday": supply_mod.dense_supply(st.read_table("supply.parquet"), geo)["weekday"]}   # training days are weekdays
    counts = st.read_table("counts.parquet")
    z = {"weekday": hour_profile_z(counts[counts["date"].isin(train)], "weekday")}
    result = run_ensemble(est_train, dense, st.read_table("route_seats.parquet"), stages.route_coverage_array(ctx),
                          st.read_table("route_info.parquet"), z, cfg)
    cuts = {k: {"central": v["central"]} for k, v in result.cuts.items()}
    train_planner = planner.rebind(CrowdingTable.load(result.cells, result.levels), cuts, cfg)
    held_scorer = Scorer(_heldout_table(train_planner.table, inp, np.asarray(cuts["weekday"]["central"])), geo, cuts, cfg)

    rows = []
    for q in queries:
        options = train_planner.options(q.from_stop, q.to_stop, q.time)
        if len(options) < 2:
            continue
        scored = [train_planner.scorer.score(o, "weekday") for o in options]
        picked = pick_cards(scored, train_planner.scorer, "weekday", cfg)
        cand = picked["candidate"]
        if cand is None or picked["advantage"] < margin_minutes(picked["fastest"].t_adj, cfg):
            continue                                     # no central advantage: nothing to check
        fast_h, cand_h = held_scorer.score(picked["fastest"].option, "weekday"), held_scorer.score(cand.option, "weekday")
        advantage_held = fast_h.t_adj - cand_h.t_adj
        rows.append({"group": "shown (robust in range)" if picked["calmer"] is not None else
                     "suppressed (central advantage, not robust)",
                     "holds on held-out days": advantage_held >= margin_minutes(fast_h.t_adj, cfg),
                     "calmer still lower": advantage_held > 0})
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["group", "queries", "advantage still lower", "advantage still >= margin"])
    return df.groupby("group").agg(**{"queries": ("calmer still lower", "size"),
                                      "calmer still lower on held-out days": ("calmer still lower", "mean"),
                                      "advantage still >= margin on held-out days": ("holds on held-out days", "mean")}).reset_index()
