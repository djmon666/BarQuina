#!/usr/bin/env python3
"""Async HTTP load harness that simulates mobile orders from outside the server."""
from __future__ import annotations

import argparse
import asyncio
import statistics
import time
import urllib.parse
import re
from dataclasses import dataclass

import httpx


@dataclass
class ScenarioResult:
    create_order_s: float
    add_items_s: float
    toggle_s: float
    total_s: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Remote load test simulator for BarQuina mobile flow")
    parser.add_argument("base_url", help="Base URL of the running server, e.g. https://quina.local")
    parser.add_argument("user_id", type=int, help="Existing staff user id to impersonate")
    parser.add_argument("table_id", type=int, help="Table id to target")
    parser.add_argument("product_id", type=int, help="Product id to add to orders")
    parser.add_argument("orders", type=int, help="Total orders to simulate")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Maximum number of concurrent virtual devices (default: 5)",
    )
    parser.add_argument(
        "--status-cycles",
        type=int,
        default=3,
        help="How many times to hit the toggle-served endpoint per order (default: 3)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="HTTP timeout in seconds (default: 10)",
    )
    parser.add_argument(
        "--verify-ssl",
        action="store_true",
        help="Enable SSL verification (disabled by default for self-signed certs)",
    )
    return parser.parse_args()


async def bootstrap_client(args: argparse.Namespace) -> httpx.AsyncClient:
    client = httpx.AsyncClient(
        base_url=args.base_url,
        timeout=args.timeout,
        follow_redirects=False,
        verify=args.verify_ssl,
    )
    # Establish session + login mobile user
    await client.get("/mobile/")
    resp = await client.post("/mobile/select-user", data={"user_id": args.user_id})
    if resp.status_code not in {302, 200}:
        raise RuntimeError(f"Login failed with status {resp.status_code}")
    return client


def extract_order_id(location: str) -> int:
    parsed = urllib.parse.urlparse(location)
    qs = urllib.parse.parse_qs(parsed.query)
    if "order_id" not in qs:
        raise RuntimeError(f"Cannot find order_id in redirect {location}")
    return int(qs["order_id"][0])


def extract_toggle_url(html: str) -> str | None:
    match = re.search(r'data-toggle-url="([^"]+)"', html)
    return match.group(1) if match else None


async def run_scenario(client: httpx.AsyncClient, args: argparse.Namespace, sem: asyncio.Semaphore) -> ScenarioResult:
    async with sem:
        scenario_start = time.perf_counter()
        # create order
        t0 = time.perf_counter()
        resp = await client.post(f"/mobile/tables/{args.table_id}/orders")
        if resp.status_code not in {302, 303}:
            raise RuntimeError(f"Order creation failed with status {resp.status_code}")
        create_elapsed = time.perf_counter() - t0
        order_id = extract_order_id(resp.headers.get("location", ""))

        # add item
        payload = {f"quantity_{args.product_id}": "1"}
        t1 = time.perf_counter()
        resp_add = await client.post(f"/mobile/orders/{order_id}/add-items", data=payload)
        if resp_add.status_code not in {302, 303}:
            raise RuntimeError(f"Add-items failed with status {resp_add.status_code}")
        add_elapsed = time.perf_counter() - t1

        # capture toggle endpoint from rendered order page
        toggle_elapsed_total = 0.0
        if args.status_cycles > 0:
            page = await client.get(f"/mobile/tables/{args.table_id}?order_id={order_id}", follow_redirects=True)
            if page.status_code != 200:
                raise RuntimeError(f"Failed to load order page (status {page.status_code})")
            toggle_url = extract_toggle_url(page.text)
            if not toggle_url:
                raise RuntimeError("Could not find data-toggle-url in page; ensure there is at least one item")
            for _ in range(args.status_cycles):
                t2 = time.perf_counter()
                resp_toggle = await client.post(toggle_url)
                if resp_toggle.status_code not in {302, 204}:
                    raise RuntimeError(f"Toggle call failed with status {resp_toggle.status_code}")
                toggle_elapsed_total += time.perf_counter() - t2

        total_elapsed = time.perf_counter() - scenario_start
        return ScenarioResult(create_elapsed, add_elapsed, toggle_elapsed_total, total_elapsed)


def summarize(latencies: list[float]) -> dict[str, float]:
    latencies_sorted = sorted(latencies)
    return {
        "avg": statistics.mean(latencies_sorted),
        "p95": latencies_sorted[int(0.95 * (len(latencies_sorted) - 1))],
        "max": latencies_sorted[-1],
    }


async def main_async(args: argparse.Namespace) -> None:
    sem = asyncio.Semaphore(args.concurrency)
    tasks = []
    for _ in range(args.orders):
        client = await bootstrap_client(args)
        task = asyncio.create_task(run_scenario(client, args, sem))
        task.add_done_callback(lambda t, c=client: asyncio.create_task(c.aclose()))
        tasks.append(task)

    results: list[ScenarioResult] = []
    for task in asyncio.as_completed(tasks):
        results.append(await task)

    create_stats = summarize([r.create_order_s for r in results])
    add_stats = summarize([r.add_items_s for r in results])
    toggle_stats = summarize([r.toggle_s for r in results])
    total_stats = summarize([r.total_s for r in results])

    print("\n=== Stress summary ===")
    print(f"Orders simulated: {len(results)}")
    print(f"Concurrency: {args.concurrency}")
    print(f"Create order   avg={create_stats['avg']:.3f}s  p95={create_stats['p95']:.3f}s  max={create_stats['max']:.3f}s")
    print(f"Add items      avg={add_stats['avg']:.3f}s  p95={add_stats['p95']:.3f}s  max={add_stats['max']:.3f}s")
    print(f"Toggle flow    avg={toggle_stats['avg']:.3f}s  p95={toggle_stats['p95']:.3f}s  max={toggle_stats['max']:.3f}s")
    print(f"Total scenario avg={total_stats['avg']:.3f}s  p95={total_stats['p95']:.3f}s  max={total_stats['max']:.3f}s")


def main() -> None:
    args = parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
