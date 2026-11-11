"""Agent evaluation against a running API (start it with scripts/dev_stack.py).

Runs buyer scenarios (EN + AR) and scores three things per scenario:
  task success   expected tools were called and expected artifacts were produced
  clarification  when the budget is missing the agent asks instead of searching
  grounding      the reply carries no "could not be traced" note

Usage: python scripts/eval_agent.py [--api http://localhost:8000] [--provider fake]
Writes evals/results/agent_eval_<provider>.json and prints a table.
"""

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
import smoke_e2e  # noqa: E402
from smoke_e2e import chat  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
UNTRACED_MARKERS = ("could not be traced", "لا يمكن تتبع", "تعذر تتبع")


@dataclass
class Scenario:
    name: str
    language: str
    messages: list[str]
    tools: list[str] = field(default_factory=list)  # expected, across all turns
    artifacts: list[str] = field(default_factory=list)  # expected, across all turns
    must_clarify: bool = False  # first turn: no search, a question back
    forbidden_tools: list[str] = field(default_factory=list)


SCENARIOS = [
    Scenario(
        "rent_en",
        "en",
        ["I have 5M EGP and want to rent it out in New Cairo for 5 years"],
        tools=["search_units", "compare_financing", "project_returns"],
        artifacts=["shortlist", "financing", "projection", "risks"],
    ),
    Scenario(
        "resell_en",
        "en",
        ["I have 6M EGP and want to resell in 3 years"],
        tools=["search_units", "project_returns"],
        artifacts=["shortlist", "projection"],
    ),
    Scenario(
        "live_en",
        "en",
        ["I have 4M EGP and want a home to live in, 5 years horizon"],
        tools=["search_units"],
        artifacts=["shortlist"],
    ),
    Scenario(
        "rent_ar",
        "ar",
        ["معايا ٤ مليون وعايز أشتري للإيجار في مدينتي لمدة ٥ سنوات"],
        tools=["search_units"],
        artifacts=["shortlist"],
    ),
    Scenario(
        "resell_ar",
        "ar",
        ["معايا 6 مليون جنيه وعايز أشتري وأبيع بعد 3 سنين"],
        tools=["search_units"],
        artifacts=["shortlist"],
    ),
    Scenario(
        "missing_budget_en",
        "en",
        ["I want to buy a home to live in New Cairo"],
        must_clarify=True,
        forbidden_tools=["search_units"],
    ),
    Scenario(
        "missing_budget_ar",
        "ar",
        ["عايز أشتري شقة للاستثمار"],
        must_clarify=True,
        forbidden_tools=["search_units"],
    ),
    Scenario(
        "knowledge_en",
        "en",
        ["What is the cancellation and refund policy?"],
        tools=["search_knowledge"],
        artifacts=["citations"],
    ),
    Scenario(
        "knowledge_ar",
        "ar",
        ["ايه سياسة الإلغاء والاسترداد؟"],
        tools=["search_knowledge"],
        artifacts=["citations"],
    ),
    Scenario(
        "broker_contact_en",
        "en",
        ["I want to talk to a broker", "Contact me on 01012345678"],
        tools=["create_lead"],
        artifacts=["handoff"],
    ),
]


def run(client: httpx.Client, sc: Scenario) -> dict[str, Any]:
    sid = client.post("/chat/sessions", json={"language": sc.language}).json()["session_id"]
    turns = [chat(client, sid, m, sc.language) for m in sc.messages]
    tools = [t for turn in turns for t in turn["tools"]]
    artifacts = {k for turn in turns for k in turn["artifacts"]}
    text = "\n".join(turn["text"] for turn in turns)
    first = turns[0]
    clean = all(t["done"] and not t["errors"] for t in turns)

    success = (
        clean
        and all(t in tools for t in sc.tools)
        and all(a in artifacts for a in sc.artifacts)
        and not any(t in tools for t in sc.forbidden_tools)
    )
    result: dict[str, Any] = {
        "scenario": sc.name,
        "language": sc.language,
        "task_success": success,
        "grounded": not any(m in text for m in UNTRACED_MARKERS),
        "tools": tools,
        "artifacts": sorted(artifacts),
        "seconds": round(sum(t["seconds"] for t in turns), 2),
    }
    if sc.must_clarify:
        questioned = "?" in first["text"] or "؟" in first["text"]
        asked = questioned and "search_units" not in first["tools"]
        result["clarified"] = asked and not first["artifacts"].get("shortlist")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--provider", default="fake", help="label of the provider the API runs")
    parser.add_argument("--pause", type=float, default=0.0, help="seconds before each chat turn")
    args = parser.parse_args()
    smoke_e2e.PAUSE = args.pause
    client = httpx.Client(base_url=args.api, timeout=180)

    results = [run(client, sc) for sc in SCENARIOS]
    clarify = [r for r in results if "clarified" in r]
    summary = {
        "provider": args.provider,
        "scenarios": len(results),
        "task_success": round(sum(r["task_success"] for r in results) / len(results), 3),
        "clarification_quality": round(sum(r["clarified"] for r in clarify) / len(clarify), 3),
        "grounding": round(sum(r["grounded"] for r in results) / len(results), 3),
        "mean_seconds": round(sum(r["seconds"] for r in results) / len(results), 2),
    }
    out = ROOT / "evals" / "results" / f"agent_eval_{args.provider}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"{'scenario':<20}{'lang':<6}{'success':<9}{'clarified':<11}{'grounded':<10}{'sec':>6}")
    for r in results:
        clar = {True: "yes", False: "no"}.get(r.get("clarified"), "-")
        print(
            f"{r['scenario']:<20}{r['language']:<6}{'pass' if r['task_success'] else 'FAIL':<9}"
            f"{clar:<11}{'yes' if r['grounded'] else 'no':<10}{r['seconds']:>6}"
        )
    print(json.dumps(summary, indent=2))
    print(f"written {out}")


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPError as exc:
        print(f"HTTP failure: {exc}")
        sys.exit(1)
