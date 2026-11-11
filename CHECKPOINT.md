# Checkpoint — Real Estate Investment Companion

Last updated: 2026-11-12. Full design: `architecture.md`. Build plan: `PLAN.md`.

## Current State
- Build steps 1-12 done. Step 13: published to GitHub (public, CI green); deploy not started.
- Backend: 191 tests pass (unit + integration on embedded Postgres). ruff check, ruff format --check, 6/6 import-linter contracts pass.
- Frontend: lint, typecheck, 10 vitest tests, build pass.
- E2E: `scripts/smoke_e2e.py` passes against `scripts/dev_stack.py --provider fake` (EN journey, knowledge + citations, HTML report, broker handoff + broker queue auth, Arabic session). UI checked in Chrome in EN and AR (RTL), broker page loads leads.
- Live LLM (2026-11-12): valid key now in `.env`, but the old invalid system-wide `GEMINI_API_KEY` wins over `.env` in pydantic-settings, so export the `.env` key into the shell before `dev_stack.py`. Model `gemini-3.5-flash` (2.5-flash closed to new keys; 3.8-flash hangs with 504). Live smoke on 3.5-flash: buyer journey (update_profile, search_units, compare_financing, project_returns) passes in ~21s. Free tier = 5 RPM and 20 requests/day per model, which ran out before the knowledge/report/Arabic steps and the full agent eval. Live eval on `gemini-3.1-flash-lite` (no quota issues): task success 0.60, clarification 1.00, grounding 0.70, 5.3 s/scenario; it often stops after search_units and states untraced figures. Recorded in README and `evals/results/agent_eval_gemini-3.1-flash-lite.json`.
- Git: `main` on https://github.com/Mrwanawad/Real-Estate-Investment-Companion-using-Google-ADK-Litestar-LightGBM-React (public). Author Mrwan Awad, no Claude attribution.

## Modules (all under src/reic/modules)
- inventory: search + goal-weighted shortlist.
- financing: Decimal calculators (installments, mortgage, PV comparison).
- market: ARIMA(1,1,0)+drift area forecast with rolling backtest; LightGBM quantile unit value (split-conformal widened) with baseline promotion gate; LightGBM rent. Trains lazily in memory (~2s).
- scenarios: NumPy Monte Carlo (value, rent, IRR, break-even, sensitivity) + rule-based risks EN/AR.
- knowledge: 16 synthetic docs (10 EN, 6 AR), BM25 + hashing/MiniLM vectors + RRF, in-memory index.
- handoff: leads table (0003), broker API (X-API-Key guard), HMAC webhook signing `ts.body`.
- reports: Jinja2 HTML EN/AR with inline SVG; PDF via WeasyPrint when GTK exists (not on this machine, so PDF link is null).
- companion: ADK `LlmAgent` per turn, 7 tools (update_profile, search_units, compare_financing, project_returns, search_knowledge, create_lead, build_report), SSE chat API, grounding check on numbers, provider chain anthropic -> gemini with circuit breaker, scripted `FakeLlm` for tests/offline demo. Gateway over other modules in `bootstrap/companion.py`.

## Real metrics (synthetic data)
- Forecast backtest: MAPE 5.9%, MASE 0.94, 80% coverage 0.77 (seasonal naive: 20.4%, 3.03, 0.32).
- Unit value: holdout MAE 7,807 EGP/m2 vs baseline 17,176; P10-P90 coverage 0.737 after conformal (target 0.80).
- Rent: MAE 6,587 EGP, MAPE 10.2%.
- Agent eval (10 scenarios, fake provider): task success 0.90, clarification 1.00, grounding 1.00. The one miss (Arabic, 4M EGP, Madinaty) has no matching synthetic units.
- RAG (26 gold Qs): recall@4 1.00 all modes; MRR bm25 0.981, vector 0.923, hybrid 0.962.

## Packaging
- Dockerfile (python:3.12-slim + pango for WeasyPrint), .dockerignore, fly.toml, CI updated, README rewritten. Docker image never built (not allowed on this machine).

## Decisions
- Gemini client: 60s request timeout + 3 retry attempts with backoff (429/5xx) via ADK `retry_options`. Tool "started" events only from non-partial ADK events (SSE mode repeated every call). Smoke/eval take `--pause SECONDS` per turn for free-tier keys.
- Rate limit (2026-11-12): Litestar RateLimitMiddleware on POST /leads, POST /chat/sessions, POST /chat/sessions/{id}/messages only; `RATE_LIMIT_PER_MINUTE` (default 20, 0 off), client id from `CLIENT_IP_HEADER` when set (fly.toml sets Fly-Client-IP), else socket IP. In-memory store (single machine). dev_stack sets it to 0 so smoke/eval can burst. Code: `bootstrap/rate_limit.py`.
- See PLAN.md locked decisions. Added: knowledge index in memory (corpus is small; pgvector not needed yet). Chat sessions in memory (single process, capped at 2000).
- Webhook signature = HMAC-SHA256 over `"<timestamp>." + body`, header `X-REIC-Signature: sha256=<hex>` + `X-REIC-Timestamp`.
- Financing assumptions in Settings: discount 22%, mortgage 24% / 10y / 20% down, inflation 15% (synthetic).

## Next
- Live eval on gemini-3.5-flash needs quota: enable billing on the Gemini key's project (cents per run) or wait for the daily reset, then `scripts/smoke_e2e.py --pause 15` and `scripts/eval_agent.py --provider gemini --pause 15`; record numbers in README.
- Deploy: flyctl, neonctl, wrangler not installed; each needs an interactive login (Fly also wants a card). Fly.io (API) + Neon (DB) + Cloudflare Pages (UI).
- Optional: async webhook; PDF in Docker (GTK in image).

## Gotchas
- `GEMINI_API_KEY` set system-wide here is invalid; tests force `LLM_PROVIDER=fake`.
- `scripts/dev_stack.py` keeps pgdata in `%LOCALAPPDATA%\reic\pgdata` (pgserver breaks on spaced paths). API on :8000, broker key `dev-broker-key`.
- ADK instruction is passed as a callable so the profile's braces are not treated as state templates.
- Tool failures return `{"error": ...}` to the model (wrapper in toolbox) instead of killing the turn.
- `google-adk` 2.14 pins `google-genai>=2.30,<3`. TypeScript pinned `~6.0`. Never run `docker build` on this machine.
- If dev_stack was killed, Postgres crash-recovers on next start (~35s) and pgserver's 10s pg_ctl timeout fails; rerun once. Stop with `pg_ctl -D %LOCALAPPDATA%\reic\pgdata stop -m fast`.
- `pgserver` prints a harmless `I/O operation on closed file` at exit.
