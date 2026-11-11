# Build Plan — Real Estate Investment Companion

Source: crew-planner output, 2026-11-09. Spec: `architecture.md`. Conventions from `../ai-os-crm-copilot`.

## Locked decisions
- Python 3.12 (pgserver Windows wheels stop at cp312). uv.
- numpy-financial `>=1.0,<1.1` (1.1.0 needs Python 3.13).
- Package `reic` under `src/reic/`. Modular monolith, hexagonal modules, import-linter.
- LLM: Anthropic (via ADK `LiteLlm`) primary, Gemini native fallback, `fake` scripted `BaseLlm` for tests. `LLM_PROVIDER=anthropic|gemini|fake`. `GEMINI_API_KEY` is set system-wide on this machine: tests must default to fake and `monkeypatch.delenv` where "no key" matters.
- Agent: Google ADK (`LlmAgent`, `InMemoryRunner`/`Runner.run_async`). Own provider fallback + circuit breaker (pattern from user's Complaint-Triage repo).
- API: Litestar 2.x + Pydantic. DB: Postgres 16 + pgvector (pgserver locally/tests, Neon prod). SQLAlchemy 2.0 + Alembic.
- Frontend: Vite + React + TypeScript, i18next (en, ar-EG), RTL, Plotly.js.
- Observability: OpenTelemetry only.
- Reports: Jinja2 + WeasyPrint (lazy, null renderer when GTK missing), inline SVG charts.
- Embeddings: hashing embedder (tests/CI), small multilingual MiniLM default, bge-m3 for local eval only.
- Prophet optional (`forecast` extra); statsmodels default forecaster.
- Docker: Dockerfile written, never built locally. Fly.io remote builder. Cloudflare Pages for UI.
- Full build, then deploy. Public repo `Real-Estate-Investment-Companion-using-Google-ADK-Litestar-LightGBM-React`, created at the end. Commits authored by Mrwan Awad only, no Claude lines.
- Eval numbers only from real runs. Synthetic data clearly labelled.

## Modules (`src/reic/modules/<name>/{domain,ports,application,adapters/{inbound,outbound}}`)
| Module | Responsibility |
|---|---|
| inventory | Projects, developers, units, payment plans; search; shortlist scoring |
| financing | Pure Decimal calculators: installments, mortgage, PV/NPV/IRR, comparison |
| market | Market data store; area index forecast; quantile LightGBM unit value; LightGBM rental yield |
| scenarios | NumPy Monte Carlo, break-even, sensitivity, rule-based risk summary |
| knowledge | RAG EN+AR: chunking, BM25 + pgvector, RRF, reranker, citations |
| handoff | Leads table, broker queue, HMAC webhook |
| reports | Jinja2 HTML EN/AR RTL, PDF via WeasyPrint when available |
| companion | ADK agent, buyer profile, clarification policy, grounding check, composer, sessions |
| shared | config, llm factory/fallback/fake, observability, i18n, db, numbers |
| bootstrap | Litestar app, DI, gateway adapters wrapping modules, demo data |

## Steps
1. Scaffold: pyproject (extras agents/ml/forecast/retrieval/reports/observability/gemini/eval), ruff, import-linter, skeleton, config, Litestar `/health`, pgserver fixture, Alembic baseline, `.env.example`, CI, CHECKPOINT, frontend scaffold. Review.
2. Synthetic data generator (12 areas, ~15 developers, ~40 projects, ~1500 units, payment plans, monthly area indices 2015-2026 with devaluation regimes, ~5000 rentals) + public indices CSV (CBE rates, CPI, EGP/USD with source/retrieved_at) + inventory module + search API + seed script.
3. Financing calculators, 100% coverage on `financing/domain`, reference-value tests. Review.
4. Market data store + forecast (seasonal-naive, statsmodels, Prophet optional), metrics (MAPE/MASE/coverage/pinball), rolling-origin backtest recorded.
5. Unit value (LightGBM quantile 0.1/0.5/0.9) + rental yield (LightGBM) training scripts, promotion gate vs baseline, adapters, API. Review (4+5).
6. Scenario simulator + risk summary.
7. Knowledge RAG: synthetic EN/AR docs corpus, hybrid retrieval, gold set + retrieval eval.
8. Companion agent (ADK), LLM factory + fallback + fake, profile, clarification, grounding, tools, SSE chat API, sessions. Review.
9. Handoff (leads, webhook, broker API key) + reports (HTML/PDF EN/AR).
10. Frontend: chat (SSE, charts, citations, report download, RTL) + broker page. Review.
11. Observability (OTel spans/metrics) + evals (agent scenarios, RAG eval) with real Gemini runs recorded.
12. dev_stack.py, smoke_e2e.py, Dockerfile, fly.toml, README, CHECKPOINT. Final review.
13. Publish + deploy (needs user accounts/keys).
