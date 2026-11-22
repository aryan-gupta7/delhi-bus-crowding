"""Command line: ``python -m crowd {run,gates,validate,query,serve} [options]``."""

from __future__ import annotations

import argparse
import logging
import sys

from crowd.config import Config
from crowd.pipeline import Context, run, write_manifest
from crowd.store import Store


def _context(args: argparse.Namespace) -> Context:
    cfg = Config.load(args.config)
    return Context(cfg=cfg, store=Store(cfg.path("out")))


def cmd_run(args: argparse.Namespace) -> int:
    from crowd.stages import STAGES
    ctx = _context(args)
    timings = run(STAGES, ctx, force=args.force, only=args.stage)
    manifest = write_manifest(STAGES, ctx, timings, extra={})
    print(f"reproducibility_hash {manifest['reproducibility_hash']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="crowd", description=__doc__)
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    p_run = sub.add_parser("run", help="run the pipeline S0-S8 (skips up-to-date stages)")
    p_run.add_argument("--force", action="store_true", help="re-run every stage")
    p_run.add_argument("--stage", help="run only this stage")
    p_run.set_defaults(func=cmd_run)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
