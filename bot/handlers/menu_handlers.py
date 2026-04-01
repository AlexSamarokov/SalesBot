"""
Обработчики нажатий кнопок постоянного Reply-меню.

Матчит текст входящего сообщения с текстами кнопок из global_menu.yaml
и делегирует в соответствующий сервис.
"""

from __future__ import annotations

import logging

from aiogram import Router, Bot, F
from aiogram.types import Message

from bot.keyboards.reply import get_menu_button_texts
from bot.services.menu_service import handle_menu_trial, handle_menu_manager

logger = logging.getLogger(__name__)
router = Router(name="menu_handlers")

# Тексты кнопок меню
_trial_text, _manager_text = get_menu_button_texts()


@router.message(F.text == _trial_text)
async def handle_persistent_trial(message: Message, bot: Bot) -> None:
    """Нажатие «Записаться на пробное» из постоянного меню."""
    telegram_id = message.from_user.id
    chat_id = message.chat.id

    await handle_menu_trial(bot, chat_id, telegram_id)

    logger.info("User %d: persistent menu → trial signup", telegram_id)


@router.message(F.text == _manager_text)
async def handle_persistent_manager(message: Message, bot: Bot) -> None:
    """Нажатие «Написать менеджеру» из постоянного меню."""
    telegram_id = message.from_user.id
    chat_id = message.chat.id

    await handle_menu_manager(bot, chat_id, telegram_id)

    logger.info("User %d: persistent menu → manager contact", telegram_id)
