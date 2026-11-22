"""Command line: ``python -m crowd {run,gates,validate,query,serve} [options]``."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from crowd.config import Config
from crowd.pipeline import Context, run, write_manifest
from crowd.store import Store


def _context(args: argparse.Namespace) -> Context:
    cfg = Config.load(args.config)
    return Context(cfg=cfg, store=Store(cfg.path("out")))


def cmd_run(args: argparse.Namespace) -> int:
    from crowd.stages import STAGES
    ctx = _context(args)
    if args.frozen_cuts:                           # score against the band cuts of a reference run
        ctx.frozen_cuts = Store(Path(args.frozen_cuts).parent).read_json(Path(args.frozen_cuts).name)["cuts"]
    timings = run(STAGES, ctx, force=args.force, only=args.stage)
    manifest = write_manifest(STAGES, ctx, timings, extra=_manifest_extra(ctx, args.frozen_cuts))
    print(f"reproducibility_hash {manifest['reproducibility_hash']}")
    return 0


def _manifest_extra(ctx: Context, frozen_cuts: str | None) -> dict:
    """What a reader of run_manifest.json needs without opening other files (all deterministic)."""
    st = ctx.store
    optional = lambda name: st.read_json(name) if st.exists(name) else None          # noqa: E731
    cuts = optional("cuts.json")
    return {"frozen_cuts_from": frozen_cuts, "ingest": optional("ingest_report.json"),
            "band_cuts_central": cuts and {k: v["central"] for k, v in cuts["cuts"].items()},
            "scenario": cuts and cuts["scenario"], "estimator": optional("estimator_fit.json"), "gates": optional("gates.json")}


def cmd_gates(args: argparse.Namespace) -> int:
    from crowd.stages import STAGES
    ctx = _context(args)
    run([s for s in STAGES if s.name == "gates"] or [], ctx, force=True)
    results = ctx.store.read_json("gates.json")
    failed = [g for g in results if g["passed"] is False and g["blocking"]]
    for g in results:
        mark = {True: "PASS", False: "FAIL", None: "info"}[g["passed"]]
        print(f"{g['id']:<4}{mark:<5}{g['name']}: {g['value']}  {g['note']}")
    return 1 if failed else 0


def cmd_validate(args: argparse.Namespace) -> int:
    from crowd.validation.report import ITEMS, run_all
    only = tuple(args.only.split(",")) if args.only else ITEMS
    path = run_all(_context(args), only)
    print(f"validation report: {path}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn
    from crowd.api.app import create_app
    uvicorn.run(create_app(_context(args)), host=args.host, port=args.port)
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    from crowd import stages
    from crowd.outputs import CrowdingTable, StopResolver, query
    ctx = _context(args)
    table = CrowdingTable.load(ctx.store.read_table("crowding_cells.parquet"), ctx.store.read_array("levels.npy"))
    geo = stages.geometry(ctx)
    result = query(table, geo, StopResolver(geo, ctx.cfg), args.route, args.from_stop, args.to_stop, args.time, args.day)
    print(json.dumps(result, indent=2))
    return 0 if "error" not in result else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="crowd", description=__doc__)
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    p_run = sub.add_parser("run", help="run the pipeline S0-S8 (skips up-to-date stages)")
    p_run.add_argument("--force", action="store_true", help="re-run every stage")
    p_run.add_argument("--stage", help="run only this stage")
    p_run.add_argument("--frozen-cuts", help="path to a reference run's cuts.json: score against its band cuts instead of recomputing them")
    p_run.set_defaults(func=cmd_run)
    p_val = sub.add_parser("validate", help="held-out validation (V1 ...) -> out/validation/report.md")
    p_val.add_argument("--only", help="comma-separated subset of v1,v7,v8,v9,v10,v11,v3 (default: all)")
    p_val.set_defaults(func=cmd_validate)
    p_serve = sub.add_parser("serve", help="planner API and web page")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.set_defaults(func=cmd_serve)
    p_query = sub.add_parser("query", help="crowding along one bus ride")
    p_query.add_argument("--route", required=True)
    p_query.add_argument("--from", dest="from_stop", required=True)
    p_query.add_argument("--to", dest="to_stop", required=True)
    p_query.add_argument("--time", default="09:00")
    p_query.add_argument("--day", default="weekday", choices=["weekday", "weekend"])
    p_query.set_defaults(func=cmd_query)
    p_gates = sub.add_parser("gates", help="run gates G1-G7 and print the table (non-zero exit on blocking failure)")
    p_gates.set_defaults(func=cmd_gates)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
