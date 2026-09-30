import argparse
import json
import random
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, List, Tuple


def generate_order(order_index: int) -> Dict:
    customer_id = f"cust-{random.randint(1000, 9999)}"
    item_count = random.randint(1, 4)
    items = []
    total = 0.0

    for _ in range(item_count):
        price = round(random.uniform(9.99, 149.99), 2)
        qty = random.randint(1, 3)
        total += price * qty
        items.append({
            "item_id": f"sku-{random.randint(100, 999)}",
            "quantity": qty,
            "unit_price": price,
        })

    return {
        "order_id": f"ord-{order_index}-{int(time.time() * 1000)}",
        "customer_id": customer_id,
        "items": items,
        "total_amount": round(total, 2),
        "currency": "EUR",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def send_request(url: str, payload: Dict, timeout: float = 10.0) -> Tuple[int, float, str]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = response.getcode()
            elapsed_ms = (time.perf_counter() - start) * 1000
            return status, elapsed_ms, "OK"
    except urllib.error.HTTPError as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return exc.code, elapsed_ms, exc.reason
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return 0, elapsed_ms, str(exc)


def run_benchmark(url: str, total_requests: int, concurrency: int) -> None:
    print(f"Target: {url}")
    print(f"Sending {total_requests} requests with concurrency {concurrency}...")

    orders = [generate_order(i) for i in range(total_requests)]
    latencies: List[float] = []
    status_counts: Dict[int, int] = {}

    start_time = time.perf_counter()

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(send_request, url, order) for order in orders]
        completed = 0

        for future in as_completed(futures):
            status, elapsed_ms, _ = future.result()
            latencies.append(elapsed_ms)
            status_counts[status] = status_counts.get(status, 0) + 1
            completed += 1

            if completed % max(1, total_requests // 5) == 0 or completed == total_requests:
                print(f"[{completed}/{total_requests}] completed")

    total_time = time.perf_counter() - start_time
    latencies.sort()

    p50 = latencies[int(len(latencies) * 0.50)]
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]

    print(f"\nDone in {total_time:.2f}s ({total_requests / total_time:.1f} req/s)")
    print(f"Status codes: {dict(status_counts)}")
    print(f"Latency: min={latencies[0]:.1f}ms, p50={p50:.1f}ms, p95={p95:.1f}ms, p99={p99:.1f}ms, max={latencies[-1]:.1f}ms")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send test orders to API Gateway")
    parser.add_argument("--url", required=True, help="POST /orders endpoint")
    parser.add_argument("--total", type=int, default=100, help="Number of requests")
    parser.add_argument("--concurrency", type=int, default=10, help="Concurrent workers")

    args = parser.parse_args()
    run_benchmark(args.url, args.total, args.concurrency)
