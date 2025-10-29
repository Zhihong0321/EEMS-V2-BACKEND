from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_db, require_api_key
from ..logic.ingest import ingest_ticks
from ..schema import IngestIn, IngestOut

router = APIRouter(prefix="/api/v1", tags=["readings"])


@router.post("/readings:ingest", response_model=IngestOut, dependencies=[Depends(require_api_key)])
async def ingest_readings(payload: IngestIn, db: Session = Depends(get_db)) -> IngestOut:
    accepted = await ingest_ticks(payload.simulator_id, payload.ticks, db)
    return IngestOut(accepted=accepted, sse_emitted=accepted > 0)
