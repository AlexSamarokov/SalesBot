"""
Сервис управления nurture-цепочками.

Запускает nurture для пользователя после CTA-экрана без клика,
продвигает по шагам, останавливает при клике CTA.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from bot.content.loader import content_manager
from bot.db.queries import (
    create_nurture_entry,
    deactivate_nurture,
    advance_nurture,
)
from bot.services.state_service import set_nurture_stage, move_to_general_segment

logger = logging.getLogger(__name__)


async def start_nurture_for_user(telegram_id: int, branch_id: str) -> None:
    """Запускает nurture-цепочку для пользователя.

    Создаёт запись в nurture_queue со step=1 и рассчитанным временем отправки.
    """
    total_steps = content_manager.get_nurture_total_steps(branch_id)
    if total_steps == 0:
        logger.warning(
            "No nurture steps for branch %s, skipping user %d",
            branch_id, telegram_id,
        )
        return

    delay_hours = content_manager.get_nurture_delay_hours(1)
    next_send_at = datetime.now(timezone.utc) + timedelta(hours=delay_hours)

    await create_nurture_entry(
        user_id=telegram_id,
        branch_id=branch_id,
        next_step=1,
        next_send_at=next_send_at.isoformat(),
    )

    await set_nurture_stage(telegram_id, stage=1, branch_id=branch_id)
    logger.info(
        "Nurture started: user=%d, branch=%s, first send at %s",
        telegram_id, branch_id, next_send_at.isoformat(),
    )


async def advance_nurture_step(
    entry_id: int,
    telegram_id: int,
    branch_id: str,
    current_step: int,
) -> None:
    """Продвигает nurture на следующий шаг или завершает цепочку."""
    total_steps = content_manager.get_nurture_total_steps(branch_id)
    next_step = current_step + 1

    if next_step > total_steps:
        # Nurture завершён — переводим в общий сегмент
        await deactivate_nurture(telegram_id)
        await move_to_general_segment(telegram_id)
        logger.info(
            "Nurture completed: user=%d, branch=%s → general segment",
            telegram_id, branch_id,
        )
        return

    delay_hours = content_manager.get_nurture_delay_hours(next_step)
    next_send_at = datetime.now(timezone.utc) + timedelta(hours=delay_hours)

    await advance_nurture(
        entry_id=entry_id,
        next_step=next_step,
        next_send_at=next_send_at.isoformat(),
    )

    await set_nurture_stage(telegram_id, stage=next_step, branch_id=branch_id)
    logger.info(
        "Nurture advanced: user=%d, branch=%s, step=%d, next send at %s",
        telegram_id, branch_id, next_step, next_send_at.isoformat(),
    )
