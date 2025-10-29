from __future__ import annotations

import re
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import get_db, require_api_key
from ..models import Simulator
from ..schema import SimulatorCreate, SimulatorOut

router = APIRouter(prefix="/api/v1/simulators", tags=["simulators"])

_MSISDN_RE = re.compile(r"^\+?[1-9]\d{6,14}$")


def _normalize_msisdn(msisdn: str | None) -> str | None:
    if msisdn is None:
        return None
    candidate = msisdn.strip()
    if not _MSISDN_RE.match(candidate):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid WhatsApp MSISDN")
    if not candidate.startswith("+"):
        candidate = "+" + candidate
    return candidate


@router.post("", response_model=SimulatorOut, dependencies=[Depends(require_api_key)])
def create_or_update_simulator(payload: SimulatorCreate, db: Session = Depends(get_db)) -> SimulatorOut:
    msisdn = _normalize_msisdn(payload.whatsapp_msisdn) if payload.whatsapp_msisdn else None
    existing = db.scalar(select(Simulator).where(Simulator.name == payload.name))

    if existing:
        existing.target_kwh = payload.target_kwh
        existing.whatsapp_msisdn = msisdn
        db.flush()
        simulator = existing
    else:
        simulator = Simulator(
            name=payload.name,
            target_kwh=payload.target_kwh,
            whatsapp_msisdn=msisdn,
        )
        db.add(simulator)
        db.flush()

    db.refresh(simulator)
    return SimulatorOut.model_validate(simulator)


@router.get("", response_model=List[SimulatorOut])
def list_simulators(db: Session = Depends(get_db)) -> List[SimulatorOut]:
    simulators = db.scalars(select(Simulator).order_by(Simulator.created_at)).all()
    return [SimulatorOut.model_validate(sim) for sim in simulators]
