"""
CRUD-операции над таблицами базы данных.
Каждая функция получает соединение через get_db() самостоятельно.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bot.db.database import get_db

logger = logging.getLogger(__name__)


def _now() -> str:
    """Текущее время в ISO-формате (UTC)."""
    return datetime.now(timezone.utc).isoformat()


# ──────────────────────────────────────────────
# Users
# ──────────────────────────────────────────────

async def get_user(telegram_id: int) -> Optional[Dict[str, Any]]:
    """Возвращает пользователя по telegram_id или None."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)


async def create_user(
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    source: Optional[str] = None,
    campaign_tag: Optional[str] = None,
) -> Dict[str, Any]:
    """Создаёт нового пользователя и возвращает его."""
    now = _now()
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO users
                (telegram_id, username, first_name, source, campaign_tag,
                 created_at, updated_at, last_activity_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (telegram_id, username, first_name, source, campaign_tag, now, now, now),
        )
        await db.commit()

    return await get_user(telegram_id)  # type: ignore[return-value]


async def get_or_create_user(
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    source: Optional[str] = None,
    campaign_tag: Optional[str] = None,
) -> Dict[str, Any]:
    """Возвращает существующего пользователя или создаёт нового."""
    user = await get_user(telegram_id)
    if user is not None:
        return user
    return await create_user(
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        source=source,
        campaign_tag=campaign_tag,
    )


async def update_user(telegram_id: int, **fields: Any) -> None:
    """Обновляет произвольные поля пользователя.

    Пример:
        await update_user(12345, goal="goal_exam", role="role_parent")
    """
    if not fields:
        return

    fields["updated_at"] = _now()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [telegram_id]

    async with get_db() as db:
        await db.execute(
            f"UPDATE users SET {set_clause} WHERE telegram_id = ?",
            values,
        )
        await db.commit()


async def update_last_activity(telegram_id: int) -> None:
    """Обновляет время последней активности."""
    now = _now()
    async with get_db() as db:
        await db.execute(
            "UPDATE users SET last_activity_at = ? WHERE telegram_id = ?",
            (now, telegram_id),
        )
        await db.commit()


async def get_users_by_segment(segment_filter: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Возвращает пользователей по фильтру сегмента.

    Поддерживаемые ключи фильтра:
        role, goal, branch_id, clicked_trial_cta, clicked_manager_cta, segment
    """
    conditions = ["is_active = 1", "is_blocked = 0"]
    params: List[Any] = []

    for key, value in segment_filter.items():
        if key in (
            "role", "goal", "branch_id", "segment",
            "clicked_trial_cta", "clicked_manager_cta",
        ):
            conditions.append(f"{key} = ?")
            params.append(value)

    where = " AND ".join(conditions)

    async with get_db() as db:
        cursor = await db.execute(
            f"SELECT * FROM users WHERE {where}",
            params,
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


# ──────────────────────────────────────────────
# Analytics
# ──────────────────────────────────────────────

async def log_analytics_event(
    user_id: int,
    event_type: str,
    screen_id: Optional[str] = None,
    event_data: Optional[Dict[str, Any]] = None,
) -> None:
    """Записывает аналитическое событие."""
    now = _now()
    data_json = json.dumps(event_data, ensure_ascii=False) if event_data else None

    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO analytics_events (user_id, screen_id, event_type, event_data, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, screen_id, event_type, data_json, now),
        )
        await db.commit()


# ──────────────────────────────────────────────
# Nurture Queue
# ──────────────────────────────────────────────

async def create_nurture_entry(
    user_id: int,
    branch_id: str,
    next_step: int,
    next_send_at: str,
) -> None:
    """Добавляет пользователя в очередь nurture."""
    now = _now()
    async with get_db() as db:
        # Деактивируем предыдущие записи для этого пользователя
        await db.execute(
            "UPDATE nurture_queue SET is_active = 0 WHERE user_id = ?",
            (user_id,),
        )
        await db.execute(
            """
            INSERT INTO nurture_queue (user_id, branch_id, next_step, next_send_at, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, branch_id, next_step, next_send_at, now),
        )
        await db.commit()

    logger.info(
        "Nurture entry created: user=%d, branch=%s, step=%d, send_at=%s",
        user_id, branch_id, next_step, next_send_at,
    )


async def get_pending_nurture_entries() -> List[Dict[str, Any]]:
    """Возвращает все активные записи nurture, время отправки которых наступило."""
    now = _now()
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT nq.*, u.clicked_trial_cta, u.clicked_manager_cta, u.is_blocked
            FROM nurture_queue nq
            JOIN users u ON nq.user_id = u.telegram_id
            WHERE nq.is_active = 1 AND nq.next_send_at <= ?
            """,
            (now,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def deactivate_nurture(user_id: int) -> None:
    """Деактивирует nurture для пользователя (при клике CTA или блокировке)."""
    async with get_db() as db:
        await db.execute(
            "UPDATE nurture_queue SET is_active = 0 WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()

    logger.info("Nurture deactivated for user=%d", user_id)


async def advance_nurture(
    entry_id: int,
    next_step: int,
    next_send_at: str,
) -> None:
    """Продвигает nurture-запись на следующий шаг."""
    async with get_db() as db:
        await db.execute(
            "UPDATE nurture_queue SET next_step = ?, next_send_at = ? WHERE id = ?",
            (next_step, next_send_at, entry_id),
        )
        await db.commit()
