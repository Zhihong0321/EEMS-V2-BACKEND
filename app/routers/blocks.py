from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..deps import get_db
from ..logic.blocks import get_block_history, get_latest_block
from ..schema import BlockHistoryResponse, LatestBlockOut

router = APIRouter(prefix="/api/v1/blocks", tags=["blocks"])


@router.get("/latest", response_model=LatestBlockOut)
def latest_block(simulator_id: UUID = Query(...), db: Session = Depends(get_db)) -> LatestBlockOut:
    return get_latest_block(db, simulator_id)


@router.get("/history", response_model=BlockHistoryResponse)
def block_history(
    simulator_id: UUID = Query(...),
    limit: int = Query(10, ge=1, le=96),
    db: Session = Depends(get_db),
) -> BlockHistoryResponse:
    return get_block_history(db, simulator_id, limit=limit)
