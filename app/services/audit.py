import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession


async def log_event(
    db: AsyncSession,
    action: str,
    actor_id: uuid.UUID | None = None,
    target_type: str | None = None,
    target_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    import json
    await db.execute(
        sa.text(
            "INSERT INTO audit_log (id, actor_id, action, target_type, target_id, metadata) "
            "VALUES (:id, :actor_id, :action, :target_type, :target_id, CAST(:metadata AS jsonb))"
        ),
        {
            "id": str(uuid.uuid4()),
            "actor_id": str(actor_id) if actor_id else None,
            "action": action,
            "target_type": target_type,
            "target_id": str(target_id) if target_id else None,
            "metadata": json.dumps(metadata or {}),
        },
    )
