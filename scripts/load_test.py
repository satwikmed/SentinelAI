#!/usr/bin/env python3
"""Light concurrent load test against a running SentinelAI gateway."""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time

import httpx

QUERIES = [
    "What is the data retention period after contract termination?",
    "How quickly must security incidents be reported to the SOC?",
    "How many PTO days can employees carry over?",
    "When is a DPA required for vendors?",
]


async def one(client: httpx.AsyncClient, q: str) -> tuple[int, float]:
    started = time.perf_counter()
    r = await client.post("/api/chat", json={"query": q}, timeout=120)
    return r.status_code, (time.perf_counter() - started) * 1000


async def run(base: str, concurrency: int, total: int) -> int:
    qs = [QUERIES[i % len(QUERIES)] for i in range(total)]
    latencies: list[float] = []
    codes: list[int] = []
    sem = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(base_url=base.rstrip("/")) as client:
        async def bound(q: str):
            async with sem:
                code, ms = await one(client, q)
                codes.append(code)
                latencies.append(ms)

        await asyncio.gather(*(bound(q) for q in qs))

    ok = sum(1 for c in codes if c == 200)
    print(
        {
            "base": base,
            "total": total,
            "concurrency": concurrency,
            "ok": ok,
            "errors": total - ok,
            "p50_ms": round(statistics.median(latencies), 1) if latencies else None,
            "p95_ms": round(sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)], 1)
            if latencies
            else None,
            "max_ms": round(max(latencies), 1) if latencies else None,
        }
    )
    return 0 if ok == total else 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://127.0.0.1:8000")
    p.add_argument("--concurrency", type=int, default=5)
    p.add_argument("--total", type=int, default=20)
    args = p.parse_args()
    return asyncio.run(run(args.base, args.concurrency, args.total))


if __name__ == "__main__":
    raise SystemExit(main())
