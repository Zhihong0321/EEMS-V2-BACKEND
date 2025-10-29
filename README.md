Got it. Here’s a tight, Codex-optimized backend spec you can drop straight into your repo (e.g., as `BACKEND_SPEC.md`). It’s written to give Codex explicit “what/why/how/when,” unambiguous contracts, and copy-pasteable scaffolding.

---

# Eternalgy EMS — Backend Project Spec (Prototype)

**Service name:** `eternalgy-ems-backend`
**Runtime:** Python 3.11 + FastAPI + Uvicorn
**DB:** PostgreSQL
**Deploy target:** Railway (Docker)
**Timezone of business logic:** `Asia/Kuala_Lumpur` (KL)

---

## 0) Purpose (What & Why)

**What:**
A minimal backend that ingests simulated energy readings, aggregates them into fixed 30-minute blocks (starting 00:00 daily, KL time), exposes read APIs for the dashboard, and emits live updates (SSE). When the current block reaches **≥80%** of the target kWh the backend marks the block as "alert-ready" and streams that fact so the frontend can decide how to notify users.

**Why:**

* Help factory managers control 30-minute peak usage to avoid MD (Maximum Demand) penalties.
* Keep prototype simple (REST + SSE, no over-engineering).
* Make future switch to **real MQTT meters** painless by isolating ingestion behind a small adapter.

---

## 1) Scope (When & Non-Goals)

**In-scope (now):**

* REST ingestion endpoint for simulator
* 30-min block computation + accumulation
* 80% threshold detection + SSE "alert-ready" event (frontend handles messaging)
* Read APIs for latest block & recent block history
* SSE endpoint for live UI updates
* API key auth (simple)
* SQL schema + one-shot migration
* Railway-ready Dockerfile + start commands

**Out-of-scope (later):**

* MQTT ingestion (design adapter only)
* Multi-tenant/billing/roles
* Complex analytics beyond 30-min blocks
* Retry/queue systems (keep it synchronous & simple)

---

## 2) Architecture (How)

```
Simulator (Frontend) --REST--> Backend /readings:ingest --> Postgres
                                                  |--> 30-min block upsert & accumulate
                                                  |--> 80% threshold flip → mark alert-ready
                                                  |--> SSE push to /stream/:sim_id

Dashboard (Frontend) <--REST/SSE-- Backend <---> Postgres
```

**Key choices:**

* **REST** for write/read; **SSE** for live updates (lower complexity than WebSocket).
* Store raw **power_kW** samples + **sample_seconds** → compute **energy_kWh** on insert.
* Convert timestamps to **Asia/Kuala_Lumpur** to find the block bucket, but persist UTC for consistency.
* “Ingestion adapter” function used by both REST (today) and MQTT (future) to avoid refactors.

---

## 3) Environment & Config

Required env vars:

* `DATABASE_URL` — PostgreSQL URL (from Railway)
* `BACKEND_API_KEY` — static API key for write endpoints
* `TZ=Asia/Kuala_Lumpur` — ensure process timezone (and be explicit in code)
Optional env vars:

* `PORT` (Railway provides)
* `LOG_LEVEL` (default `info`)

---

## 4) Database Schema (SQL)

> Save as `db/init.sql`. Run once against `DATABASE_URL`.

```sql
create extension if not exists pgcrypto; -- for gen_random_uuid()
create extension if not exists uuid-ossp;

create table if not exists simulators (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  target_kwh numeric(12,4) not null check (target_kwh >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Raw readings (simulated)
create table if not exists readings (
  id bigserial primary key,
  simulator_id uuid not null references simulators(id) on delete cascade,
  ts_utc timestamptz not null default now(),    -- server receive time if not provided
  device_ts timestamptz,                        -- optional client-declared time
  power_kw numeric(12,4) not null check (power_kw >= 0),
  sample_seconds int not null check (sample_seconds > 0),
  energy_kwh numeric(12,6) generated always as (power_kw * sample_seconds / 3600.0) stored
);
create index if not exists idx_readings_sim_ts on readings (simulator_id, ts_utc);

-- 30-minute blocks (fixed windows starting at 00:00 KL time)
create table if not exists blocks_30m (
  id bigserial primary key,
  simulator_id uuid not null references simulators(id) on delete cascade,
  block_start_local timestamptz not null,
  block_start_utc timestamptz not null,
  block_end_utc timestamptz not null,
  target_kwh numeric(12,4) not null,
  accumulated_kwh numeric(14,6) not null default 0,
  alerted_80pct boolean not null default false,
  unique(simulator_id, block_start_utc)
);
create index if not exists idx_blocks_sim_start on blocks_30m (simulator_id, block_start_utc);

```

---

## 5) API Contracts (REST)

### 5.0 API discovery when deployed

The deployed service exposes the interactive Swagger UI at the root path
(`/`). Visiting the base URL of the Railway deployment immediately loads the
API documentation so the frontend team can explore every route without
guessing the location. The OpenAPI schema remains available at `/openapi.json`
for programmatic use.

### Auth

All **write** calls require header:
`x-api-key: <BACKEND_API_KEY>`

### 5.1 Create/Update Simulator

`POST /api/v1/simulators`

**Body**

```json
{
  "name": "Factory A",
  "target_kwh": 120.0
}
```

**Response 200**

```json
{
  "id": "c7d7c9ad-33ce-42a8-8f7d-3aaf1c6de123",
  "name": "Factory A",
  "target_kwh": 120.0,
  "created_at": "2025-10-29T06:00:00Z",
  "updated_at": "2025-10-29T06:00:00Z"
}
```

### 5.2 List Simulators

`GET /api/v1/simulators`

**Response 200** – array of simulators (fields as above).

### 5.3 Ingest Readings (bulk)

`POST /api/v1/readings:ingest`

**Body**

```json
{
  "simulator_id": "c7d7c9ad-33ce-42a8-8f7d-3aaf1c6de123",
  "mode": "auto",
  "ticks": [
    { "power_kw": 350.5, "sample_seconds": 15, "device_ts": "2025-10-29T08:00:15Z" },
    { "power_kw": 355.2, "sample_seconds": 15, "device_ts": "2025-10-29T08:00:30Z" }
  ]
}
```

**Simulator workflow**

1. Retrieve (or create) the simulator via `POST /api/v1/simulators` and store
   the returned `id`.
2. Send readings with the simulator's UUID and a batch of ticks using the
   `POST /api/v1/readings:ingest` endpoint shown above. Each tick represents a
   single instantaneous power sample and its duration in seconds.
3. (Optional) Supply `device_ts` per tick if the simulator keeps its own
   timestamp. The backend will default to the receive time for any missing
   values.
4. Repeat this request for every batch of readings. The backend persists the
   samples, updates the 30-minute block aggregates, emits SSE updates, and
   checks the 80% alert threshold automatically.

**Response 200**

```json
{ "accepted": 2, "sse_emitted": true }
```

### 5.4 Latest Block (for current window)

`GET /api/v1/blocks/latest?simulator_id=<UUID>`

**Response 200**

```json
{
  "simulator_id": "c7d7c9ad-33ce-42a8-8f7d-3aaf1c6de123",
  "block_start_local": "2025-10-29T14:00:00+08:00",
  "block_start_utc": "2025-10-29T06:00:00Z",
  "block_end_utc": "2025-10-29T06:30:00Z",
  "target_kwh": 120.0,
  "accumulated_kwh": 96.5,
  "percent_of_target": 80.42,
  "alerted_80pct": true,
  "chart_bins": {
    "bin_seconds": 30,
    "points": [ /* 60 cumulative values aligned to the 30-minute window */ ]
  }
}
```

### 5.5 Block History (last N windows)

`GET /api/v1/blocks/history?simulator_id=<UUID>&limit=10`

**Response 200** – array of:

```json
{
  "block_start_local": "2025-10-29T13:30:00+08:00",
  "target_kwh": 120.0,
  "accumulated_kwh": 101.2,
  "percent_of_target": 84.33
}
```

### 5.6 Live Stream (SSE)

`GET /api/v1/stream/:simulator_id`

**Events:**

```json
{ "type": "reading", "ts": "2025-10-29T06:00:30Z" }
{ "type": "block-update", "accumulated_kwh": 96.5, "percent_of_target": 80.4 }
{
  "type": "alert-ready",
  "simulator_id": "c7d7c9ad-33ce-42a8-8f7d-3aaf1c6de123",
  "block_start_utc": "2025-10-29T06:00:00Z",
  "block_window_label": "14:00–14:30 (local KL)",
  "target_kwh": 120.0,
  "accumulated_kwh": 96.5,
  "percent_of_target": 80.42
}
```

---

## 6) Core Logic (exact rules)

### 6.1 Timestamp & Block Windowing

* Choose **reading_time** per tick = `device_ts` if provided, else server `now()` (UTC).
* Convert to local KL time: `local_ts = reading_time AT TIME ZONE 'Asia/Kuala_Lumpur'`.
* Compute **block_start_local**:

  * `h = date_trunc('hour', local_ts)`
  * `half = floor(extract(minute from local_ts)/30)::int` (0 or 1)
  * `block_start_local = h + (half * interval '30 min')`
* Convert to UTC for storage:

  * `block_start_utc = block_start_local AT TIME ZONE 'UTC'`
  * `block_end_utc = block_start_utc + interval '30 min'`

### 6.2 Accumulation

* For each tick: `energy_kWh = power_kW * sample_seconds / 3600` (stored generated column).
* **Upsert** a `blocks_30m` row for `(simulator_id, block_start_utc)` with `target_kwh` = simulator.target_kwh at that moment.
* **Increment** `accumulated_kwh` by tick’s `energy_kwh`.
* Optional: write per-bin aggregation (30-second bins) in SQL for charting. Minimal approach: compute bins on the fly via query groupings from `readings` filtered to the active block.

### 6.3 80% Threshold Alert

* After updating a block:

  * If `accumulated_kwh >= 0.8 * target_kwh` **AND** `alerted_80pct=false`:

    * Set `alerted_80pct=true`
    * Emit SSE `alert-ready` with payload:

      ```json
      {
        "type": "alert-ready",
        "simulator_id": "<UUID>",
        "block_start_utc": "<ISO8601>",
        "block_window_label": "HH:MM–HH:MM (local KL)",
        "target_kwh": <float>,
        "accumulated_kwh": <float>,
        "percent_of_target": <float>
      }
      ```

> Alert-ready emits **at most once per block per simulator**. The frontend decides how to notify users (WhatsApp, SMS, etc.).

### 6.4 Idempotency (simple)

* Accept duplicate ticks; accumulation is additive.
* (Optional extension) Allow an optional `client_tick_id` to ignore duplicates. Not required for prototype.

---

## 7) Alert-ready (No Server-Side Messaging)

* Backend responsibility stops at marking the block as `alerted_80pct` and emitting the SSE `alert-ready` event.
* Frontend (or any downstream consumer) is responsible for deciding whether to send WhatsApp, email, push, etc.
* No messaging credentials are loaded on the backend; deployment environments do not need WhatsApp config.

---

## 8) SSE (Server-Sent Events) Contract

Endpoint: `GET /api/v1/stream/:simulator_id`

* Set headers: `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `Connection: keep-alive`
* Heartbeat every 15s: `event: ping\ndata: {}\n\n`
* Emit events on:

  * successful ingest (type `reading`)
  * block accumulation change (type `block-update`)
  * 80% threshold flip (type `alert-ready`)

Server snippet (pseudo):

```python
async def sse_stream(sim_id):
    # Keep a queue per simulator; ingest path puts messages here.
    # Write: yield "event: <type>\n" + "data: <json>\n\n"
```

---

## 9) Security & Validation

* Write endpoints require `x-api-key` == `BACKEND_API_KEY`.
* Validate: `power_kw >= 0`, `sample_seconds > 0`, `simulator_id` exists.
* Rate-limit (optional, not required for prototype).

---

## 10) Observability

* Log JSON lines: level, route, simulator_id, tick_count, block_start_utc, accumulated_kwh, alert_status.
* Expose health: `GET /healthz` → `{ "ok": true }`.

---

## 11) FastAPI File Layout (suggested)

```
app/
  __init__.py
  main.py             # FastAPI app, routes include
  deps.py             # db session, auth dependency
  models.py           # SQLAlchemy models
  schema.py           # Pydantic DTOs
  db.py               # engine/session init
  logic/
    ingest.py         # ingestion adapter (used by REST; future MQTT)
    blocks.py         # block math, binning
    sse.py            # broadcaster per simulator
  routers/
    simulators.py
    readings.py
    blocks.py
    stream.py
  migrations/         # optional (we use init.sql for proto)
db/
  init.sql
Dockerfile
Procfile (optional)
```

---

## 12) Pydantic DTOs (interfaces Codex should implement)

```python
# schema.py
from pydantic import BaseModel, Field, conint, confloat
from typing import List, Optional
from datetime import datetime
from uuid import UUID

class SimulatorCreate(BaseModel):
    name: str
    target_kwh: confloat(ge=0)

class SimulatorOut(SimulatorCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime

class TickIn(BaseModel):
    power_kw: confloat(ge=0)
    sample_seconds: conint(gt=0)
    device_ts: Optional[datetime] = None

class IngestIn(BaseModel):
    simulator_id: UUID
    mode: Optional[str] = Field(default=None, pattern="^(auto|manual)?$")
    ticks: List[TickIn]

class IngestOut(BaseModel):
    accepted: int
    sse_emitted: bool

class LatestBlockOut(BaseModel):
    simulator_id: UUID
    block_start_local: datetime
    block_start_utc: datetime
    block_end_utc: datetime
    target_kwh: float
    accumulated_kwh: float
    percent_of_target: float
    alerted_80pct: bool
    chart_bins: dict
```

---

## 13) Ingestion Adapter (single source of truth)

**Goal:** Both REST (now) and MQTT (future) call the same function.

```python
# logic/ingest.py
async def ingest_ticks(sim_id: UUID, ticks: list[TickIn], session) -> int:
    """
    For each tick:
      1) choose reading_time = device_ts or now()
      2) write readings row
      3) map to KL 30-min block; upsert blocks_30m
      4) add energy_kwh to accumulated_kwh
      5) if >= 80% and not alerted: mark alerted, emit alert-ready SSE payload
      6) push SSE ('reading' and 'block-update')
    Return: count of accepted ticks.
    """
```

---

## 14) Chart Binning (30-second bins)

**Why:** Frontend expects 60 points for the current 30-min window.

**How:** Group `readings` within `[block_start_utc, block_end_utc)`:

* Bin index = `floor((reading_time_local - block_start_local) / 30 seconds)` in `[0..59]`.
* Either produce **cumulative** points (recommended) or per-bin increments. Spec requires cumulative.

**Return shape (in `/blocks/latest`)**:

```json
"chart_bins": {
  "bin_seconds": 30,
  "points": [0.5, 1.1, 1.7, ...]  // len = 60
}
```

---

## 15) Docker & Railway

**Dockerfile (example):**

```dockerfile
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY db ./db
ENV TZ=Asia/Kuala_Lumpur
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

**requirements.txt (minimal):**

```
fastapi==0.115.*
uvicorn==0.30.*
sqlalchemy==2.0.*
psycopg2-binary==2.9.*
pydantic==2.*
python-dateutil==2.*
```

**Railway notes:**

* Service type: Docker
* Vars: `DATABASE_URL`, `BACKEND_API_KEY`, `TZ`
* One-time migration: `psql $DATABASE_URL -f db/init.sql`

---

## 16) OpenAPI (Autogen)

Add at `/docs` and `/openapi.json` via FastAPI default.
Ensure schemas reflect DTOs above for Codex to infer.

---

## 17) Acceptance Criteria (Definition of Done)

* [ ] `POST /simulators` creates/updates and returns simulator JSON.
* [ ] `POST /readings:ingest` accepts a batch, writes rows, updates block, returns `{accepted>0}`.
* [ ] 30-min block math correct for `Asia/Kuala_Lumpur` across day boundaries.
* [ ] `GET /blocks/latest` returns current window with 60 cumulative points.
* [ ] `GET /blocks/history?limit=10` returns last N windows with % of target.
* [ ] 80% threshold sets `alerted_80pct` once and emits SSE `alert-ready`.
* [ ] `GET /stream/:simulator_id` emits live events; heartbeat every 15s.
* [ ] API key enforced on write routes; healthcheck available.
* [ ] Railway deploy succeeds with env vars set; `db/init.sql` applied.

---

## 18) Future: MQTT Adapter (design only)

Add a small service (or module) later:

* Subscribe topic: `meters/<simulator_id>/reading`
* Payload (same as TickIn):

  ```json
  { "power_kw": 350.5, "sample_seconds": 15, "device_ts": "2025-10-29T06:35:00Z" }
  ```
* On message: call `ingest_ticks(sim_id, [tick])` — **no changes** to models, APIs, or UI.

---

## 19) Quick Start (for Codex)

1. Scaffold FastAPI app, connect SQLAlchemy to `DATABASE_URL`.
2. Implement models matching the SQL schema (or run `init.sql` and use SQLAlchemy mappings).
3. Implement DTOs and routers per contracts.
4. Implement `logic/ingest.py` with the exact steps in §13.
5. Implement SSE broadcaster with per-simulator async queues.
6. Wire alert-ready SSE payload when block hits 80% (no outbound messaging).
7. Add `/healthz`, enable `/docs`.
8. Dockerize and deploy on Railway.
9. Validate with sample simulator POSTs.

---

If you want, I can generate a **starter FastAPI repo** skeleton (folders, files, and stubbed endpoints) next so your team can just fill in the logic.
