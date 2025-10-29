from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    conint,
    confloat,
    field_validator,
)


def _coerce_whatsapp_number(value: Optional[object]) -> Optional[int]:
    """Normalize WhatsApp numbers while tolerating legacy formatting."""

    if value is None:
        return None

    if isinstance(value, bool):  # bool is a subclass of int but we do not want True/False
        raise TypeError("whatsapp_number must be a digits-only string or integer")

    if isinstance(value, Decimal):
        value = int(value)

    if isinstance(value, int):
        if value <= 0:
            raise ValueError("whatsapp_number must be a positive integer")
        return value

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None

        digits_only = "".join(ch for ch in stripped if ch.isdigit())

        if not digits_only:
            raise ValueError("whatsapp_number must contain at least one digit")

        number = int(digits_only)
        if number <= 0:
            raise ValueError("whatsapp_number must be a positive integer")
        return number

    raise TypeError("whatsapp_number must be a digits-only string or integer")


class SimulatorBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(
        ...,
        example="Factory A",
        validation_alias=AliasChoices("name", "simulator_name", "simulatorName"),
        description="Human-friendly simulator label shown in the dashboard.",
    )
    target_kwh: confloat(ge=0) = Field(
        ...,
        example=120.0,
        validation_alias=AliasChoices(
            "target_kwh",
            "targetKwh",
            "target_kWh",
            "targetKWhr",
        ),
        description="Target energy consumption in kWh for the 30-minute window.",
    )
    whatsapp_number: Optional[conint(gt=0)] = Field(
        default=None,
        example=60123456789,
        validation_alias=AliasChoices(
            "whatsapp_number",
            "whatsappNumber",
            "whatsapp_no",
            "whatsappNo",
        ),
        description="Digits-only WhatsApp number the frontend will message when an alert-ready event is received (e.g. 60123456789).",
    )

    @field_validator("whatsapp_number", mode="before")
    @classmethod
    def _normalize_whatsapp(cls, value: Optional[object]) -> Optional[int]:
        return _coerce_whatsapp_number(value)


class SimulatorCreate(SimulatorBase):
    pass


class SimulatorOut(BaseModel):
    id: UUID
    name: str
    target_kwh: float
    whatsapp_number: Optional[int]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("whatsapp_number", mode="before")
    @classmethod
    def _normalize_whatsapp(cls, value: Optional[object]) -> Optional[int]:
        return _coerce_whatsapp_number(value)


class SimulatorResponse(BaseModel):
    data: SimulatorOut


class SimulatorListResponse(BaseModel):
    data: List[SimulatorOut]


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


class BlockHistoryResponse(BaseModel):
    data: List[BlockHistoryItem]
