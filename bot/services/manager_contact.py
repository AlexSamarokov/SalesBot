"""
Сервис контакта с менеджером.

Обрабатывает CTA-действия: «Записаться на пробное» и «Написать менеджеру».
Формирует ссылку на менеджера, отправляет пользователю,
обновляет состояние (clicked_trial_cta / clicked_manager_cta),
деактивирует nurture.
"""

from __future__ import annotations

import logging
from typing import Optional

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import settings
from bot.content.loader import content_manager
from bot.db.queries import get_user, log_analytics_event
from bot.services.state_service import mark_trial_cta_clicked, mark_manager_cta_clicked

logger = logging.getLogger(__name__)


def _get_manager_message(telegram_id: int, branch_id: Optional[str], message_key: str) -> str:
    """Получает заготовленный текст для менеджера из контента ветки.

    Если ветка не найдена, возвращает дефолтное сообщение из global_menu.
    """
    if branch_id:
        msg = content_manager.get_manager_message(branch_id, message_key)
        if msg:
            return msg.strip()

    # Fallback из global_menu
    default_messages = content_manager.global_menu.get("default_messages", {})
    if message_key in ("trial_signup",):
        return default_messages.get(
            "trial_signup",
            "Добрый день! Хочу записаться на пробное занятие по математике.",
        ).strip()

    return default_messages.get(
        "contact_manager",
        "Добрый день! У меня есть вопрос по занятиям по математике.",
    ).strip()


async def handle_trial_signup(
    bot: Bot,
    chat_id: int,
    telegram_id: int,
    source: str = "cta_button",
    target: Optional[str] = None,
) -> None:
    """Обрабатывает CTA «Записаться на пробное».

    1. Отмечает clicked_trial_cta в БД
    2. Деактивирует nurture
    3. Отправляет пользователю ссылку на менеджера с заготовленным текстом
    """
    # Получаем данные пользователя для определения ветки
    user = await get_user(telegram_id)
    branch_id = user.get("branch_id") if user else None

    # Отмечаем клик
    await mark_trial_cta_clicked(telegram_id)

    # Получаем текст для менеджера
    manager_text = _get_manager_message(telegram_id, branch_id, "trial_signup")

    # Формируем ссылку на менеджера
    manager_link = settings.MANAGER_CONTACT_LINK

    # Отправляем пользователю сообщение со ссылкой
    response_text = (
        "Отлично! Нажмите на кнопку ниже — откроется чат с менеджером.\n\n"
        f"Ваше сообщение будет начинаться с:\n<i>{manager_text}</i>"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Написать менеджеру", url=manager_link)],
        ]
    )

    await bot.send_message(
        chat_id=chat_id,
        text=response_text,
        reply_markup=keyboard,
    )

    # Аналитика
    await log_analytics_event(
        user_id=telegram_id,
        event_type="cta_click",
        screen_id=user.get("current_screen_id") if user else None,
        event_data={
            "cta_type": "trial_signup",
            "source": source,
            "target": target,
        },
    )

    logger.info("User %d: trial signup CTA handled (source=%s)", telegram_id, source)


async def handle_manager_contact(
    bot: Bot,
    chat_id: int,
    telegram_id: int,
    source: str = "cta_button",
    target: Optional[str] = None,
) -> None:
    """Обрабатывает CTA «Написать менеджеру» / «Задать вопрос».

    1. Отмечает clicked_manager_cta в БД
    2. Деактивирует nurture
    3. Отправляет пользователю ссылку на менеджера с заготовленным текстом
    """
    user = await get_user(telegram_id)
    branch_id = user.get("branch_id") if user else None

    # Отмечаем клик
    await mark_manager_cta_clicked(telegram_id)

    # Получаем текст для менеджера
    manager_text = _get_manager_message(telegram_id, branch_id, "ask_question")

    # Формируем ссылку
    manager_link = settings.MANAGER_CONTACT_LINK

    response_text = (
        "Нажмите на кнопку ниже — откроется чат с менеджером.\n\n"
        f"Ваше сообщение будет начинаться с:\n<i>{manager_text}</i>"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Написать менеджеру", url=manager_link)],
        ]
    )

    await bot.send_message(
        chat_id=chat_id,
        text=response_text,
        reply_markup=keyboard,
    )

    # Аналитика
    await log_analytics_event(
        user_id=telegram_id,
        event_type="cta_click",
        screen_id=user.get("current_screen_id") if user else None,
        event_data={
            "cta_type": "manager_contact",
            "source": source,
            "target": target,
        },
    )

    logger.info("User %d: manager contact CTA handled (source=%s)", telegram_id, source)
