#!/usr/bin/env python3
"""Benchmark a separately managed local llama.cpp semantic endpoint.

The script intentionally does not start a model process or download weights.
Run it with a local llama.cpp server and a JSONL corpus, for example:

    PYTHONPATH=src python scripts/benchmark_semantic_provider.py \
        --endpoint http://127.0.0.1:8080/completion \
        --model-label Qwen3-4B-Q4_K_M \
        --output benchmark-results.json
"""

from __future__ import annotations

import argparse
import json
import resource
import statistics
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

from piper.semantic_analysis import ExternalSemanticAnalyzer, LlamaCppSemanticProvider


def _records(path: Path) -> Iterable[Mapping[str, Any]]:
    with path.open("r", encoding="utf-8") as corpus:
        for line_number, line in enumerate(corpus, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, Mapping):
                raise ValueError(f"corpus line {line_number} must be an object")
            yield value


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * percentile))
    return round(ordered[index], 4)


def run(args: argparse.Namespace) -> Dict[str, Any]:
    provider = LlamaCppSemanticProvider(
        args.endpoint,
        timeout_seconds=args.timeout,
        max_text_length=args.max_text_length,
    )
    analyzer = ExternalSemanticAnalyzer(
        provider,
        timeout_seconds=args.timeout,
        max_text_length=args.max_text_length,
    )
    latencies: list[float] = []
    matches = 0
    completed = 0
    fallbacks = 0
    details = []
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    for record in _records(args.corpus):
        text = str(record.get("text", ""))
        language = str(record.get("language", ""))
        expected = record.get("expected", {})
        started = time.perf_counter()
        result = analyzer.analyze(text, language)
        elapsed_ms = (time.perf_counter() - started) * 1000
        latencies.append(elapsed_ms)
        completed += 1
        if result.source != "external":
            fallbacks += 1
        is_match = (
            isinstance(expected, Mapping)
            and result.source == "external"
            and result.context == expected.get("context")
            and result.intent == expected.get("intent")
            and result.emotion == expected.get("emotion")
        )
        matches += int(is_match)
        details.append(
            {
                "language": language,
                "source": result.source,
                "unavailable": list(result.unavailable),
                "latency_ms": round(elapsed_ms, 4),
                "match": is_match,
            }
        )

    rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        "endpoint": args.endpoint,
        "model_label": args.model_label,
        "records": completed,
        "semantic_accuracy": round(matches / completed, 4) if completed else 0.0,
        "fallback_rate": round(fallbacks / completed, 4) if completed else 0.0,
        "latency_ms": {
            "mean": round(statistics.mean(latencies), 4) if latencies else 0.0,
            "p50": _percentile(latencies, 0.50),
            "p95": _percentile(latencies, 0.95),
        },
        "max_rss_delta": max(0, rss_after - rss_before),
        "details": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", required=True)
    parser.add_argument(
        "--model-label",
        default="",
        help="Optional label for the already-loaded llama.cpp model",
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("tests/fixtures/semantic_pilot.jsonl"),
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--max-text-length", type=int, default=4000)
    args = parser.parse_args()
    result = run(args)
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")


if __name__ == "__main__":
    main()
