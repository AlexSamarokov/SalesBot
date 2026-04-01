"""
Обработчик команды /start.

- Создаёт пользователя в БД (или находит существующего)
- Парсит deep-link параметры (source, campaign_tag)
- При первом входе: показывает shared_welcome_1
- При повторном входе: предлагает продолжить или начать заново
"""

from __future__ import annotations

import logging

from aiogram import Router, Bot
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
)

from bot.db.queries import get_or_create_user
from bot.services.screen_renderer import render_screen, send_reply_keyboard
from bot.services.state_service import reset_user_flow

logger = logging.getLogger(__name__)
router = Router(name="start")

# ID первого экрана воронки
FIRST_SCREEN_ID = "shared_welcome_1"


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot) -> None:
    """Обработчик /start.

    Deep-link формат: /start source_campaign
    Например: /start vk_spring2025
    """
    telegram_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    # Парсим deep-link параметры
    source = None
    campaign_tag = None
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        deep_link = args[1].strip()
        parts = deep_link.split("_", maxsplit=1)
        source = parts[0] if len(parts) >= 1 else None
        campaign_tag = parts[1] if len(parts) >= 2 else None

    # Получаем или создаём пользователя
    user = await get_or_create_user(
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        source=source,
        campaign_tag=campaign_tag,
    )

    # Устанавливаем persistent reply keyboard
    await send_reply_keyboard(bot, message.chat.id)

    # Проверяем, проходил ли пользователь воронку ранее
    current_screen = user.get("current_screen_id")

    if current_screen and current_screen != FIRST_SCREEN_ID:
        # Повторный /start — пользователь уже в середине воронки
        await _offer_continue_or_restart(message, bot, current_screen)
    else:
        # Первый вход или пользователь на самом первом экране
        await render_screen(bot, message.chat.id, telegram_id, FIRST_SCREEN_ID)

    logger.info(
        "User %d (%s) started bot. source=%s, campaign=%s, returning=%s",
        telegram_id, username, source, campaign_tag, bool(current_screen),
    )


async def _offer_continue_or_restart(
    message: Message,
    bot: Bot,
    current_screen_id: str,
) -> None:
    """Предлагает пользователю продолжить с того же места или начать заново."""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Продолжить",
                    callback_data=f"resume:{current_screen_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Начать заново",
                    callback_data="restart:confirm",
                ),
            ],
        ]
    )

    await bot.send_message(
        chat_id=message.chat.id,
        text="С возвращением! Вы уже начинали проходить бот.\n\nЧто хотите сделать?",
        reply_markup=keyboard,
    )


@router.callback_query(lambda c: c.data and c.data.startswith("resume:"))
async def handle_resume(callback: CallbackQuery, bot: Bot) -> None:
    """Продолжение с текущего экрана."""
    await callback.answer()

    screen_id = callback.data.split(":", 1)[1]
    telegram_id = callback.from_user.id

    await render_screen(bot, callback.message.chat.id, telegram_id, screen_id)


@router.callback_query(lambda c: c.data == "restart:confirm")
async def handle_restart(callback: CallbackQuery, bot: Bot) -> None:
    """Перезапуск воронки с начала."""
    await callback.answer()

    telegram_id = callback.from_user.id

    # Сбрасываем состояние
    await reset_user_flow(telegram_id)

    # Показываем первый экран
    await render_screen(bot, callback.message.chat.id, telegram_id, FIRST_SCREEN_ID)

    logger.info("User %d restarted the funnel", telegram_id)
