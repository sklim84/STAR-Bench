# Rerun quickstart (co-author hosts)

Frozen point: tag `rerun-freeze-20260916` on branch `audit-fixes` in both repositories.
Everything below runs from the STAR-Bench checkout, with STAR-Bench-Web checked out next to it.

## 1. Environments (once)
```bash
python -m venv .venv-eval && . .venv-eval/bin/activate
pip install -r _experiments/env/requirements-eval.txt
pip install -r ../STAR-Bench-Web/requirements-tools.txt
python -m _experiments.env.check_env          # must report no conflict
```
The serving stack (vLLM, torch) installs separately from `_experiments/env/requirements-serving.txt`;
never in the same virtual environment. Container recipes are in the same directory.

## 2. Models (once per configuration)
Download the models this host serves, then write each snapshot commit into
`_experiments/scripts/model_revisions.json`. A configuration without a revision refuses to serve.
```bash
python -m _experiments.scripts.runner.plan --host-gpus 2        # what this host can serve
huggingface-cli download <model> --revision <commit>
```

## 3. Pre-flight (before every run session)
```bash
python -m _experiments.scripts.preflight.run --all --report --configs <your config ids>
```
Gates 2 to 5 must pass. Gate 1 fails only while a model revision is still empty.

## 4. Smoke test (per configuration, 5 to 10 minutes)
```bash
bash _experiments/scripts/run_benchmark.sh --config <id> --gpu 0,1 \
     --mode single --tools-lang kr --limit 40 --out-root _experiments/results_smoke_2026
python -m _experiments.scripts.preflight.run canary --config <id> --base-url http://127.0.0.1:11434/v1
```
Stop and report if the canary trips: no-tool-call rate, system errors, `finish_reason: length`,
fallback-parser share, empty tool results, prompt headroom.

## 5. Main run
```bash
bash _experiments/scripts/run_master.sh --host-gpus 2 --host-profile 48g \
     --columns single,oracle,e2e --tools-lang kr --query-lang kr \
     --only <your config ids> --out-root _experiments/results_2026rerun
```
Fresh output directory, concurrency 8, temperature 0, seed 20260925. Interrupted runs continue with
`--resume` in the same directory; a short run fails the record count check instead of passing silently.

## 6. The three extra 2×2 arms (only for the configurations marked 2×2)
```bash
for arm in "kr en" "en kr" "en en"; do set -- $arm
  bash _experiments/scripts/run_master.sh --host-gpus 2 --columns single \
       --tools-lang $1 --query-lang $2 --only <config> --out-root _experiments/results_2026rerun
done
```

## 7. Send back
The whole output directory (`<run_id>.jsonl` + `<run_id>.manifest.json`), the server logs for those runs,
and the canary output. No scoring on your side: scoring happens once, centrally, from the records.
