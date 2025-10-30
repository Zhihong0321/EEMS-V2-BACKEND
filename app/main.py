from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import get_settings
from .db import engine
from .models import Base
from .routers import blocks, readings, simulators, stream

settings = get_settings()

logging.basicConfig(level=settings.log_level.upper())
logger = logging.getLogger(__name__)

app = FastAPI(title="Eternalgy EMS Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.exception_handler(RequestValidationError)
async def handle_request_validation(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    logger.info(
        "Validation error for %s %s: %s",
        request.method,
        request.url.path,
        exc.errors(),
    )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(StarletteHTTPException)
async def handle_http_exception(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    content = {"detail": exc.detail}
    if exc.status_code >= 500:
        logger.exception(
            "HTTP exception for %s %s: %s",
            request.method,
            request.url.path,
            exc.detail,
        )
    if exc.headers:
        return JSONResponse(
            status_code=exc.status_code, content=content, headers=exc.headers
        )
    return JSONResponse(status_code=exc.status_code, content=content)


@app.exception_handler(Exception)
async def handle_unexpected_exception(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.exception(
        "Unhandled error during %s %s",
        request.method,
        request.url.path,
    )
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


DOCS_HTML = """
<!DOCTYPE html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <title>Eternalgy EMS Backend API</title>
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <style>
      :root {
        color-scheme: light dark;
        --bg: #0b1021;
        --fg: #f5f7ff;
        --accent: #3fa7ff;
        --muted: #a5acc6;
        --card: rgba(255, 255, 255, 0.08);
      }
      body {
        margin: 0;
        padding: 2rem;
        font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        background: radial-gradient(circle at 25% 25%, rgba(63, 167, 255, 0.12), transparent 55%),
          radial-gradient(circle at 80% 20%, rgba(120, 86, 255, 0.1), transparent 60%),
          #02040a;
        color: var(--fg);
        line-height: 1.6;
      }
      a {
        color: var(--accent);
        text-decoration: none;
        font-weight: 600;
      }
      a:hover {
        text-decoration: underline;
      }
      h1 {
        font-size: 2.5rem;
        margin-bottom: 0.5rem;
      }
      h2 {
        margin-top: 2.5rem;
        font-size: 1.7rem;
      }
      h3 {
        margin-top: 1.8rem;
        font-size: 1.3rem;
      }
      p {
        margin: 0.75rem 0;
        color: var(--muted);
      }
      code, pre {
        font-family: "Fira Code", "Source Code Pro", monospace;
      }
      pre {
        background: var(--card);
        padding: 1rem;
        border-radius: 0.9rem;
        overflow: auto;
        font-size: 0.95rem;
      }
      table {
        width: 100%;
        border-collapse: collapse;
        margin: 1.2rem 0;
        background: var(--card);
        border-radius: 0.9rem;
        overflow: hidden;
      }
      th, td {
        padding: 0.85rem 1rem;
        text-align: left;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        vertical-align: top;
      }
      th {
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-size: 0.75rem;
        color: var(--muted);
      }
      tr:last-child td {
        border-bottom: none;
      }
      .card {
        background: var(--card);
        border-radius: 1rem;
        padding: 1.5rem;
        margin-top: 1.5rem;
      }
      .badge {
        display: inline-block;
        padding: 0.15rem 0.65rem;
        border-radius: 999px;
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        background: rgba(63, 167, 255, 0.2);
        color: var(--accent);
        margin-right: 0.5rem;
      }
      .stack {
        display: grid;
        gap: 0.75rem;
      }
      @media (max-width: 720px) {
        body {
          padding: 1.5rem 1rem;
        }
        table, pre {
          font-size: 0.9rem;
        }
      }
    </style>
  </head>
  <body>
    <header>
      <span class=\"badge\">Eternalgy EMS</span>
      <h1>Backend API Guide</h1>
      <p>
        Everything you need to integrate the Eternalgy EMS backend. The API ingests simulator readings, aggregates
        them into 30-minute KL blocks, and emits <code>alert-ready</code> SSE events once usage crosses 80% of the target.
      </p>
      <p>
        Prefer interactive docs? Jump straight to the <a href=\"/docs\">Swagger UI</a>.
      </p>
    </header>

    <section>
      <h2>Auth quick facts</h2>
      <div class=\"card stack\">
        <p><strong>API key header:</strong> <code>x-api-key: &lt;BACKEND_API_KEY&gt;</code> (required for every <em>write</em> endpoint).</p>
        <p><strong>Read endpoints</strong> (<code>GET /blocks</code>, <code>/stream</code>, <code>/healthz</code>) are public.</p>
      </div>
    </section>

    <section>
      <h2>Simulator APIs</h2>
      <div class=\"card\">
        <h3>POST /api/v1/simulators</h3>
        <p>Create a simulator profile or overwrite an existing one (matched by <code>name</code>).</p>
        <table>
          <thead>
            <tr>
              <th>Field</th>
              <th>Type</th>
              <th>Required?</th>
              <th>Accepted aliases</th>
              <th>Example</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><code>name</code></td>
              <td>string</td>
              <td>yes</td>
              <td><code>name</code>, <code>simulator_name</code>, <code>simulatorName</code></td>
              <td><code>"Factory A"</code></td>
            </tr>
            <tr>
              <td><code>target_kwh</code></td>
              <td>number ≥ 0</td>
              <td>yes</td>
              <td><code>target_kwh</code>, <code>targetKwh</code>, <code>target_kWh</code>, <code>targetKWhr</code></td>
              <td><code>120</code></td>
            </tr>
            <tr>
              <td><code>whatsapp_number</code></td>
              <td>integer (digits only)</td>
              <td>no</td>
              <td><code>whatsapp_number</code>, <code>whatsappNumber</code>, <code>whatsapp_no</code>, <code>whatsappNo</code></td>
              <td><code>60123456789</code></td>
            </tr>
          </tbody>
        </table>
        <p><strong>Sample request:</strong></p>
        <pre><code>curl -X POST "$BASE_URL/api/v1/simulators" \<br />
  -H "content-type: application/json" \<br />
  -H "x-api-key: $BACKEND_API_KEY" \<br />
  -d '{
    "name": "Factory A",
    "targetKwh": 120,
    "whatsappNumber": 60123456789
  }'</code></pre>
        <p><strong>Sample response:</strong></p>
        <pre><code>{
  "data": {
    "id": "c7d7c9ad-33ce-42a8-8f7d-3aaf1c6de123",
    "name": "Factory A",
    "target_kwh": 120.0,
    "whatsapp_number": 60123456789,
    "created_at": "2024-05-02T06:00:00Z",
    "updated_at": "2024-05-02T06:00:00Z"
  }
}</code></pre>
      </div>

      <div class=\"card\">
        <h3>GET /api/v1/simulators</h3>
        <p>Return all simulators in creation order.</p>
        <p><strong>Sample response:</strong></p>
        <pre><code>{
  "data": [
    {
      "id": "c7d7c9ad-33ce-42a8-8f7d-3aaf1c6de123",
      "name": "Factory A",
      "target_kwh": 120.0,
      "whatsapp_number": 60123456789,
      "created_at": "2024-05-02T06:00:00Z",
      "updated_at": "2024-05-02T06:00:00Z"
    }
  ]
}</code></pre>
      </div>
    </section>

    <section>
      <h2>Readings ingestion</h2>
      <div class=\"card\">
        <h3>POST /api/v1/readings:ingest</h3>
        <p>Bulk insert tick data for a simulator. Each tick carries power (kW) and the number of seconds the reading covers.</p>
        <p><strong>Sample request:</strong></p>
        <pre><code>curl -X POST "$BASE_URL/api/v1/readings:ingest" \<br />
  -H "content-type: application/json" \<br />
  -H "x-api-key: $BACKEND_API_KEY" \<br />
  -d '{
    "simulator_id": "c7d7c9ad-33ce-42a8-8f7d-3aaf1c6de123",
    "mode": "auto",
    "ticks": [
      { "power_kw": 350.5, "sample_seconds": 15, "device_ts": "2024-05-02T08:00:15Z" },
      { "power_kw": 355.2, "sample_seconds": 15, "device_ts": "2024-05-02T08:00:30Z" }
    ]
  }'</code></pre>
        <p><strong>Sample response:</strong></p>
        <pre><code>{
  "accepted": 2,
  "sse_emitted": true
}</code></pre>
        <p><strong>Alias tips:</strong> Accepts <code>simulatorId</code>, <code>powerKw</code>, <code>sampleSeconds</code>, and <code>deviceTs</code> too.</p>
      </div>
    </section>

    <section>
      <h2>Blocks &amp; history</h2>
      <div class=\"card\">
        <h3>GET /api/v1/blocks/latest</h3>
        <p>Query with <code>?simulator_id=&lt;UUID&gt;</code> to obtain the most recent 30-minute block.</p>
        <pre><code>{
  "simulator_id": "c7d7c9ad-33ce-42a8-8f7d-3aaf1c6de123",
  "block_start_local": "2024-05-02T14:00:00+08:00",
  "block_start_utc": "2024-05-02T06:00:00Z",
  "block_end_utc": "2024-05-02T06:30:00Z",
  "target_kwh": 120.0,
  "accumulated_kwh": 96.5,
  "percent_of_target": 80.42,
  "alerted_80pct": true,
  "chart_bins": {
    "bin_seconds": 30,
    "points": [12.5, 24.8, 36.1, 48.3, 60.0, 72.4, 84.9, 96.5]
  }
}</code></pre>
      </div>

      <div class=\"card\">
        <h3>GET /api/v1/blocks/history</h3>
        <p>Query with <code>?simulator_id=&lt;UUID&gt;&amp;limit=10</code> to fetch past block summaries.</p>
        <pre><code>{
  "data": [
    {
      "block_start_local": "2024-05-02T13:30:00+08:00",
      "target_kwh": 120.0,
      "accumulated_kwh": 101.2,
      "percent_of_target": 84.33
    },
    {
      "block_start_local": "2024-05-02T13:00:00+08:00",
      "target_kwh": 120.0,
      "accumulated_kwh": 92.4,
      "percent_of_target": 77.0
    }
  ]
}</code></pre>
      </div>
    </section>

    <section>
      <h2>Server-sent events</h2>
      <div class=\"card\">
        <h3>GET /api/v1/stream/&lt;simulator_id&gt;</h3>
        <p>Stay subscribed for live updates. A new <code>alert-ready</code> event fires once per block when usage crosses 80%.</p>
        <pre><code>{ "type": "reading", "ts": "2024-05-02T06:00:30Z", "power_kw": 352.1 }
{ "type": "block-update", "accumulated_kwh": 96.5, "percent_of_target": 80.42 }
{
  "type": "alert-ready",
  "simulator_id": "c7d7c9ad-33ce-42a8-8f7d-3aaf1c6de123",
  "block_start_utc": "2024-05-02T06:00:00Z",
  "block_window_label": "14:00–14:30 (local KL)",
  "target_kwh": 120.0,
  "accumulated_kwh": 96.5,
  "percent_of_target": 80.42
}</code></pre>
      </div>
    </section>

    <section>
      <h2>Health check</h2>
      <div class=\"card\">
        <h3>GET /healthz</h3>
        <pre><code>{ "ok": true }</code></pre>
      </div>
    </section>
  </body>
</html>
"""


@app.get("/", include_in_schema=False, response_class=HTMLResponse)
async def root_docs_page() -> HTMLResponse:
    return HTMLResponse(content=DOCS_HTML)


@app.get("/healthz")
def healthcheck() -> dict[str, bool]:
    return {"ok": True}


app.include_router(simulators.router)
app.include_router(readings.router)
app.include_router(blocks.router)
app.include_router(stream.router)
