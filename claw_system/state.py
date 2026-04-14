import json
from datetime import datetime
from pathlib import Path

import aiosqlite
import structlog

from claw_system.models import PipelineState, PipelineStatus

logger = structlog.get_logger(__name__)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS pipeline_states (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    collector_output TEXT,
    analyst_output TEXT,
    fig_output TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _state_to_row(state: PipelineState) -> dict:
    status_val = state.status.value if isinstance(state.status, PipelineStatus) else state.status
    return {
        "id": state.id,
        "url": state.url,
        "status": status_val,
        "collector_output": json.dumps(state.collector_output) if state.collector_output else None,
        "analyst_output": json.dumps(state.analyst_output) if state.analyst_output else None,
        "fig_output": json.dumps(state.fig_output) if state.fig_output else None,
        "error_message": state.error_message,
        "created_at": state.created_at.isoformat(),
        "updated_at": state.updated_at.isoformat(),
    }


def _row_to_state(row: dict) -> PipelineState:
    return PipelineState(
        id=row["id"],
        url=row["url"],
        status=PipelineStatus(row["status"]),
        collector_output=json.loads(row["collector_output"]) if row["collector_output"] else None,
        analyst_output=json.loads(row["analyst_output"]) if row["analyst_output"] else None,
        fig_output=json.loads(row["fig_output"]) if row["fig_output"] else None,
        error_message=row["error_message"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


class StateStore:
    def __init__(self, db_path: Path | str = "claw_pipeline.db") -> None:
        self._db_path = str(db_path)
        self._db: aiosqlite.Connection | None = None

    async def _get_db(self) -> aiosqlite.Connection:
        if self._db is None:
            self._db = await aiosqlite.connect(self._db_path)
            self._db.row_factory = aiosqlite.Row
            await self._db.execute(_CREATE_TABLE_SQL)
            await self._db.commit()
            logger.info("state_store_initialized", db_path=self._db_path)
        return self._db

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None
            logger.info("state_store_closed")

    async def create(self, url: str) -> PipelineState:
        state = PipelineState(url=url)
        db = await self._get_db()
        row = _state_to_row(state)
        columns = ", ".join(row.keys())
        placeholders = ", ".join("?" for _ in row)
        values = list(row.values())
        await db.execute(
            f"INSERT INTO pipeline_states ({columns}) VALUES ({placeholders})",
            values,
        )
        await db.commit()
        logger.info("pipeline_created", pipeline_id=state.id, url=url)
        return state

    async def get(self, pipeline_id: str) -> PipelineState | None:
        db = await self._get_db()
        cursor = await db.execute(
            "SELECT * FROM pipeline_states WHERE id = ?", (pipeline_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return _row_to_state(dict(row))

    async def update(self, pipeline_id: str, **kwargs) -> PipelineState | None:
        state = await self.get(pipeline_id)
        if state is None:
            return None

        if "status" in kwargs and isinstance(kwargs["status"], str):
            kwargs["status"] = PipelineStatus(kwargs["status"])

        for key, value in kwargs.items():
            if hasattr(state, key):
                setattr(state, key, value)
        state.touch()

        row = _state_to_row(state)
        set_clause = ", ".join(f"{k} = ?" for k in row.keys() if k != "id")
        values = [v for k, v in row.items() if k != "id"] + [pipeline_id]

        db = await self._get_db()
        await db.execute(
            f"UPDATE pipeline_states SET {set_clause} WHERE id = ?",
            values,
        )
        await db.commit()
        logger.info("pipeline_updated", pipeline_id=pipeline_id, updated_fields=list(kwargs.keys()))
        return state

    async def list_by_status(self, status: PipelineStatus) -> list[PipelineState]:
        db = await self._get_db()
        cursor = await db.execute(
            "SELECT * FROM pipeline_states WHERE status = ? ORDER BY created_at DESC",
            (status.value,),
        )
        rows = await cursor.fetchall()
        return [_row_to_state(dict(r)) for r in rows]

    async def get_latest_pending(self) -> PipelineState | None:
        pending = await self.list_by_status(PipelineStatus.PENDING)
        if not pending:
            collecting = await self.list_by_status(PipelineStatus.COLLECTING)
            if not collecting:
                return None
            return collecting[0]
        return pending[0]

    async def delete(self, pipeline_id: str) -> bool:
        db = await self._get_db()
        cursor = await db.execute(
            "DELETE FROM pipeline_states WHERE id = ?", (pipeline_id,)
        )
        await db.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info("pipeline_deleted", pipeline_id=pipeline_id)
        return deleted