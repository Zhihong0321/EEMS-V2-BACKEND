from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, conint, confloat


class SimulatorCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., example="Factory A")
    target_kwh: confloat(ge=0) = Field(
        ...,
        example=120.0,
        validation_alias=AliasChoices("target_kwh", "targetKwh"),
        description="Target energy consumption in kWh for the 30-minute window.",
    )


class SimulatorOut(SimulatorCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TickIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    power_kw: confloat(ge=0) = Field(
        ...,
        example=350.5,
        validation_alias=AliasChoices("power_kw", "powerKw"),
        description="Instantaneous power level in kW for this tick.",
    )
    sample_seconds: conint(gt=0) = Field(
        ...,
        example=15,
        validation_alias=AliasChoices("sample_seconds", "sampleSeconds"),
        description="Duration in seconds that the power reading applies to.",
    )
    device_ts: Optional[datetime] = Field(
        default=None,
        example="2024-05-01T08:00:15Z",
        validation_alias=AliasChoices("device_ts", "deviceTs"),
        description="Optional timestamp captured by the simulator.",
    )


class IngestIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    simulator_id: UUID = Field(
        ...,
        validation_alias=AliasChoices("simulator_id", "simulatorId"),
        example="c7d7c9ad-33ce-42a8-8f7d-3aaf1c6de123",
    )
    mode: Optional[str] = Field(default=None, pattern=r"^(auto|manual)?$", example="auto")
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
