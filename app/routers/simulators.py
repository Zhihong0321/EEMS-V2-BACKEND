from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import get_db, require_api_key
from ..models import Simulator
from ..schema import SimulatorCreate, SimulatorOut

router = APIRouter(prefix="/api/v1/simulators", tags=["simulators"])

@router.post("", response_model=SimulatorOut, dependencies=[Depends(require_api_key)])
def create_or_update_simulator(payload: SimulatorCreate, db: Session = Depends(get_db)) -> SimulatorOut:
    existing = db.scalar(select(Simulator).where(Simulator.name == payload.name))

    if existing:
        existing.target_kwh = payload.target_kwh
        db.flush()
        simulator = existing
    else:
        simulator = Simulator(
            name=payload.name,
            target_kwh=payload.target_kwh,
        )
        db.add(simulator)
        db.flush()

    db.refresh(simulator)
    return SimulatorOut.model_validate(simulator)


@router.get("", response_model=List[SimulatorOut])
def list_simulators(db: Session = Depends(get_db)) -> List[SimulatorOut]:
    simulators = db.scalars(select(Simulator).order_by(Simulator.created_at)).all()
    return [SimulatorOut.model_validate(sim) for sim in simulators]
