from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from .config import get_settings
from .db import engine
from .models import Base
from .routers import blocks, readings, simulators, stream

settings = get_settings()

logging.basicConfig(level=settings.log_level.upper())

app = FastAPI(title="Eternalgy EMS Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/", include_in_schema=False)
async def root_docs_redirect() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/healthz")
def healthcheck() -> dict[str, bool]:
    return {"ok": True}


app.include_router(simulators.router)
app.include_router(readings.router)
app.include_router(blocks.router)
app.include_router(stream.router)
