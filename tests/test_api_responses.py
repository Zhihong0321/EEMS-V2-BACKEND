from __future__ import annotations

import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from starlette.requests import Request

from app.logic.blocks import get_block_history
from app.main import handle_unexpected_exception
from app.models import Base, Simulator
from app.routers.simulators import list_simulators
from app.schema import (
    BlockHistoryResponse,
    SimulatorCreate,
    SimulatorListResponse,
    SimulatorOut,
)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
    )
    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        future=True,
        expire_on_commit=False,
    )
    Base.metadata.create_all(bind=engine)
    session: Session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_list_simulators_returns_enveloped_payload(db_session: Session) -> None:
    db_session.add(
        Simulator(
            name="Factory A",
            target_kwh=120.0,
            whatsapp_number=60123456789,
        )
    )
    db_session.commit()

    response = list_simulators(db=db_session)

    assert isinstance(response, SimulatorListResponse)
    assert len(response.data) == 1
    assert response.data[0].name == "Factory A"


def test_list_simulators_empty_array(db_session: Session) -> None:
    response = list_simulators(db=db_session)

    assert isinstance(response, SimulatorListResponse)
    assert response.data == []


def test_block_history_returns_enveloped_payload(db_session: Session) -> None:
    response = get_block_history(db_session, uuid.uuid4(), limit=5)

    assert isinstance(response, BlockHistoryResponse)
    assert response.data == []


def test_internal_error_is_returned_as_json() -> None:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/boom",
        "headers": [],
    }
    request = Request(scope)

    response = asyncio.run(handle_unexpected_exception(request, RuntimeError("boom")))

    assert response.status_code == 500
    assert response.headers["content-type"] == "application/json"
    assert json.loads(response.body.decode()) == {"detail": "Internal Server Error"}


def test_simulator_create_normalizes_whatsapp_aliases() -> None:
    payload = SimulatorCreate(
        name="Factory B",
        targetKwh=90,
        whatsappNumber=" +60 12-345 6789 ",
    )

    assert payload.whatsapp_number == 60123456789


def test_simulator_out_handles_legacy_string_numbers() -> None:
    class LegacySimulator:
        def __init__(self) -> None:
            self.id = uuid.uuid4()
            self.name = "Factory Legacy"
            self.target_kwh = 150.0
            self.whatsapp_number = "+60 12 345 6789"
            now = datetime.now(timezone.utc)
            self.created_at = now
            self.updated_at = now

    result = SimulatorOut.model_validate(LegacySimulator())

    assert result.whatsapp_number == 60123456789
