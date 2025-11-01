"""Lightweight, idempotent schema fixes applied during startup."""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def apply_startup_migrations(engine: Engine) -> None:
    """Apply tiny in-code migrations required by the current models.

    The production database was created before ``Simulator.whatsapp_number`` existed,
    so every ``SELECT``/``INSERT`` referencing the column crashes with
    ``column simulators.whatsapp_number does not exist``.  Because the project does
    not ship Alembic migrations yet, we run the minimal ALTER TABLE here to keep the
    live schema aligned with the ORM models.  The inspection guard keeps the call
    idempotent across restarts.
    """

    with engine.begin() as conn:
        inspector = inspect(conn)

        if "simulators" not in inspector.get_table_names():
            # ``Base.metadata.create_all`` will create the table if missing; nothing
            # else to do here.
            return

        existing_columns = {col["name"] for col in inspector.get_columns("simulators")}

        if "whatsapp_number" not in existing_columns:
            if engine.dialect.name == "postgresql":
                conn.execute(
                    text(
                        "ALTER TABLE simulators ADD COLUMN IF NOT EXISTS whatsapp_number BIGINT"
                    )
                )
            else:
                # SQLite (used locally) does not understand ``IF NOT EXISTS`` for
                # columns, but the explicit inspection above keeps the ALTER safe.
                conn.execute(text("ALTER TABLE simulators ADD COLUMN whatsapp_number BIGINT"))
