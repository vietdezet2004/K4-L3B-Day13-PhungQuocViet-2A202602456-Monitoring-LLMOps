from __future__ import annotations

import os
from contextlib import asynccontextmanager

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from structlog.contextvars import bind_contextvars

from .agent import LabAgent
from .incidents import disable, enable, status
from .logging_config import configure_logging, get_logger
from .metrics import record_error, snapshot
from .middleware import CorrelationIdMiddleware
from .pii import hash_user_id, summarize_text
from .schemas import ChatRequest, ChatResponse
from .tracing import tracing_enabled

configure_logging()
log = get_logger()
agent = LabAgent()


@asynccontextmanager
async def lifespan(_: FastAPI):
    log.info(
        "app_started",
        service=os.getenv("APP_NAME", "day13-monitoring-llmops-lab"),
        env=os.getenv("APP_ENV", "dev"),
        payload={"tracing_enabled": tracing_enabled()},
    )
    yield


app = FastAPI(title="Day 13 Monitoring & LLMOps Lab", lifespan=lifespan)
app.add_middleware(CorrelationIdMiddleware)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "tracing_enabled": tracing_enabled(), "incidents": status()}


@app.get("/metrics")
async def metrics() -> dict:
    return snapshot()


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    log_path = Path(os.getenv("LOG_PATH", "data/logs.jsonl"))
    records = []
    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass

    req_received = [r for r in records if r.get("event") == "request_received"]
    resp_sent = [r for r in records if r.get("event") == "response_sent"]
    req_failed = [r for r in records if r.get("event") == "request_failed"]

    latencies = [r.get("latency_ms", 0) for r in resp_sent if "latency_ms" in r]
    ttfts = [r.get("ttft_ms", 0) for r in resp_sent if "ttft_ms" in r]

    def pct(values, p):
        if not values:
            return 0
        items = sorted(values)
        idx = max(0, min(len(items) - 1, round((p / 100) * len(items) + 0.5) - 1))
        return items[idx]

    p50 = pct(latencies, 50)
    p95 = pct(latencies, 95)
    p99 = pct(latencies, 99)
    ttft_p95 = pct(ttfts, 95)

    traffic_count = len(req_received)
    rate_per_min = traffic_count  # In workload sample window

    total_reqs = max(1, len(req_received))
    error_rate = round((len(req_failed) / total_reqs) * 100, 2)

    tools = [r.get("tool_success") for r in resp_sent if r.get("tool_success") is not None] + [
        r.get("tool_success") for r in req_failed if r.get("tool_success") is not None
    ]
    tool_success_cnt = sum(1 for t in tools if t is True)
    retrieval_rate = round((tool_success_cnt / max(1, len(tools))) * 100, 1) if tools else 100.0

    costs = [r.get("cost_usd", 0.0) for r in resp_sent]
    total_cost = round(sum(costs), 4)

    tokens_in = sum(r.get("tokens_in", 0) for r in resp_sent)
    tokens_out = sum(r.get("tokens_out", 0) for r in resp_sent)

    qualities = [r.get("quality_score", 0.0) for r in resp_sent if "quality_score" in r]
    avg_quality = round(sum(qualities) / max(1, len(qualities)), 2) if qualities else 0.0

    # Status indicators based on config/dashboard.yaml thresholds
    lat_status = "PASS" if p95 <= 3000 else "VIOLATION"
    lat_color = "#10b981" if p95 <= 3000 else "#ef4444"

    traf_status = "PASS" if rate_per_min >= 1 else "VIOLATION"
    traf_color = "#10b981" if rate_per_min >= 1 else "#ef4444"

    err_status = "PASS" if error_rate <= 2 else "VIOLATION"
    err_color = "#10b981" if error_rate <= 2 else "#ef4444"

    cost_status = "PASS" if total_cost <= 2.5 else "VIOLATION"
    cost_color = "#10b981" if total_cost <= 2.5 else "#ef4444"

    tok_status = "PASS" if (tokens_in + tokens_out) <= 50000 else "VIOLATION"
    tok_color = "#10b981" if (tokens_in + tokens_out) <= 50000 else "#ef4444"

    qual_status = "PASS" if avg_quality >= 0.75 else "VIOLATION"
    qual_color = "#10b981" if avg_quality >= 0.75 else "#ef4444"

    recent_rows = ""
    for r in resp_sent[-5:][::-1]:
        cid = r.get("correlation_id", "N/A")
        feat = r.get("feature", "N/A")
        lat = r.get("latency_ms", 0)
        cost = r.get("cost_usd", 0)
        q = r.get("quality_score", 0)
        recent_rows += f"""
        <tr style="border-bottom: 1px solid #334155;">
            <td style="padding: 8px 12px; font-family: monospace; color: #38bdf8;">{cid}</td>
            <td style="padding: 8px 12px;">{feat}</td>
            <td style="padding: 8px 12px; font-weight: bold; color: {'#ef4444' if lat > 3000 else '#f1f5f9'};">{lat} ms</td>
            <td style="padding: 8px 12px;">${cost}</td>
            <td style="padding: 8px 12px;">{q}</td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="30">
    <title>K4-L3B Day 13 Monitoring & LLMOps Dashboard</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 24px; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; border-bottom: 1px solid #1e293b; padding-bottom: 16px; }}
        .title-box h1 {{ font-size: 24px; color: #f8fafc; margin-bottom: 4px; }}
        .title-box p {{ color: #94a3b8; font-size: 14px; }}
        .badges {{ display: flex; gap: 10px; }}
        .badge {{ background: #1e293b; border: 1px solid #334155; padding: 6px 12px; border-radius: 6px; font-size: 13px; color: #38bdf8; font-weight: 500; }}
        .grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 24px; }}
        .panel {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; display: flex; flex-direction: column; justify-content: space-between; }}
        .panel-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }}
        .panel-title {{ font-size: 15px; font-weight: 600; color: #e2e8f0; }}
        .panel-status {{ font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: bold; color: white; }}
        .main-stat {{ font-size: 32px; font-weight: 700; color: #f8fafc; margin-bottom: 12px; }}
        .stat-unit {{ font-size: 14px; font-weight: normal; color: #94a3b8; margin-left: 4px; }}
        .stat-details {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 13px; color: #cbd5e1; border-top: 1px solid #334155; padding-top: 12px; }}
        .threshold-info {{ margin-top: 12px; font-size: 12px; color: #94a3b8; background: #0f172a; padding: 6px 10px; border-radius: 6px; }}
        .recent-section {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; }}
        .recent-section h2 {{ font-size: 16px; margin-bottom: 12px; color: #e2e8f0; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
        th {{ text-align: left; padding: 8px 12px; background: #0f172a; color: #94a3b8; border-bottom: 1px solid #334155; }}
    </style>
</head>
<body>
    <div class="header">
        <div class="title-box">
            <h1>📊 K4-L3B Day 13 Monitoring & LLMOps Dashboard</h1>
            <p>Target: <code>day13-l3b-monitoring-llmops-lab</code> | Source: <code>data/logs.jsonl</code></p>
        </div>
        <div class="badges">
            <span class="badge">🕒 Time Range: Last 60m</span>
            <span class="badge">🔄 Auto-Refresh: 30s</span>
            <span class="badge">🧑 Student: 2A202602456</span>
        </div>
    </div>

    <div class="grid">
        <!-- 1. Latency Panel -->
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">1. Latency percentiles & TTFT</span>
                <span class="panel-status" style="background: {lat_color};">{lat_status}</span>
            </div>
            <div class="main-stat">{p95}<span class="stat-unit">ms (P95)</span></div>
            <div class="stat-details">
                <div>P50: <b>{p50} ms</b></div>
                <div>P99: <b>{p99} ms</b></div>
                <div>TTFT P95: <b>{ttft_p95} ms</b></div>
                <div>Samples: <b>{len(latencies)}</b></div>
            </div>
            <div class="threshold-info">Ngưỡng: <b>P95 &le; 3000 ms</b> (SLO Target)</div>
        </div>

        <!-- 2. Traffic Panel -->
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">2. Request traffic</span>
                <span class="panel-status" style="background: {traf_color};">{traf_status}</span>
            </div>
            <div class="main-stat">{traffic_count}<span class="stat-unit">requests</span></div>
            <div class="stat-details">
                <div>Rate: <b>{rate_per_min} req/min</b></div>
                <div>Received: <b>{len(req_received)}</b></div>
                <div>Sent: <b>{len(resp_sent)}</b></div>
                <div>Failed: <b>{len(req_failed)}</b></div>
            </div>
            <div class="threshold-info">Ngưỡng: <b>rate_per_minute &ge; 1</b></div>
        </div>

        <!-- 3. Errors Panel -->
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">3. Error rate & retrieval success</span>
                <span class="panel-status" style="background: {err_color};">{err_status}</span>
            </div>
            <div class="main-stat">{error_rate}%<span class="stat-unit">error rate</span></div>
            <div class="stat-details">
                <div>Retrieval Success: <b>{retrieval_rate}%</b></div>
                <div>Failed Requests: <b>{len(req_failed)}</b></div>
                <div>Total Analyzed: <b>{len(records)}</b></div>
                <div>Tool Calls: <b>{len(tools)}</b></div>
            </div>
            <div class="threshold-info">Ngưỡng: <b>error_rate &le; 2%</b> | Retrieval &ge; 90%</div>
        </div>

        <!-- 4. Cost Panel -->
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">4. Cost over time</span>
                <span class="panel-status" style="background: {cost_color};">{cost_status}</span>
            </div>
            <div class="main-stat">${total_cost:.4f}<span class="stat-unit">USD total</span></div>
            <div class="stat-details">
                <div>Cost/req avg: <b>${(total_cost/max(1,len(resp_sent))):.6f}</b></div>
                <div>Cost rate: <b>${total_cost:.4f}/min</b></div>
            </div>
            <div class="threshold-info">Ngưỡng: <b>total cost &le; $2.5 USD</b></div>
        </div>

        <!-- 5. Tokens Panel -->
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">5. Input and output tokens</span>
                <span class="panel-status" style="background: {tok_color};">{tok_status}</span>
            </div>
            <div class="main-stat">{tokens_in + tokens_out:,}<span class="stat-unit">tokens total</span></div>
            <div class="stat-details">
                <div>Tokens In: <b>{tokens_in:,}</b></div>
                <div>Tokens Out: <b>{tokens_out:,}</b></div>
                <div>Avg/req: <b>{int((tokens_in+tokens_out)/max(1,len(resp_sent)))}</b></div>
                <div>Model: <b>claude-sonnet-4-5</b></div>
            </div>
            <div class="threshold-info">Ngưỡng: <b>sum_by_field &le; 50,000</b></div>
        </div>

        <!-- 6. Quality Panel -->
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">6. Quality proxy</span>
                <span class="panel-status" style="background: {qual_color};">{qual_status}</span>
            </div>
            <div class="main-stat">{avg_quality:.2f}<span class="stat-unit">/ 1.0 score</span></div>
            <div class="stat-details">
                <div>Min Score: <b>{min(qualities) if qualities else 0}</b></div>
                <div>Max Score: <b>{max(qualities) if qualities else 0}</b></div>
                <div>Evaluated: <b>{len(qualities)}</b></div>
                <div>Proxy metric: <b>heuristic</b></div>
            </div>
            <div class="threshold-info">Ngưỡng: <b>mean quality &ge; 0.75</b></div>
        </div>
    </div>

    <div class="recent-section">
        <h2>📋 Recent Traced Requests (From <code>data/logs.jsonl</code>)</h2>
        <table>
            <thead>
                <tr>
                    <th>Correlation ID</th>
                    <th>Feature</th>
                    <th>Latency (ms)</th>
                    <th>Cost (USD)</th>
                    <th>Quality</th>
                </tr>
            </thead>
            <tbody>
                {recent_rows}
            </tbody>
        </table>
    </div>
</body>
</html>
    """
    return HTMLResponse(content=html)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    from dotenv import load_dotenv
    load_dotenv(".env", override=True)
    bind_contextvars(
        user_id_hash=hash_user_id(body.user_id),
        session_id=body.session_id,
        feature=body.feature,
        model=agent.model,
        env=os.getenv("APP_ENV", "dev"),
    )

    log.info(
        "request_received",
        service="api",
        payload={"message_preview": summarize_text(body.message)},
    )
    try:
        result = agent.run(
            user_id=body.user_id,
            feature=body.feature,
            session_id=body.session_id,
            message=body.message,
            correlation_id=request.state.correlation_id,
        )
        log.info(
            "response_sent",
            service="api",
            latency_ms=result.latency_ms,
            ttft_ms=result.ttft_ms,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            cost_usd=result.cost_usd,
            quality_score=result.quality_score,
            tool_name="retrieval",
            tool_success=True,
            payload={"answer_preview": summarize_text(result.answer)},
        )
        return ChatResponse(
            answer=result.answer,
            correlation_id=request.state.correlation_id,
            latency_ms=result.latency_ms,
            ttft_ms=result.ttft_ms,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            cost_usd=result.cost_usd,
            quality_score=result.quality_score,
        )
    except Exception as exc:  # pragma: no cover
        error_type = type(exc).__name__
        record_error(error_type)
        log.error(
            "request_failed",
            service="api",
            error_type=error_type,
            tool_name="retrieval" if isinstance(exc, RuntimeError) else None,
            tool_success=False if isinstance(exc, RuntimeError) else None,
            payload={"detail": str(exc), "message_preview": summarize_text(body.message)},
        )
        raise HTTPException(status_code=500, detail=error_type) from exc


@app.post("/incidents/{name}/enable")
async def enable_incident(name: str) -> JSONResponse:
    try:
        enable(name)
        log.warning("incident_enabled", service="control", payload={"name": name})
        return JSONResponse({"ok": True, "incidents": status()})
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/incidents/{name}/disable")
async def disable_incident(name: str) -> JSONResponse:
    try:
        disable(name)
        log.warning("incident_disabled", service="control", payload={"name": name})
        return JSONResponse({"ok": True, "incidents": status()})
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
