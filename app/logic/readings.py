from __future__ import annotations

import asyncio
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Block30m, Reading, Simulator
from .ingest import _ensure_aware


def _quantize_energy(value: Decimal | float | int) -> Decimal:
    return Decimal(value).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


async def truncate_readings(simulator_id: UUID, cutoff_ts: datetime, session: Session) -> int:
    cutoff_utc = _ensure_aware(cutoff_ts)

    simulator: Simulator | None = session.get(Simulator, str(simulator_id))
    if simulator is None:
        raise HTTPException(status_code=404, detail="Simulator not found")

    readings = session.scalars(
        select(Reading)
        .where(
            Reading.simulator_id == str(simulator.id),
            Reading.ts_utc > cutoff_utc,
        )
        .order_by(Reading.ts_utc)
    ).all()

    deleted = len(readings)
    if deleted == 0:
        return 0

    affected_blocks = session.scalars(
        select(Block30m)
        .where(
            Block30m.simulator_id == str(simulator.id),
            Block30m.block_end_utc > cutoff_utc,
        )
        .order_by(Block30m.block_start_utc)
    ).all()

    for reading in readings:
        session.delete(reading)

    for block in affected_blocks:
        total_energy = session.scalar(
            select(func.coalesce(func.sum(Reading.energy_kwh), 0))
            .where(
                Reading.simulator_id == str(simulator.id),
                Reading.ts_utc >= block.block_start_utc,
                Reading.ts_utc < block.block_end_utc,
            )
        )
        accumulated = _quantize_energy(total_energy or Decimal("0"))
        block.accumulated_kwh = accumulated

        target = Decimal(block.target_kwh)
        percent = Decimal("0")
        if target > 0:
            percent = (accumulated / target) * Decimal(100)
        block.alerted_80pct = percent >= Decimal(80)

    await asyncio.to_thread(session.commit)
    return deleted
