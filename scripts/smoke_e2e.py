"""End-to-end smoke test against a running API (start it with scripts/dev_stack.py).

Walks the buyer journey: health -> session -> profile + shortlist + financing + returns ->
knowledge question -> report -> broker handoff -> broker queue. Exits non-zero on failure.

Usage: python scripts/smoke_e2e.py [--api http://localhost:8000] [--broker-key dev-broker-key]
"""

import argparse
import json
import sys
import time
from typing import Any

import httpx

# Seconds to wait before each chat turn; free-tier LLM keys allow only a few requests per minute.
PAUSE = 0.0


def chat(client: httpx.Client, sid: str, message: str, language: str = "en") -> dict[str, Any]:
    time.sleep(PAUSE)
    events: list[tuple[str, dict[str, Any]]] = []
    started = time.perf_counter()
    with client.stream(
        "POST", f"/chat/sessions/{sid}/messages", json={"message": message, "language": language}
    ) as response:
        response.raise_for_status()
        kind = "message"
        for line in response.iter_lines():
            if line.startswith("event:"):
                kind = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                events.append((kind, json.loads(line.split(":", 1)[1])))
    text = "".join(d["text"] for k, d in events if k == "delta")
    return {
        "text": text,
        "tools": [d["name"] for k, d in events if k == "tool" and d["status"] == "started"],
        "artifacts": {d["kind"]: d["data"] for k, d in events if k == "artifact"},
        "errors": [d for k, d in events if k == "error"],
        "done": any(k == "done" for k, _ in events),
        "seconds": round(time.perf_counter() - started, 2),
    }


def check(condition: bool, label: str) -> None:
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}")
    if not condition:
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--broker-key", default="dev-broker-key")
    parser.add_argument("--pause", type=float, default=0.0, help="seconds before each chat turn")
    args = parser.parse_args()
    global PAUSE
    PAUSE = args.pause
    client = httpx.Client(base_url=args.api, timeout=180)

    print("1. health")
    check(client.get("/health").json()["status"] == "ok", "API healthy")

    print("2. buyer journey (en)")
    sid = client.post("/chat/sessions", json={"language": "en"}).json()["session_id"]
    turn = chat(client, sid, "I have 5M EGP and want to rent it out in New Cairo for 5 years")
    print(f"     tools={turn['tools']} {turn['seconds']}s")
    check(turn["done"] and not turn["errors"], "turn completed without errors")
    for kind in ("shortlist", "financing", "projection", "risks"):
        check(kind in turn["artifacts"], f"{kind} artifact")
    units = turn["artifacts"]["shortlist"]["units"]
    check(all(u["price_egp"] <= 5_000_000 for u in units), "shortlist within budget")
    value = turn["artifacts"]["projection"]["value"]
    check(value["p10"] <= value["p50"] <= value["p90"], "P10 <= P50 <= P90")
    check(len(turn["text"]) > 40, "assistant explained the result")

    print("3. knowledge question")
    turn = chat(client, sid, "What is the cancellation and refund policy?")
    check("citations" in turn["artifacts"], "answer carries citations")

    print("4. report")
    turn = chat(client, sid, "Please build the report")
    report = turn["artifacts"].get("report")
    check(report is not None, "report artifact")
    html = client.get(report["url_html"]).text
    check("<svg" in html and "SYNTHETIC" in html.upper(), "HTML report has charts and disclaimer")

    print("5. broker handoff")
    chat(client, sid, "I want to talk to a broker")
    turn = chat(client, sid, "Contact me on 01012345678")
    lead = turn["artifacts"].get("handoff")
    check(lead is not None, "lead created")
    queue = client.get("/broker/leads", headers={"X-API-Key": args.broker_key})
    check(queue.status_code == 200, "broker queue reachable with key")
    body = queue.json()
    items = body if isinstance(body, list) else body.get("items", [])
    check(any(i.get("id") == lead["lead_id"] for i in items), "lead visible to broker")
    check(client.get("/broker/leads").status_code == 401, "broker queue rejects missing key")

    print("6. Arabic session")
    sid_ar = client.post("/chat/sessions", json={"language": "ar"}).json()["session_id"]
    turn = chat(client, sid_ar, "معايا ٤ مليون وعايز أشتري للإيجار في مدينتي لمدة ٥ سنوات", "ar")
    check(turn["done"] and not turn["errors"], "Arabic turn completed")
    print("\nE2E smoke: all checks passed")


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPError as exc:
        print(f"HTTP failure: {exc}")
        sys.exit(1)
