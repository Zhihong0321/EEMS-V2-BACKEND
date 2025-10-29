from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from ..config import get_settings
from ..models import Block30m, Reading, Simulator
from ..schema import TickIn
from .sse import sse_manager


def _ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _decimal(value: float | Decimal, places: str = "0.000000") -> Decimal:
    return Decimal(str(value)).quantize(Decimal(places), rounding=ROUND_HALF_UP)


def _compute_block_windows(local_ts: datetime):
    floor_hour = local_ts.replace(minute=0, second=0, microsecond=0)
    half = 0 if local_ts.minute < 30 else 1
    block_start_local = floor_hour + timedelta(minutes=30 * half)
    block_start_utc = block_start_local.astimezone(timezone.utc)
    block_end_utc = block_start_utc + timedelta(minutes=30)
    return block_start_local, block_start_utc, block_end_utc


async def ingest_ticks(simulator_id: UUID, ticks: Iterable[TickIn], session: Session) -> int:
    tick_list = list(ticks)
    if not tick_list:
        return 0

    simulator: Simulator | None = session.get(Simulator, str(simulator_id))
    if simulator is None:
        raise HTTPException(status_code=404, detail="Simulator not found")

    settings = get_settings()
    tz = ZoneInfo(settings.timezone)

    accepted = 0

    for tick in tick_list:
        reading_time = tick.device_ts or datetime.now(timezone.utc)
        reading_time = _ensure_aware(reading_time)
        local_ts = reading_time.astimezone(tz)
        block_start_local, block_start_utc, block_end_utc = _compute_block_windows(local_ts)

        power_kw_decimal = _decimal(tick.power_kw, "0.0001")
        energy = (power_kw_decimal * Decimal(int(tick.sample_seconds)) / Decimal("3600")).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )

        reading = Reading(
            simulator_id=str(simulator.id),
            ts_utc=reading_time,
            device_ts=tick.device_ts,
            power_kw=power_kw_decimal,
            sample_seconds=int(tick.sample_seconds),
            energy_kwh=energy,
        )
        session.add(reading)
        session.flush()

        block = session.scalar(
            select(Block30m).where(
                Block30m.simulator_id == str(simulator.id),
                Block30m.block_start_utc == block_start_utc,
            )
        )
        if block is None:
            block = Block30m(
                simulator_id=str(simulator.id),
                block_start_local=block_start_local,
                block_start_utc=block_start_utc,
                block_end_utc=block_end_utc,
                target_kwh=_decimal(simulator.target_kwh, "0.0001"),
                accumulated_kwh=Decimal("0"),
            )
            session.add(block)
            session.flush()

        block.accumulated_kwh = (Decimal(block.accumulated_kwh) + energy).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
        session.flush()

        percent = 0.0
        target_decimal = Decimal(block.target_kwh)
        if target_decimal > 0:
            percent = float((Decimal(block.accumulated_kwh) / target_decimal) * Decimal(100))

        await sse_manager.publish(
            simulator.id,
            "reading",
            {"ts": reading_time.isoformat()},
        )
        await sse_manager.publish(
            simulator.id,
            "block-update",
            {
                "accumulated_kwh": float(block.accumulated_kwh),
                "percent_of_target": percent,
            },
        )

        if not block.alerted_80pct and target_decimal > 0 and percent >= 80:
            block.alerted_80pct = True
            session.flush()

            block_start_local = block.block_start_local.astimezone(tz)
            block_end_local = block.block_end_utc.astimezone(tz)
            timezone_label = "local KL" if settings.timezone == "Asia/Kuala_Lumpur" else f"local {settings.timezone}"
            block_window_label = f"{block_start_local.strftime('%H:%M')}–{block_end_local.strftime('%H:%M')} ({timezone_label})"
            percent_of_target = float((Decimal(block.accumulated_kwh) / target_decimal) * Decimal(100))
            percent_of_target = round(percent_of_target, 2)

            await sse_manager.publish(
                simulator.id,
                "alert-ready",
                {
                    "type": "alert-ready",
                    "simulator_id": str(simulator.id),
                    "block_start_utc": block.block_start_utc.isoformat(),
                    "block_window_label": block_window_label,
                    "target_kwh": float(block.target_kwh),
                    "accumulated_kwh": float(block.accumulated_kwh),
                    "percent_of_target": percent_of_target,
                },
            )

        accepted += 1

    await asyncio.to_thread(session.commit)
    return accepted
