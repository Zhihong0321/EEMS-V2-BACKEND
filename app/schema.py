from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, conint, confloat


class SimulatorCreate(BaseModel):
    name: str
    target_kwh: confloat(ge=0)
    whatsapp_msisdn: Optional[str] = None


class SimulatorOut(SimulatorCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TickIn(BaseModel):
    power_kw: confloat(ge=0)
    sample_seconds: conint(gt=0)
    device_ts: Optional[datetime] = None


class IngestIn(BaseModel):
    simulator_id: UUID
    mode: Optional[str] = Field(default=None, pattern=r"^(auto|manual)?$")
    ticks: List[TickIn]


class IngestOut(BaseModel):
    accepted: int
    sse_emitted: bool


class ChartBins(BaseModel):
    bin_seconds: int
    points: List[float]


class LatestBlockOut(BaseModel):
    simulator_id: UUID
    block_start_local: datetime
    block_start_utc: datetime
    block_end_utc: datetime
    target_kwh: float
    accumulated_kwh: float
    percent_of_target: float
    alerted_80pct: bool
    chart_bins: ChartBins


class BlockHistoryItem(BaseModel):
    block_start_local: datetime
    target_kwh: float
    accumulated_kwh: float
    percent_of_target: float


class BlockHistoryOut(BaseModel):
    items: List[BlockHistoryItem]
