# Architecture

## Problem
Buyers and small investors face large, rarely repeated decisions: which unit, cash vs. installments vs. mortgage, live in it, rent it out or resell, what return to expect and what can go wrong. Brokers cannot spend hours on each lead. The companion does the analysis in a conversation, in English or Egyptian Arabic, and hands the buyers who are ready to a broker with their profile attached.

## Inputs and outputs
- **In:** the buyer conversation (goal, budget, down payment, monthly capacity, horizon, preferred areas), inventory and payment plans, monthly area price indices, rental listings, macro series (CPI, EGP/USD, CBE rates), and company policy documents.
- **Out:** a goal-weighted shortlist, a financing comparison in today's money, P10/P50/P90 value and rent projections with IRR and break-even, a risk summary, cited policy answers, an HTML/PDF report, and a broker lead.

## System

```
React UI (EN/AR, RTL) --SSE--> Litestar API --> ChatService --> AdkEngine (Google ADK LlmAgent)
                                                    |                 |
                                                    |                 +-- LLM: Anthropic -> Gemini chain
                                                    |                     (circuit breaker, timeout, retries)
                                                    |                     or scripted FakeLlm
                                                    v
                                        Toolbox (7 tools) --> CompanionBackend gateway (bootstrap)
                                                                |
        +---------------+---------------+-----------------+----+-----------+-------------+
        v               v               v                 v                v             v
    inventory       financing         market          scenarios        knowledge      handoff / reports
    SQL search      Decimal calcs     ARIMA forecast  Monte Carlo      BM25+vector    leads, HMAC webhook,
    + scoring       PV comparison     LightGBM value  IRR, break-even  RRF, cited     Jinja2 HTML, WeasyPrint PDF
                                      + rent          risk rules
```

**Modular monolith.** Each module under `src/reic/modules/` has `domain / ports / application / adapters`. import-linter enforces 6 contracts: layers point inward, modules don't import each other, and the domain, ports and application layers import no framework or vendor (Litestar, SQLAlchemy, LightGBM, Google, httpx...). Wiring and cross-module gateways live in `src/reic/bootstrap/`.

## Agent design
- **One `LlmAgent` per turn**, built with the current profile in the instruction. The instruction is passed as a callable so profile JSON braces are not read as ADK state templates. Sessions persist across turns in ADK's session service.
- **Tools:** `update_profile`, `search_units`, `compare_financing`, `project_returns`, `search_knowledge`, `create_lead`, `build_report`. A tool failure comes back to the model as `{"error": ...}` instead of ending the turn. At most 12 model calls per turn.
- **Numbers come only from tools.** After each reply, a grounding check compares every figure in the text with the turn's tool outputs, and a note is appended when a figure can't be traced.
- **Clarification policy:** the agent asks for the goal and budget before it searches.
- **Streaming:** text deltas, tool status and typed artifacts (shortlist, financing, projection, risks, citations, handoff, report) go out as SSE events. Gemini's SSE mode repeats each function call in a partial and a final event, so tool status is emitted from the final one only.
- **Providers:** `anthropic` (through LiteLLM, falling back to Gemini), `gemini`, or `fake`. A circuit breaker opens after 3 failures for 60 s. Gemini calls time out at 60 s and retry 429/5xx with backoff.

## Models and methods
- **Area price forecast:** ARIMA(1,1,0) with drift on log prices. Rolling-origin backtest (3 origins x 12 months x 12 areas) scored by MAPE, MASE, 80% coverage and pinball loss against seasonal naive.
- **Unit value:** LightGBM quantile regression (0.1/0.5/0.9) on EGP/m2, with intervals widened by split conformal. A promotion gate serves the area-median baseline unless the model beats it on holdout MAE.
- **Rent:** LightGBM regression on area, type, size, finishing and furnishing.
- **Scenarios:** vectorised NumPy Monte Carlo with log-normal price growth, normal inflation and beta vacancy. Outputs are value, cumulative rent, IRR, break-even and a one-at-a-time sensitivity table. Risk rules (delivery, liquidity, price sensitivity, currency/inflation) in EN and AR.
- **Financing:** pure `Decimal` math for installment schedules, mortgage amortisation, PV/IRR and a three-way comparison in present value. Checked against hand-worked reference values and seeded property tests.
- **Knowledge:** markdown policy documents (10 EN, 6 AR) chunked by heading. Retrieval is BM25 with Arabic-aware normalisation plus vectors (hashing, MiniLM or bge-m3), fused with reciprocal rank fusion. Answers cite their chunks.

## Data
- **Synthetic** (`scripts/generate_synthetic_data.py`, fixed seed, sha256 manifest): 12 real Egyptian districts, 15 fictional developers, 40 projects, 1,500 units, 82 payment plans, 5,000 rental listings, and monthly area indices 2015-2026 with the 2016-2024 devaluation jumps.
- **Public anchors** (`demo_data/public/`, source URL and retrieval time on every row): World Bank CPI and EGP/USD annual series, the current CBE overnight rates, and recent CPI prints. The synthetic monthly macro series is interpolated from them and labelled as such.

## Safety and abuse controls
- Outputs are scenarios with a disclaimer on every report. No figure comes from the model's own arithmetic.
- Per-client rate limit on the public write endpoints (lead creation, chat sessions, chat messages), keyed by the proxy's client-IP header in production.
- The broker queue is guarded by an API key. Lead webhooks are signed with HMAC-SHA256 over `timestamp.body`.

## Evaluation
- **Market:** backtest and holdout metrics written by `scripts/train_market_models.py`.
- **RAG:** a 26-question EN/AR gold set, scored by Recall@4 and MRR for the BM25, vector and hybrid modes (`scripts/eval_rag.py`).
- **Agent:** 10 EN/AR scenarios (full journeys, missing budget, knowledge questions, broker contact), scored on task success, clarification quality, grounding and latency (`scripts/eval_agent.py`).
- **System:** `scripts/smoke_e2e.py` runs the whole buyer journey against a running stack, plus 192 backend and 10 frontend tests in CI.

## Deployment
- **API:** Fly.io (Frankfurt), image `python:3.12-slim` with pango, fonts and libgomp. Runs `alembic upgrade head` on start; machines stop when idle.
- **DB:** Neon Postgres (Frankfurt) with the pgvector extension enabled.
- **UI:** Cloudflare Workers static assets with SPA fallback.

## Trade-offs and what is not built
- The knowledge index and chat sessions are in memory. The corpus is small and the app runs as one machine; pgvector is enabled for when the corpus grows.
- No cross-encoder reranker. Hybrid RRF already reaches Recall@4 = 1.00 on the gold set.
- Observability is OpenTelemetry tracing per request. Token cost and drop-off dashboards are not built.
- The forecast is retrained in memory at startup (about 2 s). A monthly retrain job and drift monitoring are the next step for real data.
