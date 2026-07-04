"""Measure sync and ASGI DRF API Logger overhead with Django test clients.

This script is intended for application-level smoke benchmarks. It does not
start a server; it imports the target Django settings module and exercises the
configured middleware stack through Django's sync Client and AsyncClient.
"""

import argparse
import asyncio
import json
import os
import sys
import time
from collections import Counter


def percentile(values, percent):
    if not values:
        return 0.0
    ordered = sorted(values)
    index = round((len(ordered) - 1) * percent)
    return ordered[index]


def summarize(label, durations, statuses):
    return {
        "label": label,
        "requests": len(durations),
        "status_counts": dict(sorted(Counter(statuses).items())),
        "avg_ms": round((sum(durations) / len(durations)) * 1000, 3) if durations else 0.0,
        "p95_ms": round(percentile(durations, 0.95) * 1000, 3),
        "p99_ms": round(percentile(durations, 0.99) * 1000, 3),
    }


def request_sync(client, method, path, body, content_type):
    if method == "GET":
        return client.get(path)
    return client.post(path, data=body, content_type=content_type)


async def request_async(client, method, path, body, content_type):
    if method == "GET":
        return await client.get(path)
    return await client.post(path, data=body, content_type=content_type)


def run_sync_case(label, method, path, requests, body, content_type, signal_enabled):
    from django.test import Client, override_settings
    from drf_api_logger import API_LOGGER_SIGNAL

    durations = []
    statuses = []

    def listener(**kwargs):
        return None

    API_LOGGER_SIGNAL.listen += listener
    try:
        with override_settings(
            DRF_API_LOGGER_DATABASE=False,
            DRF_API_LOGGER_SIGNAL=signal_enabled,
        ):
            client = Client()
            for _ in range(requests):
                started = time.perf_counter()
                response = request_sync(client, method, path, body, content_type)
                durations.append(time.perf_counter() - started)
                statuses.append(response.status_code)
    finally:
        API_LOGGER_SIGNAL.listen -= listener

    return summarize(label, durations, statuses)


async def run_async_case(label, method, path, requests, concurrency, body, content_type, signal_enabled):
    from django.test import AsyncClient, override_settings
    from drf_api_logger import API_LOGGER_SIGNAL

    durations = []
    statuses = []
    lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(concurrency)

    def listener(**kwargs):
        return None

    async def one_request(client):
        async with semaphore:
            started = time.perf_counter()
            response = await request_async(client, method, path, body, content_type)
            duration = time.perf_counter() - started
            async with lock:
                durations.append(duration)
                statuses.append(response.status_code)

    API_LOGGER_SIGNAL.listen += listener
    try:
        with override_settings(
            DRF_API_LOGGER_DATABASE=False,
            DRF_API_LOGGER_SIGNAL=signal_enabled,
        ):
            client = AsyncClient()
            await asyncio.gather(*(one_request(client) for _ in range(requests)))
    finally:
        API_LOGGER_SIGNAL.listen -= listener

    return summarize(label, durations, statuses)


def add_overhead(results):
    by_label = {item["label"]: item for item in results}
    sync_signal = by_label["sync_signal"]["avg_ms"]
    asgi_signal = by_label["asgi_signal"]["avg_ms"]
    sync_baseline = by_label["sync_baseline"]["avg_ms"]
    asgi_baseline = by_label["asgi_baseline"]["avg_ms"]
    return {
        "sync_signal_over_sync_baseline_avg_ms": round(sync_signal - sync_baseline, 3),
        "asgi_signal_over_asgi_baseline_avg_ms": round(asgi_signal - asgi_baseline, 3),
        "asgi_signal_over_sync_signal_avg_ms": round(asgi_signal - sync_signal, 3),
    }


def parse_args():
    parser = argparse.ArgumentParser(
        description="Measure DRF API Logger sync and ASGI overhead with Django test clients."
    )
    parser.add_argument("--settings", help="Django settings module, for example config.settings.")
    parser.add_argument("--path", default="/api/echo/", help="Endpoint path to exercise.")
    parser.add_argument("--method", choices=["GET", "POST"], default="POST")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument(
        "--body",
        default=json.dumps({"safe": "visible", "password": "example-secret"}),
        help="POST body. Keep this synthetic; do not benchmark with real secrets.",
    )
    parser.add_argument("--content-type", default="application/json")
    return parser.parse_args()


def main():
    args = parse_args()
    sys.path.insert(0, os.getcwd())
    if args.settings:
        os.environ["DJANGO_SETTINGS_MODULE"] = args.settings
    if not os.environ.get("DJANGO_SETTINGS_MODULE"):
        raise SystemExit("Set DJANGO_SETTINGS_MODULE or pass --settings.")

    import django

    django.setup()

    results = [
        run_sync_case(
            "sync_baseline",
            args.method,
            args.path,
            args.requests,
            args.body,
            args.content_type,
            signal_enabled=False,
        ),
        run_sync_case(
            "sync_signal",
            args.method,
            args.path,
            args.requests,
            args.body,
            args.content_type,
            signal_enabled=True,
        ),
        asyncio.run(
            run_async_case(
                "asgi_baseline",
                args.method,
                args.path,
                args.requests,
                args.concurrency,
                args.body,
                args.content_type,
                signal_enabled=False,
            )
        ),
        asyncio.run(
            run_async_case(
                "asgi_signal",
                args.method,
                args.path,
                args.requests,
                args.concurrency,
                args.body,
                args.content_type,
                signal_enabled=True,
            )
        ),
    ]

    print(json.dumps({"results": results, "overhead": add_overhead(results)}, indent=2))


if __name__ == "__main__":
    main()
