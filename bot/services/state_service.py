"""
Сервис управления состоянием пользователя.

Обёртка над db/queries.py для удобной работы с состоянием:
чтение/запись goal, role, current_screen_id, nurture_stage и т.д.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from bot.db import queries

logger = logging.getLogger(__name__)


async def get_user_state(telegram_id: int) -> Optional[Dict[str, Any]]:
    """Возвращает полное состояние пользователя или None."""
    return await queries.get_user(telegram_id)


async def set_goal(telegram_id: int, goal: str) -> None:
    """Сохраняет выбранную цель пользователя."""
    await queries.update_user(telegram_id, goal=goal)
    logger.info("User %d: goal set to %s", telegram_id, goal)


async def set_role(telegram_id: int, role: str) -> None:
    """Сохраняет выбранную роль пользователя."""
    await queries.update_user(telegram_id, role=role)
    logger.info("User %d: role set to %s", telegram_id, role)


async def set_branch(telegram_id: int, branch_id: str) -> None:
    """Устанавливает текущую ветку пользователя."""
    await queries.update_user(telegram_id, branch_id=branch_id)
    logger.info("User %d: branch set to %s", telegram_id, branch_id)


async def set_current_screen(telegram_id: int, screen_id: str) -> None:
    """Обновляет текущий экран пользователя."""
    await queries.update_user(telegram_id, current_screen_id=screen_id)


async def mark_screen_completed(telegram_id: int, screen_id: str) -> None:
    """Отмечает экран как пройденный."""
    await queries.update_user(telegram_id, last_completed_screen_id=screen_id)


async def mark_trial_cta_clicked(telegram_id: int) -> None:
    """Отмечает, что пользователь нажал CTA «Записаться на пробное»."""
    await queries.update_user(telegram_id, clicked_trial_cta=1)
    # Деактивируем nurture
    await queries.deactivate_nurture(telegram_id)
    logger.info("User %d: trial CTA clicked, nurture deactivated", telegram_id)


async def mark_manager_cta_clicked(telegram_id: int) -> None:
    """Отмечает, что пользователь нажал CTA «Написать менеджеру»."""
    await queries.update_user(telegram_id, clicked_manager_cta=1)
    # Деактивируем nurture
    await queries.deactivate_nurture(telegram_id)
    logger.info("User %d: manager CTA clicked, nurture deactivated", telegram_id)


async def set_nurture_stage(telegram_id: int, stage: int, branch_id: str) -> None:
    """Обновляет nurture-стадию пользователя."""
    await queries.update_user(
        telegram_id,
        nurture_stage=stage,
        nurture_branch_id=branch_id,
    )


async def move_to_general_segment(telegram_id: int) -> None:
    """Переводит пользователя в сегмент общего контента."""
    await queries.update_user(
        telegram_id,
        segment="general_useful_nurture",
        nurture_stage=0,
    )
    logger.info("User %d: moved to general_useful_nurture segment", telegram_id)


async def reset_user_flow(telegram_id: int) -> None:
    """Сбрасывает прогресс пользователя для повторного прохождения воронки.

    Сохраняет: telegram_id, username, first_name, source, campaign_tag, created_at.
    Сбрасывает: goal, role, branch, screens, nurture, CTA.
    """
    await queries.update_user(
        telegram_id,
        role=None,
        goal=None,
        branch_id=None,
        current_screen_id=None,
        last_completed_screen_id=None,
        nurture_stage=0,
        nurture_branch_id=None,
        clicked_trial_cta=0,
        clicked_manager_cta=0,
        cta_shown_at=None,
        segment=None,
    )
    await queries.deactivate_nurture(telegram_id)
    logger.info("User %d: flow reset", telegram_id)
