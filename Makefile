# One command per concern. Requires uv (https://docs.astral.sh/uv/).
.PHONY: setup all gates validate test test-data serve clean

setup:            ## create the pinned Python 3.12 environment
	uv sync

all:              ## run the pipeline S0-S8 (skips up-to-date stages); writes out/run_manifest.json
	uv run python -m crowd run

gates:            ## gates G1-G7 (non-zero exit on a blocking failure)
	uv run python -m crowd gates

validate:         ## held-out validation -> out/validation/report.md
	uv run python -m crowd validate

test:             ## unit + mini end-to-end tests (fast)
	uv run pytest -q

test-data:        ## checks against the real October files (needs `make all` first)
	uv run pytest -m data -q

serve:            ## planner API and web page on http://127.0.0.1:8000
	uv run python -m crowd serve

clean:            ## remove generated artefacts (never touches data/)
	rm -rf out
