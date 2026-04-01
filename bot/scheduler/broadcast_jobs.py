"""
Периодическая джоба обработки запланированных рассылок.

Каждую минуту:
1. Выбирает рассылки со статусом 'scheduled' и scheduled_at <= now.
2. Выполняет отправку по сегменту.
3. Логирует результаты.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from bot.loader import bot
from bot.db.database import get_db
from bot.db.queries import get_users_by_segment, log_analytics_event

logger = logging.getLogger(__name__)


async def process_scheduled_broadcasts() -> None:
    """Проверяет и отправляет запланированные рассылки."""
    now = datetime.now(timezone.utc).isoformat()

    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT * FROM broadcasts
            WHERE status = 'scheduled' AND scheduled_at <= ?
            """,
            (now,),
        )
        rows = await cursor.fetchall()
        broadcasts = [dict(r) for r in rows]

    if not broadcasts:
        return

    logger.info("Broadcast processor: %d рассылок к отправке", len(broadcasts))

    for broadcast in broadcasts:
        try:
            await _execute_broadcast(broadcast)
        except Exception as e:
            logger.error(
                "Ошибка рассылки id=%s: %s",
                broadcast.get("id"),
                e,
                exc_info=True,
            )
            # Помечаем как ошибку, но не теряем
            await _update_broadcast_status(broadcast["id"], "draft")


async def _execute_broadcast(broadcast: Dict[str, Any]) -> None:
    """Выполняет одну рассылку."""
    broadcast_id = broadcast["id"]
    text = broadcast["text"]
    media_type = broadcast.get("media_type")
    media_file_id = broadcast.get("media_file_id")
    segment_json = broadcast.get("segment_filter", "{}")

    # Парсим фильтр сегмента
    try:
        segment_filter = json.loads(segment_json) if segment_json else {}
    except json.JSONDecodeError:
        segment_filter = {}

    # Помечаем как "в процессе"
    await _update_broadcast_status(broadcast_id, "sending")

    # Получаем пользователей по сегменту
    users = await get_users_by_segment(segment_filter)

    sent_count = 0
    fail_count = 0
    now = datetime.now(timezone.utc).isoformat()

    for user in users:
        user_id = user["telegram_id"]
        status = "sent"
        error = None

        try:
            if media_type and media_file_id:
                await _send_media_broadcast(user_id, text, media_type, media_file_id)
            else:
                await bot.send_message(chat_id=user_id, text=text)
            sent_count += 1
        except Exception as e:
            error_msg = str(e).lower()
            if "forbidden" in error_msg or "blocked" in error_msg:
                status = "blocked"
                # Помечаем пользователя как заблокировавшего бота
                from bot.db.queries import update_user
                await update_user(user_id, is_blocked=1)
            else:
                status = "failed"
            error = str(e)[:500]
            fail_count += 1

        # Логируем результат в broadcast_logs
        async with get_db() as db:
            await db.execute(
                """
                INSERT INTO broadcast_logs
                    (broadcast_id, user_id, status, error, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (broadcast_id, user_id, status, error, now),
            )
            await db.commit()

    # Обновляем статус рассылки
    await _update_broadcast_status(broadcast_id, "sent", sent_at=now)

    logger.info(
        "Broadcast %d completed: %d sent, %d failed, %d total",
        broadcast_id, sent_count, fail_count, len(users),
    )


async def _send_media_broadcast(
    chat_id: int,
    text: str,
    media_type: str,
    media_file_id: str,
) -> None:
    """Отправляет рассылку с медиа."""
    if media_type == "photo":
        await bot.send_photo(chat_id=chat_id, photo=media_file_id, caption=text)
    elif media_type == "video":
        await bot.send_video(chat_id=chat_id, video=media_file_id, caption=text)
    elif media_type == "document":
        await bot.send_document(chat_id=chat_id, document=media_file_id, caption=text)
    else:
        await bot.send_message(chat_id=chat_id, text=text)


async def _update_broadcast_status(
    broadcast_id: int,
    status: str,
    sent_at: str | None = None,
) -> None:
    """Обновляет статус рассылки в БД."""
    async with get_db() as db:
        if sent_at:
            await db.execute(
                "UPDATE broadcasts SET status = ?, sent_at = ? WHERE id = ?",
                (status, sent_at, broadcast_id),
            )
        else:
            await db.execute(
                "UPDATE broadcasts SET status = ? WHERE id = ?",
                (status, broadcast_id),
            )
        await db.commit()
