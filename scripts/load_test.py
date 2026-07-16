"""Generate concurrent mixed traffic and summarize gateway outcomes.

Each requested TPS value creates that many workers, and every worker sends one
request per second.  Alpha Bank therefore produces an eight-request burst each
second against its seeded five-TPS limit, making VP4029 responses reproducible.
"""
from __future__ import annotations

import json
import random
import threading
import time
import urllib.error
import urllib.request

BASE_URL = "http://localhost:5000/api/v1/verify"
DURATION_SECONDS = 60
CLIENTS = [
    ("alphabank", "alpha-key", "al_ops_01", "103.24.10.5", 8),
    ("zetafin", "zeta-key", "ze_ops_01", "103.24.10.6", 3),
    ("novahr", "nova-key", "no_ops_01", "198.51.100.9", 4),
]


def empty_summary() -> dict[str, int]:
    return {
        "sent": 0,
        "succeeded": 0,
        "rate_limited": 0,
        "blocked": 0,
        "failed": 0,
    }


def classify_status(summary: dict[str, int], status_code: int) -> None:
    """Update one client's counters from the HTTP outcome."""
    summary["sent"] += 1
    if status_code == 200:
        summary["succeeded"] += 1
    elif status_code == 429:
        summary["rate_limited"] += 1
    elif status_code == 403:
        summary["blocked"] += 1
    else:
        summary["failed"] += 1


def _send_once(client) -> int:
    client_id, api_key, user_id, client_ip, _ = client
    payload = json.dumps(
        {
            "client_ref_id": f"{client_id}-{random.randint(1000, 9999)}",
            "id_type": "PAN",
            "id_number": "ABCDE1234F",
            "name": "Rahul Sharma",
        }
    ).encode("utf-8")
    outbound_request = urllib.request.Request(
        BASE_URL,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key,
            "X-User-Id": user_id,
            "X-Forwarded-For": client_ip,
        },
    )
    try:
        with urllib.request.urlopen(outbound_request, timeout=5) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except Exception:
        return 0


def _worker(client, results: dict, lock: threading.Lock, start_at: float) -> None:
    """Send one request per second until the shared test window closes."""
    client_id = client[0]
    deadline = start_at + DURATION_SECONDS
    next_send = start_at

    while next_send < deadline:
        delay = next_send - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        status_code = _send_once(client)
        with lock:
            classify_status(results[client_id], status_code)
        next_send += 1.0


def main() -> None:
    results = {client[0]: empty_summary() for client in CLIENTS}
    lock = threading.Lock()
    start_at = time.monotonic() + 0.5
    threads: list[threading.Thread] = []

    # One worker represents one request per second.  Creating eight workers for
    # Alpha Bank forms an eight-request burst against its five-TPS allowance.
    for client in CLIENTS:
        requests_per_second = client[4]
        for _ in range(requests_per_second):
            threads.append(
                threading.Thread(
                    target=_worker,
                    args=(client, results, lock, start_at),
                    daemon=True,
                )
            )

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
