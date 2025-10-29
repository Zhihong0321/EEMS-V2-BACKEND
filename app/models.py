from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Simulator(Base):
    __tablename__ = "simulators"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    target_kwh: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    readings: Mapped[list["Reading"]] = relationship(back_populates="simulator")
    blocks: Mapped[list["Block30m"]] = relationship(back_populates="simulator")


class Reading(Base):
    __tablename__ = "readings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    simulator_id: Mapped[str] = mapped_column(ForeignKey("simulators.id", ondelete="CASCADE"), nullable=False)
    ts_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    device_ts: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    power_kw: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    sample_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    energy_kwh: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False)

    simulator: Mapped[Simulator] = relationship(back_populates="readings")

    __table_args__ = (
        CheckConstraint("power_kw >= 0", name="check_power_non_negative"),
        CheckConstraint("sample_seconds > 0", name="check_sample_seconds_positive"),
    )


class Block30m(Base):
    __tablename__ = "blocks_30m"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    simulator_id: Mapped[str] = mapped_column(ForeignKey("simulators.id", ondelete="CASCADE"), nullable=False)
    block_start_local: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    block_start_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    block_end_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    target_kwh: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    accumulated_kwh: Mapped[float] = mapped_column(Numeric(14, 6), nullable=False, default=0)
    alerted_80pct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    simulator: Mapped[Simulator] = relationship(back_populates="blocks")

    __table_args__ = (
        UniqueConstraint("simulator_id", "block_start_utc", name="uq_blocks_sim_start"),
    )
