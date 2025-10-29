create extension if not exists pgcrypto;
create extension if not exists "uuid-ossp";

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

