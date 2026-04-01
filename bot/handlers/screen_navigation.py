"""
Обработчики навигации по экранам.

Обрабатывает callback_data в формате "action:target":
- go_to_screen:screen_id — переход на указанный экран
- set_goal:goal_value — сохранение цели и переход к выбору роли
- set_role:role_value — сохранение роли и динамический роутинг в ветку
- go_to_next_nurture:screen_id — переход к следующему nurture-экрану
- stay_in_nurture:segment — завершение nurture, перевод в общий сегмент
"""

from __future__ import annotations

import logging

from aiogram import Router, Bot
from aiogram.types import CallbackQuery

from bot.db.queries import get_user, log_analytics_event
from bot.services.screen_renderer import render_screen
from bot.services.state_service import (
    set_goal,
    set_role,
    set_branch,
    mark_screen_completed,
    move_to_general_segment,
)
from bot.services.router_service import resolve_route

logger = logging.getLogger(__name__)
router = Router(name="screen_navigation")


# ──────────────────────────────────────────────
# go_to_screen — простой переход на экран
# ──────────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("go_to_screen:"))
async def handle_go_to_screen(callback: CallbackQuery, bot: Bot) -> None:
    """Переход на указанный экран."""
    await callback.answer()

    target_screen_id = callback.data.split(":", 1)[1]
    telegram_id = callback.from_user.id
    chat_id = callback.message.chat.id

    # Отмечаем предыдущий экран как пройденный
    user = await get_user(telegram_id)
    if user and user.get("current_screen_id"):
        await mark_screen_completed(telegram_id, user["current_screen_id"])

    # Логируем клик
    await log_analytics_event(
        user_id=telegram_id,
        event_type="button_click",
        screen_id=user.get("current_screen_id") if user else None,
        event_data={"action": "go_to_screen", "target": target_screen_id},
    )

    # Рендерим целевой экран
    await render_screen(bot, chat_id, telegram_id, target_screen_id)


# ──────────────────────────────────────────────
# set_goal — выбор цели
# ──────────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("set_goal:"))
async def handle_set_goal(callback: CallbackQuery, bot: Bot) -> None:
    """Сохраняет выбранную цель и переходит к экрану выбора роли."""
    await callback.answer()

    goal_value = callback.data.split(":", 1)[1]
    telegram_id = callback.from_user.id
    chat_id = callback.message.chat.id

    # Сохраняем цель
    await set_goal(telegram_id, goal_value)

    # Отмечаем экран выбора цели как пройденный
    await mark_screen_completed(telegram_id, "shared_goal_select_2")

    # Логируем
    await log_analytics_event(
        user_id=telegram_id,
        event_type="button_click",
        screen_id="shared_goal_select_2",
        event_data={"action": "set_goal", "goal": goal_value},
    )

    # Переходим к экрану выбора роли
    await render_screen(bot, chat_id, telegram_id, "shared_role_select_3")


# ──────────────────────────────────────────────
# set_role — выбор роли + динамический роутинг
# ──────────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("set_role:"))
async def handle_set_role(callback: CallbackQuery, bot: Bot) -> None:
    """Сохраняет роль, определяет ветку и показывает первый экран ветки."""
    await callback.answer()

    role_value = callback.data.split(":", 1)[1]
    telegram_id = callback.from_user.id
    chat_id = callback.message.chat.id

    # Сохраняем роль
    await set_role(telegram_id, role_value)

    # Отмечаем экран выбора роли как пройденный
    await mark_screen_completed(telegram_id, "shared_role_select_3")

    # Получаем goal из состояния
    user = await get_user(telegram_id)
    goal_value = user.get("goal") if user else None

    if not goal_value:
        # Если goal потерян — возвращаем на экран выбора цели
        logger.warning(
            "User %d: goal not found in state, redirecting to goal select",
            telegram_id,
        )
        await render_screen(bot, chat_id, telegram_id, "shared_goal_select_2")
        return

    # Динамический роутинг
    route = resolve_route(goal_value, role_value)

    if not route:
        logger.error(
            "User %d: route not found for goal=%s, role=%s",
            telegram_id, goal_value, role_value,
        )
        await render_screen(bot, chat_id, telegram_id, "shared_goal_select_2")
        return

    target_screen_id, branch_id = route

    # Сохраняем ветку
    await set_branch(telegram_id, branch_id)

    # Логируем
    await log_analytics_event(
        user_id=telegram_id,
        event_type="button_click",
        screen_id="shared_role_select_3",
        event_data={
            "action": "set_role",
            "role": role_value,
            "goal": goal_value,
            "routed_to": target_screen_id,
            "branch_id": branch_id,
        },
    )

    # Рендерим первый экран ветки
    await render_screen(bot, chat_id, telegram_id, target_screen_id)

    logger.info(
        "User %d routed: goal=%s, role=%s → screen=%s, branch=%s",
        telegram_id, goal_value, role_value, target_screen_id, branch_id,
    )


# ──────────────────────────────────────────────
# go_to_next_nurture — переход к следующему nurture-экрану
# ──────────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("go_to_next_nurture:"))
async def handle_go_to_next_nurture(callback: CallbackQuery, bot: Bot) -> None:
    """Пользователь нажал «Читать дальше» в nurture — показываем следующий шаг сразу."""
    await callback.answer()

    target_screen_id = callback.data.split(":", 1)[1]
    telegram_id = callback.from_user.id
    chat_id = callback.message.chat.id

    # Отмечаем текущий экран как пройденный
    user = await get_user(telegram_id)
    if user and user.get("current_screen_id"):
        await mark_screen_completed(telegram_id, user["current_screen_id"])

    # Увеличиваем nurture_stage
    if user:
        current_stage = user.get("nurture_stage", 0)
        branch_id = user.get("nurture_branch_id") or user.get("branch_id")
        if branch_id and current_stage > 0:
            from bot.services.state_service import set_nurture_stage
            await set_nurture_stage(telegram_id, current_stage + 1, branch_id)
            # Деактивируем запланированную отправку в nurture_queue
            from bot.db.queries import deactivate_nurture, create_nurture_entry
            # Пользователь сам нажал "дальше", значит запланированный шаг не нужен
            # Но нужно запланировать следующий если он есть
            # Проще: деактивируем текущую запись, nurture_stage уже обновлён

    # Логируем
    await log_analytics_event(
        user_id=telegram_id,
        event_type="button_click",
        screen_id=user.get("current_screen_id") if user else None,
        event_data={"action": "go_to_next_nurture", "target": target_screen_id},
    )

    # Рендерим следующий nurture-экран
    await render_screen(bot, chat_id, telegram_id, target_screen_id)


# ──────────────────────────────────────────────
# stay_in_nurture — завершение nurture, перевод в общий сегмент
# ──────────────────────────────────────────────

@router.callback_query(lambda c: c.data and c.data.startswith("stay_in_nurture:"))
async def handle_stay_in_nurture(callback: CallbackQuery, bot: Bot) -> None:
    """Пользователь нажал «Пока просто читаю» — переводим в общий сегмент."""
    await callback.answer()

    telegram_id = callback.from_user.id

    # Переводим в общий сегмент
    await move_to_general_segment(telegram_id)

    # Логируем
    await log_analytics_event(
        user_id=telegram_id,
        event_type="button_click",
        screen_id=None,
        event_data={"action": "stay_in_nurture", "result": "moved_to_general"},
    )

    await callback.message.answer(
        "Хорошо! Мы будем иногда присылать полезные материалы.\n\n"
        "Если захотите записаться на пробное или задать вопрос — "
        "кнопки всегда доступны в меню ниже 👇"
    )

    logger.info("User %d: finished nurture, moved to general segment", telegram_id)
