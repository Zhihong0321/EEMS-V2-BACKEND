from __future__ import annotations

from decimal import Decimal
from typing import List
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from ..config import get_settings
from ..models import Block30m, Reading
from ..schema import (
    BlockHistoryItem,
    BlockHistoryResponse,
    ChartBins,
    LatestBlockOut,
)
from .ingest import _ensure_aware


def _percent(accumulated: Decimal, target: Decimal) -> float:
    if target == 0:
        return 0.0
    return float((accumulated / target) * Decimal(100))


def _chart_bins(session: Session, simulator_id: str, block: Block30m, tz: ZoneInfo) -> ChartBins:
    bin_size_seconds = 30
    total_bins = int((block.block_end_utc - block.block_start_utc).total_seconds() / bin_size_seconds)
    bin_values = [0.0 for _ in range(total_bins)]

    readings = session.scalars(
        select(Reading)
        .where(
            Reading.simulator_id == simulator_id,
            Reading.ts_utc >= block.block_start_utc,
            Reading.ts_utc < block.block_end_utc,
        )
        .order_by(Reading.ts_utc)
    ).all()

    for reading in readings:
        reading_time = reading.device_ts or reading.ts_utc
        reading_time = _ensure_aware(reading_time)
        local_ts = reading_time.astimezone(tz)
        delta = local_ts - block.block_start_local
        seconds = delta.total_seconds()
        if seconds < 0:
            continue
        index = int(seconds // bin_size_seconds)
        if 0 <= index < total_bins:
            bin_values[index] += float(reading.energy_kwh)

    cumulative = 0.0
    points: List[float] = []
    for value in bin_values:
        cumulative += value
        points.append(round(cumulative, 6))

    if len(points) < total_bins:
        points.extend([round(cumulative, 6)] * (total_bins - len(points)))

    return ChartBins(bin_seconds=bin_size_seconds, points=points)


def get_latest_block(session: Session, simulator_id: UUID) -> LatestBlockOut:
    block = session.scalar(
        select(Block30m)
        .where(Block30m.simulator_id == str(simulator_id))
        .order_by(desc(Block30m.block_start_utc))
    )
    if block is None:
        raise HTTPException(status_code=404, detail="No blocks for simulator")

    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    chart_bins = _chart_bins(session, str(simulator_id), block, tz)

    percent = _percent(Decimal(block.accumulated_kwh), Decimal(block.target_kwh))

    return LatestBlockOut(
        simulator_id=UUID(block.simulator_id),
        block_start_local=block.block_start_local,
        block_start_utc=block.block_start_utc,
        block_end_utc=block.block_end_utc,
        target_kwh=float(block.target_kwh),
        accumulated_kwh=float(block.accumulated_kwh),
        percent_of_target=percent,
        alerted_80pct=block.alerted_80pct,
        chart_bins=chart_bins,
    )


def get_block_history(
    session: Session, simulator_id: UUID, limit: int = 10
) -> BlockHistoryResponse:
    blocks = session.scalars(
        select(Block30m)
        .where(Block30m.simulator_id == str(simulator_id))
        .order_by(desc(Block30m.block_start_utc))
        .limit(limit)
    ).all()

    items: List[BlockHistoryItem] = []
    for block in blocks:
        percent = _percent(Decimal(block.accumulated_kwh), Decimal(block.target_kwh))
        items.append(
            BlockHistoryItem(
                block_start_local=block.block_start_local,
                target_kwh=float(block.target_kwh),
                accumulated_kwh=float(block.accumulated_kwh),
                percent_of_target=percent,
            )
        )

    return BlockHistoryResponse(data=items)
