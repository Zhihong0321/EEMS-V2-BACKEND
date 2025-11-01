from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import get_db, require_api_key
from ..models import Simulator
from ..schema import SimulatorCreate, SimulatorOut

router = APIRouter(prefix="/api/v1/simulators", tags=["simulators"])

@router.post(
    "",
    response_model=SimulatorOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_api_key)],
)
def create_or_update_simulator(payload: SimulatorCreate, db: Session = Depends(get_db)) -> SimulatorOut:
    existing = db.scalar(select(Simulator).where(Simulator.name == payload.name))

    if existing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Simulator with name '{payload.name}' already exists.",
        )

    simulator = Simulator(
        name=payload.name,
        target_kwh=payload.target_kwh,
        whatsapp_number=payload.whatsapp_number,
    )
    db.add(simulator)
    db.flush()

    db.refresh(simulator)
    return SimulatorOut.model_validate(simulator)


@router.get("", response_model=List[SimulatorOut])
def list_simulators(db: Session = Depends(get_db)) -> List[SimulatorOut]:
    simulators = db.scalars(select(Simulator).order_by(Simulator.created_at)).all()
    return [SimulatorOut.model_validate(sim) for sim in simulators]


@router.delete(
    "/{simulator_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_api_key)],
)
def delete_simulator(simulator_id: UUID, db: Session = Depends(get_db)) -> None:
    simulator = db.get(Simulator, str(simulator_id))
    if simulator is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Simulator with id '{simulator_id}' not found.",
        )

    db.delete(simulator)
