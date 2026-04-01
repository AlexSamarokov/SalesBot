"""
Обработчики CTA-кнопок.

CTA-действия — это не переходы на экраны, а действия,
которые открывают контакт с менеджером:
- open_trial_signup — запись на пробное
- open_manager_chat — написать менеджеру / задать вопрос
"""

from __future__ import annotations

import logging

from aiogram import Router, Bot
from aiogram.types import CallbackQuery

from bot.services.manager_contact import handle_trial_signup, handle_manager_contact

logger = logging.getLogger(__name__)
router = Router(name="cta_handlers")


@router.callback_query(lambda c: c.data and c.data.startswith("open_trial_signup:"))
async def handle_trial_cta(callback: CallbackQuery, bot: Bot) -> None:
    """Пользователь нажал «Записаться на пробное» (inline-кнопка на экране)."""
    await callback.answer()

    target = callback.data.split(":", 1)[1]
    telegram_id = callback.from_user.id
    chat_id = callback.message.chat.id

    await handle_trial_signup(
        bot=bot,
        chat_id=chat_id,
        telegram_id=telegram_id,
        source="inline_cta",
        target=target,
    )

    logger.info("User %d: inline trial CTA clicked, target=%s", telegram_id, target)


@router.callback_query(lambda c: c.data and c.data.startswith("open_manager_chat:"))
async def handle_manager_cta(callback: CallbackQuery, bot: Bot) -> None:
    """Пользователь нажал «Написать менеджеру» / «Задать вопрос» (inline-кнопка)."""
    await callback.answer()

    target = callback.data.split(":", 1)[1]
    telegram_id = callback.from_user.id
    chat_id = callback.message.chat.id

    await handle_manager_contact(
        bot=bot,
        chat_id=chat_id,
        telegram_id=telegram_id,
        source="inline_cta",
        target=target,
    )

    logger.info("User %d: inline manager CTA clicked, target=%s", telegram_id, target)
