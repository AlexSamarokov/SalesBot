"""
Fallback-обработчик.

Ловит любые текстовые сообщения и callback-запросы,
не обработанные другими хендлерами.
Повторно показывает текущий экран пользователя
или предлагает начать с /start.
"""

from __future__ import annotations

import logging

from aiogram import Router, Bot
from aiogram.types import Message, CallbackQuery

from bot.db.queries import get_user
from bot.services.screen_renderer import render_screen

logger = logging.getLogger(__name__)
router = Router(name="fallback")

FIRST_SCREEN_ID = "shared_welcome_1"


@router.message()
async def handle_unknown_text(message: Message, bot: Bot) -> None:
    """Обрабатывает любой текст, не пойманный другими хендлерами.

    Если пользователь есть в БД и у него есть текущий экран — показываем его.
    Иначе предлагаем начать с /start.
    """
    telegram_id = message.from_user.id
    chat_id = message.chat.id

    user = await get_user(telegram_id)

    if user and user.get("current_screen_id"):
        # Показываем текущий экран повторно
        current_screen = user["current_screen_id"]
        await bot.send_message(
            chat_id=chat_id,
            text="Используйте кнопки для навигации 👇",
        )
        await render_screen(bot, chat_id, telegram_id, current_screen)
    else:
        # Пользователь не начинал — предлагаем /start
        await bot.send_message(
            chat_id=chat_id,
            text="Чтобы начать, отправьте команду /start",
        )

    logger.debug(
        "Fallback text from user %d: %s",
        telegram_id,
        message.text[:50] if message.text else "(no text)",
    )


@router.callback_query()
async def handle_unknown_callback(callback: CallbackQuery, bot: Bot) -> None:
    """Обрабатывает неизвестные callback_data."""
    await callback.answer(
        text="Кнопка больше не активна. Используйте текущие кнопки.",
        show_alert=False,
    )

    logger.debug(
        "Unknown callback from user %d: %s",
        callback.from_user.id,
        callback.data,
    )
