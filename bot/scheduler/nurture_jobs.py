"""
Периодическая джоба обработки nurture-очереди.

Каждые 5 минут:
1. Выбирает из nurture_queue записи, время отправки которых наступило.
2. Проверяет, не нажал ли пользователь CTA / не заблокировал ли бота.
3. Отправляет nurture-экран пользователю.
4. Продвигает очередь на следующий шаг или завершает цепочку.
"""

from __future__ import annotations

import logging
from typing import Dict, Any

from bot.loader import bot
from bot.content.loader import content_manager
from bot.db.queries import (
    get_pending_nurture_entries,
    deactivate_nurture,
    get_user,
)
from bot.services.screen_renderer import render_screen
from bot.services.nurture_service import advance_nurture_step
from bot.db.queries import log_analytics_event

logger = logging.getLogger(__name__)


async def process_pending_nurture() -> None:
    """Обрабатывает все pending nurture-записи."""
    entries = await get_pending_nurture_entries()

    if not entries:
        return

    logger.info("Nurture processor: %d записей к отправке", len(entries))

    for entry in entries:
        try:
            await _process_single_entry(entry)
        except Exception as e:
            logger.error(
                "Ошибка обработки nurture entry id=%s, user=%s: %s",
                entry.get("id"),
                entry.get("user_id"),
                e,
                exc_info=True,
            )


async def _process_single_entry(entry: Dict[str, Any]) -> None:
    """Обрабатывает одну запись из nurture-очереди."""
    entry_id = entry["id"]
    user_id = entry["user_id"]
    branch_id = entry["branch_id"]
    next_step = entry["next_step"]

    # Проверяем: не нажал ли пользователь CTA
    clicked_trial = entry.get("clicked_trial_cta", 0)
    clicked_manager = entry.get("clicked_manager_cta", 0)
    is_blocked = entry.get("is_blocked", 0)

    if clicked_trial or clicked_manager:
        logger.info(
            "Nurture entry %d: user %d clicked CTA, deactivating",
            entry_id, user_id,
        )
        await deactivate_nurture(user_id)
        return

    if is_blocked:
        logger.info(
            "Nurture entry %d: user %d blocked bot, deactivating",
            entry_id, user_id,
        )
        await deactivate_nurture(user_id)
        return

    # Получаем screen_id для текущего nurture-шага
    screen_id = content_manager.get_nurture_screen_id(branch_id, next_step)
    if not screen_id:
        logger.warning(
            "Nurture entry %d: no screen for branch=%s step=%d, deactivating",
            entry_id, branch_id, next_step,
        )
        await deactivate_nurture(user_id)
        return

    # Отправляем nurture-экран
    try:
        success = await render_screen(bot, user_id, user_id, screen_id)

        if not success:
            logger.warning(
                "Nurture entry %d: failed to render screen %s for user %d",
                entry_id, screen_id, user_id,
            )
            await deactivate_nurture(user_id)
            return

    except Exception as e:
        error_msg = str(e).lower()
        # Если бот заблокирован пользователем
        if "forbidden" in error_msg or "blocked" in error_msg:
            logger.info(
                "Nurture entry %d: user %d blocked bot (send failed), deactivating",
                entry_id, user_id,
            )
            from bot.db.queries import update_user
            await update_user(user_id, is_blocked=1)
            await deactivate_nurture(user_id)
            return
        raise

    # Логируем событие
    await log_analytics_event(
        user_id=user_id,
        event_type="nurture_sent",
        screen_id=screen_id,
        event_data={
            "branch_id": branch_id,
            "step": next_step,
        },
    )

    # Продвигаем на следующий шаг
    await advance_nurture_step(
        entry_id=entry_id,
        telegram_id=user_id,
        branch_id=branch_id,
        current_step=next_step,
    )

    logger.info(
        "Nurture sent: user=%d, branch=%s, step=%d, screen=%s",
        user_id, branch_id, next_step, screen_id,
    )
