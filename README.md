# Eternalgy EMS Backend

The Eternalgy EMS backend ingests simulated energy readings, aggregates them into fixed 30-minute blocks, and streams updates for the dashboard. When a block crosses **80%** of its target the backend marks it as alert-ready and emits an SSE event—the frontend decides what to do next (WhatsApp, email, etc.). Simulator profiles keep the WhatsApp number so the UI knows the right destination once the alert-ready arrives.

> **Heads up:** hitting the deployed base URL (e.g. `https://your-app.up.railway.app/`) now opens a live API guide with the exact payloads shown below. The Swagger UI is still available at `/docs` for interactive testing.

---

## ⚡ Quickstart – create your first simulator (no more 422s)

1. **Set your environment variables**
   ```bash
   export BASE_URL="https://<your-railway-host>"
   export BACKEND_API_KEY="<same value configured on the backend>"
   ```
2. **Send the request exactly like this**

   ```bash
   curl -X POST "$BASE_URL/api/v1/simulators" \
     -H "content-type: application/json" \
     -H "x-api-key: $BACKEND_API_KEY" \
    -d '{
      "name": "Factory A",
      "targetKwh": 120,
      "whatsappNumber": 60123456789
    }'
   ```

   - The JSON body **must** be valid JSON (double quotes, numbers without quotes).
   - `targetKwh` is a number (e.g., `120` or `120.0`).
   - Leave out `whatsappNumber` or set it to `null` if you do not want to store one yet.
   - The WhatsApp number must contain digits only (no `+` sign, spaces, or hyphens).

3. **Expected 200 OK response**

   ```json
   {
     "id": "c7d7c9ad-33ce-42a8-8f7d-3aaf1c6de123",
     "name": "Factory A",
     "target_kwh": 120.0,
     "whatsapp_number": 60123456789,
     "created_at": "2024-05-02T06:00:00Z",
     "updated_at": "2024-05-02T06:00:00Z"
   }
   ```

### Request payload schema (accepted aliases included)

| column name         | type      | required? | accepted aliases                                      | example            |
| ------------------- | --------- | --------- | ----------------------------------------------------- | ------------------ |
| `name`              | string    | yes       | `name`, `simulator_name`, `simulatorName`             | `"Factory A"`      |
| `target_kwh`        | number ≥0 | yes       | `target_kwh`, `targetKwh`, `target_kWh`, `targetKWhr` | `120.0`            |
| `whatsapp_number`   | integer   | no        | `whatsapp_number`, `whatsappNumber`, `whatsapp_no`, `whatsappNo` | `60123456789`     |

> **Getting 422?** Double-check the JSON structure, header names, and that the API key header is present. Missing fields, spelling mistakes, or non-numeric strings (`"120 kWh"`) will trigger validation errors. The aliases above match what the backend accepts.

---

## API reference (frontend cheatsheet)

All write endpoints require `x-api-key: <BACKEND_API_KEY>`. Read-only endpoints (history, latest block, SSE, health) do not.

### Summary table

| Method & Path                     | Description                                   | Auth? |
| --------------------------------- | --------------------------------------------- | ----- |
| `POST /api/v1/simulators`         | Create or update a simulator profile          | ✅    |
| `GET /api/v1/simulators`          | List simulator profiles                       | ❌    |
| `POST /api/v1/readings:ingest`    | Bulk-ingest power readings                    | ✅    |
| `GET /api/v1/blocks/latest`       | Latest 30-minute block for a simulator        | ❌    |
| `GET /api/v1/blocks/history`      | Historical block summaries (limit param)      | ❌    |
| `GET /api/v1/stream/:simulatorId` | Live SSE stream (readings, block, alert-ready) | ❌    |
| `GET /healthz`                    | Health probe                                  | ❌    |

### Simulator APIs

#### `POST /api/v1/simulators`
- Request body: see table above.
- Returns the stored simulator (fields: `id`, `name`, `target_kwh`, `whatsapp_number`, `created_at`, `updated_at`).

#### `GET /api/v1/simulators`
- Response body: array of simulator objects with the same fields as above.

### Readings ingestion

#### `POST /api/v1/readings:ingest`
```json
{
  "simulator_id": "c7d7c9ad-33ce-42a8-8f7d-3aaf1c6de123",
  "mode": "auto",
  "ticks": [
    { "power_kw": 350.5, "sample_seconds": 15, "device_ts": "2024-05-02T08:00:15Z" },
    { "power_kw": 355.2, "sample_seconds": 15, "device_ts": "2024-05-02T08:00:30Z" }
  ]
}
```
- Aliases accepted: `simulatorId`, `powerKw`, `sampleSeconds`, `deviceTs`.
- Response: `{ "accepted": 2, "sse_emitted": true }`.

### Blocks

#### `GET /api/v1/blocks/latest?simulator_id=<UUID>`
```json
{
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
    "points": [ /* cumulative values for the window */ ]
  }
}
```

#### `GET /api/v1/blocks/history?simulator_id=<UUID>&limit=10`
```json
[
  {
    "block_start_local": "2024-05-02T13:30:00+08:00",
    "target_kwh": 120.0,
    "accumulated_kwh": 101.2,
    "percent_of_target": 84.33
  }
]
```

### Server-Sent Events

#### `GET /api/v1/stream/:simulator_id`
Emits events like:
```json
{ "type": "reading", "ts": "2024-05-02T06:00:30Z" }
{ "type": "block-update", "accumulated_kwh": 96.5, "percent_of_target": 80.4 }
{
  "type": "alert-ready",
  "simulator_id": "c7d7c9ad-33ce-42a8-8f7d-3aaf1c6de123",
  "block_start_utc": "2024-05-02T06:00:00Z",
  "block_window_label": "14:00–14:30 (local KL)",
  "target_kwh": 120.0,
  "accumulated_kwh": 96.5,
  "percent_of_target": 80.42
}
```

---

## Detailed project spec (for backend contributors)

### Purpose
- Ingest simulated energy readings.
- Aggregate readings into 30-minute KL time blocks.
- Flip `alerted_80pct` and emit `alert-ready` SSE when usage crosses 80% of target.
- Persist simulator profiles (with optional WhatsApp numbers) so the frontend knows who to notify.

### Architecture
```
Simulator (Frontend) --REST--> Backend /readings:ingest --> Postgres
                                                  |--> 30-min block upsert & accumulate
                                                  |--> 80% threshold flip → mark alert-ready
                                                  |--> SSE push to /stream/:sim_id

Dashboard (Frontend) <--REST/SSE-- Backend <---> Postgres
```
- REST for write/read; SSE for live UI updates.
- Store raw power readings and compute energy on insert.
- All timestamps stored as UTC; block boundaries follow `Asia/Kuala_Lumpur`.

### Environment
- `DATABASE_URL` (required)
- `BACKEND_API_KEY` (required for writes)
- `TZ=Asia/Kuala_Lumpur`
- Optional: `PORT`, `LOG_LEVEL`

### Database schema (`db/init.sql`)
```sql
create extension if not exists pgcrypto;
create extension if not exists uuid-ossp;

create table if not exists simulators (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  target_kwh numeric(12,4) not null check (target_kwh >= 0),
  whatsapp_number bigint,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists readings (
  id bigserial primary key,
  simulator_id uuid not null references simulators(id) on delete cascade,
  ts_utc timestamptz not null default now(),
  device_ts timestamptz,
  power_kw numeric(12,4) not null check (power_kw >= 0),
  sample_seconds int not null check (sample_seconds > 0),
  energy_kwh numeric(12,6) generated always as (power_kw * sample_seconds / 3600.0) stored
);
create index if not exists idx_readings_sim_ts on readings (simulator_id, ts_utc);

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

### Core logic highlights
- Block windows: 30-minute buckets starting midnight KL. Use device timestamp when provided.
- Accumulation: generated column calculates `energy_kwh`. Each ingest updates the relevant block row and chart bins.
- Threshold: if `accumulated_kwh >= 0.8 * target_kwh` and `alerted_80pct` is false → set it true and emit one `alert-ready` SSE.
- Idempotency: duplicate ticks accumulate; optional client tick IDs can be added later if needed.

### SSE contract
- Endpoint: `GET /api/v1/stream/:simulator_id`
- Headers: `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `Connection: keep-alive`
- Emit: `reading`, `block-update`, and `alert-ready` events (plus heartbeat `ping` every 15s).

### Security & observability
- FastAPI dependency enforces `x-api-key` on write routes.
- Health check: `GET /healthz` → `{ "ok": true }`.
- Structured logs recommended: include simulator ID, tick count, block info, and alert status.

### Deployment notes
- Dockerfile + `start.sh` run the FastAPI app with Uvicorn.
- Designed for Railway: pushing to GitHub triggers redeploy, DB URL provided via environment.
- Keep prototype simple—no background queues or messaging integrations.

---

## Need help?
- Still seeing validation errors? Grab the exact JSON you send, compare it with the tables above, and confirm the header names.
- The Swagger UI lives at the service root (`/`). It mirrors the contracts above and lets you try requests interactively.
- Questions? Reach out with the request payload and response body so we can debug together.
