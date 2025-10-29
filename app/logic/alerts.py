from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Tuple

import httpx

from ..config import get_settings
from ..models import Alert, Block30m, Simulator


async def send_80pct_alert(simulator: Simulator, block: Block30m, percent: float, session) -> Tuple[bool, Alert]:
    settings = get_settings()
    if not simulator.whatsapp_msisdn:
        alert = Alert(
            simulator_id=simulator.id,
            block_start_utc=block.block_start_utc,
            threshold="80pct",
            destination="",
            status="skipped",
            response_code=None,
            response_body="No WhatsApp MSISDN configured",
        )
        session.add(alert)
        await _flush_in_thread(session)
        return False, alert

    if not settings.whatsapp_api_base or not settings.whatsapp_api_token:
        alert = Alert(
            simulator_id=simulator.id,
            block_start_utc=block.block_start_utc,
            threshold="80pct",
            destination=simulator.whatsapp_msisdn,
            status="skipped",
            response_code=None,
            response_body="WhatsApp API not configured",
        )
        session.add(alert)
        await _flush_in_thread(session)
        return False, alert

    window_end_local = block.block_start_local + (block.block_end_utc - block.block_start_utc)
    message = (
        "[Eternalgy EMS]\n"
        f"Simulator: {simulator.name}\n"
        f"Window: {block.block_start_local.strftime('%H:%M')}–{window_end_local.strftime('%H:%M')}\n"
        f"Target: {float(block.target_kwh)} kWh\n"
        f"Current: {float(block.accumulated_kwh)} kWh ({percent:.1f}%)\n"
        "Status: Reached 80% threshold."
    )
    payload = {
        "to": simulator.whatsapp_msisdn,
        "type": "text",
        "text": {"body": message},
    }

    url = f"{settings.whatsapp_api_base.rstrip('/')}/messages"
    headers = {
        "Authorization": f"Bearer {settings.whatsapp_api_token}",
        "Content-Type": "application/json",
    }

    status_text = "failed"
    response_code = None
    response_body = None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
        response_code = response.status_code
        response_body = response.text
        status_text = "sent" if response.is_success else "failed"
    except httpx.HTTPError as exc:  # pragma: no cover - network failure path
        response_body = str(exc)
        status_text = "failed"

    alert = Alert(
        simulator_id=simulator.id,
        block_start_utc=block.block_start_utc,
        threshold="80pct",
        destination=simulator.whatsapp_msisdn,
        status=status_text,
        response_code=response_code,
        response_body=response_body,
        sent_at=datetime.now(timezone.utc),
    )
    session.add(alert)
    await _flush_in_thread(session)
    return status_text == "sent", alert


async def _flush_in_thread(session) -> None:
    await asyncio.to_thread(session.flush)
