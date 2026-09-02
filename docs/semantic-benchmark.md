# Semantic provider benchmark

The repository contains a reproducible pilot corpus at
`tests/fixtures/semantic_pilot.jsonl` and a runner at
`scripts/benchmark_semantic_provider.py`. The runner measures semantic label
accuracy, latency, fallback rate, and process RSS growth for a separately
managed local `llama.cpp` endpoint. It never starts a model process and never
downloads model weights.

## Current status

The benchmark is not executed in this workspace because no `llama-server`
binary, local GGUF model, or running endpoint is available. Therefore no model
is selected as the default recommendation yet. The provider remains opt-in and
the existing deterministic analyzer remains the rollback path.

## Run procedure

Start a local `llama.cpp` server with a multilingual instruct GGUF model, then
run:

```text
PYTHONPATH=src python scripts/benchmark_semantic_provider.py \
  --endpoint http://127.0.0.1:8080/completion \
  --model-label <model-id> \
  --output benchmark-results.json
```

Compare at least one candidate on the same corpus. Record the candidate,
quantization, hardware, accuracy, p50/p95 latency, maximum RSS delta, and
fallback rate before enabling it in a deployment configuration.
