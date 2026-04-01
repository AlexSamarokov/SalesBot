"""
Сервис постоянного меню.

Обрабатывает нажатия кнопок Reply-клавиатуры
«Записаться на пробное» и «Написать менеджеру».
Делегирует действие в manager_contact сервис.
"""

from __future__ import annotations

import logging

from aiogram import Bot

from bot.content.loader import content_manager
from bot.services.manager_contact import handle_trial_signup, handle_manager_contact

logger = logging.getLogger(__name__)


async def handle_menu_trial(bot: Bot, chat_id: int, telegram_id: int) -> None:
    """Обрабатывает нажатие кнопки «Записаться на пробное» из постоянного меню."""
    await handle_trial_signup(
        bot=bot,
        chat_id=chat_id,
        telegram_id=telegram_id,
        source="persistent_menu",
    )


async def handle_menu_manager(bot: Bot, chat_id: int, telegram_id: int) -> None:
    """Обрабатывает нажатие кнопки «Написать менеджеру» из постоянного меню."""
    await handle_manager_contact(
        bot=bot,
        chat_id=chat_id,
        telegram_id=telegram_id,
        source="persistent_menu",
    )
