# Real Estate Investment Companion Agent — Architecture

## Scenario
Buyers and small investors in real estate struggle with big decisions: which unit, cash vs. installments vs. mortgage, rent it out or resell, what return to expect, and what the risks are. Brokers cannot spend hours on each. The companion is a general-purpose AI agent for any real estate company: it profiles the buyer's goals and budget, compares units, simulates financing and returns (resale value, rental yield) under scenarios, explains risks in plain Arabic or English, and hands qualified buyers to a broker.

## Input
- Buyer conversation: goal (live / rent / resell), budget, down payment, monthly capacity, horizon, risk tolerance, preferred areas.
- Inventory database and payment plans.
- Market data: historical area price indices, rental listings, inflation, interest rates.
- Company documents: contracts, policies, financing options (for grounded answers).

## Output
- Shortlist of units fitting the goal and budget.
- Financing comparison: cash vs. installment vs. mortgage (total cost, monthly payment, present value).
- Return projection: expected resale value range and rental yield at horizon (P10 / P50 / P90), break-even point.
- Risk summary: delivery risk, liquidity, price sensitivity, currency/inflation exposure.
- Shareable PDF/HTML report; broker handoff with buyer profile.

## Architecture

```
 Buyer (chat UI)
        |
        v
 [Companion agent - LangGraph]
   profile buyer -> clarify goals -> plan tools
        |
        +--> [Inventory tool]      SQL search by budget/area/type
        +--> [Financing tool]      deterministic calculators (installments, mortgage, PV/NPV/IRR)
        +--> [Forecast tool]       area price index forecast (Prophet / statsmodels)
                                   + quantile LightGBM unit-level value at horizon
        +--> [Rental tool]         rental yield model (LightGBM) by area/type/size
        +--> [Scenario simulator]  Monte Carlo over price growth, inflation, rates, vacancy
        +--> [Knowledge RAG]       contracts/policies/FAQ (pgvector + BM25), cited
        +--> [Handoff tool]        CRM lead with buyer profile
        |
        v
 [Answer composer]  plain-language explanation, charts, disclaimers, citations
        |
        v
 [Report generator]  HTML/PDF summary
        |
 [Observability]  Langfuse; eval set of buyer scenarios
```

## Tools Used
- Agents: Claude tool use, LangGraph
- Forecasting: Prophet, statsmodels, LightGBM (quantile), sktime
- Simulation & finance: NumPy (Monte Carlo), numpy-financial (NPV, IRR, PMT)
- Retrieval: PostgreSQL + pgvector, BM25, bge-m3, reranker
- Data: pandas, polars
- Visualization: Plotly
- Backend: FastAPI, Pydantic
- UI: Streamlit (chat + charts) or Next.js
- Reports: Jinja2 + WeasyPrint
- Evaluation & observability: Ragas, custom scenario tests, Langfuse
- DevOps: Docker, GitHub Actions, pytest, ruff

## Tools Not Used (and why)
- LLM-computed numbers: all financial math in deterministic tools.
- Single-point forecasts: always ranges (P10/P50/P90) with assumptions shown.
- Investment guarantees: outputs are scenarios, not advice; disclaimers included.

## Methodologies
- Tool-using agent with grounded calculations; quantile forecasting + Monte Carlo scenarios.
- Backtesting forecasts on historical periods; scenario-based eval suite for the agent.

## Evaluation Metrics
- Forecast: MAPE / MASE on backtest, interval coverage.
- Rental model: MAE, MAPE.
- Calculator correctness: unit tests vs. reference values (100% required).
- Agent: task success on scenario set, faithfulness of explanations, clarification quality.
- Business: buyer-to-broker handoff rate, handoff-to-reservation conversion.

## Production Monitoring
- Forecast error drift as new prices arrive; retrain monthly.
- Conversation drop-off points, unanswered questions.
- Latency, token cost, tool error rate.

## Deployment Plan
- Streamlit Community Cloud (chat + charts + report download), or Render (FastAPI) + Vercel (Next.js) for a fuller product.
- Demo data: synthetic inventory and public market indices.
