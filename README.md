# Real Estate Investment Companion

> **All inventory, market data and documents in this repo are synthetic.** Nothing here is real pricing, a real listing, or investment advice.

An AI companion for real estate buyers and small investors. It profiles the buyer's goal (live, rent out, resell), budget and horizon, shortlists units, compares cash, installments and mortgage with deterministic calculators, projects resale value and rental yield as P10/P50/P90 ranges, explains risks in Arabic or English with cited sources, builds a shareable report, and hands qualified buyers to a broker.

## Architecture

Python 3.12, Litestar API, PostgreSQL with pgvector, React/Vite frontend. One module per capability under `src/reic/modules/`, wired in `src/reic/bootstrap/`; import-linter enforces the module boundaries.

Modules: `inventory` (unit search and shortlist), `financing` (installments, mortgage, comparison), `market` (area forecast, LightGBM unit value and rent), `scenarios` (Monte Carlo projection and risk summary), `knowledge` (BM25 + vector hybrid RAG over policy documents), `handoff` (broker leads, signed webhook), `reports` (HTML/PDF), `companion` (chat agent).

Agent: a Google ADK agent (LiteLLM for Anthropic, native Gemini, or a scripted fake model) streams server-sent events. Tools: `update_profile`, `search_units`, `compare_financing`, `project_returns`, `search_knowledge`, `create_lead`, `build_report`. The model never computes numbers; every figure comes from a tool.

Grounding check: after each reply, numbers in the text are compared against the tool results of the turn. If some cannot be traced, a note is appended to the reply saying so.

## Quickstart

```
uv sync --all-extras
python scripts/dev_stack.py --provider fake     # embedded Postgres, migrations, seed, API on :8000
cd frontend && npm install && npm run dev       # UI on :5173
python scripts/smoke_e2e.py                     # end-to-end check against the running API
```

Checks: `uv run ruff check . && uv run ruff format --check . && uv run lint-imports && uv run pytest`.

## LLM providers

Set `LLM_PROVIDER` to `fake` (default, offline, scripted), `gemini` (`GEMINI_API_KEY`, `GEMINI_MODEL`) or `anthropic` (`ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`). See `.env.example` for all settings, including financing assumptions.

## Evaluation

All numbers are on synthetic data. Results are in `evals/results/`; regenerate with `scripts/train_market_models.py`, `scripts/eval_rag.py` and `scripts/eval_agent.py`.

| Area | Metric | Result |
| --- | --- | --- |
| Area price forecast (ARIMA, rolling origin, 12 areas, 12-month horizon) | MAPE | 5.9% (seasonal naive 20.4%) |
| | MASE | 0.94 (seasonal naive 3.03) |
| | 80% interval coverage | 0.77 (seasonal naive 0.32) |
| Unit value (LightGBM quantile, EGP/m2) | Holdout MAE | 7,807 (baseline 17,176) |
| | 80% interval coverage | 0.74 |
| Rent (LightGBM) | Holdout MAE / MAPE | 6,587 EGP / 10.2% |
| RAG (26 questions, EN+AR, k=4, hashing embedder) | Recall@4, BM25 / vector / hybrid | 1.00 / 1.00 / 1.00 |
| | MRR, BM25 / vector / hybrid | 0.981 / 0.923 / 0.962 |
| Agent (10 scenarios, fake provider) | Task success | 0.90 |
| | Clarification when budget missing | 1.00 |
| | Grounding (no untraced figures) | 1.00 |

The fake provider is scripted, so the agent row tests the tools, streaming and guardrails, not language-model quality. The one failed scenario is the Arabic rent request (Madinaty, 4M EGP), where the search returns no unit. Rerun `scripts/eval_agent.py --provider gemini` against an API started with that provider for real-model numbers.

## API

- `GET /health`
- `POST /chat/sessions`, `POST /chat/sessions/{id}/messages` (SSE), `GET /chat/sessions/{id}`, `GET /chat/sessions/{id}/profile`
- `GET /reports/...` (HTML and PDF links come back as the `report` artifact)
- `POST /financing/installments`, `/financing/mortgage`, `/financing/compare`
- `POST /inventory/search`, `/inventory/shortlist`; `GET /inventory/units/{code}`, `/inventory/areas`
- `GET /market/areas/{area_id}/forecast`; `POST /market/unit-value`, `/market/rent`
- `POST /scenarios/simulate`, `/scenarios/risk`
- `GET /knowledge/search`
- `POST /leads`; `GET /broker/leads` (header `X-API-Key`)

## Deploy

Backend: `Dockerfile` and `fly.toml` (Fly.io app `reic-companion`, port 8080, `/health` check, machines auto-stop). The container runs `alembic upgrade head` and then the API. Set secrets with `fly secrets set DATABASE_URL=... GEMINI_API_KEY=... BROKER_API_KEY=... WEBHOOK_SECRET=...`; use a Postgres with pgvector (Neon). The image omits the `forecast` and `retrieval` extras to stay small.

Frontend: Cloudflare Pages, build command `npm run build`, output directory `frontend/dist`, environment variable `VITE_API_URL` pointing at the API. Add the Pages origin to `CORS_ORIGINS`.

## Limitations

- Synthetic data only; projections are illustrative and not advice.
- Backtests use 3 origins per area on a short synthetic series; metrics are optimistic about real markets.
- RAG evaluation uses the hashing embedder and a small corpus; the gold set is easy.
- The agent evaluation uses a scripted model; no real-LLM numbers are recorded yet.
- The container image has no Prophet or sentence-transformers; it uses the hashing embedder unless `retrieval` is added.
