"""
Мидлварь для проверки прав администратора.

Используется в админском роутере: если пользователь не в ADMIN_IDS,
запрос отклоняется с сообщением.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from bot.config import settings

logger = logging.getLogger(__name__)


class AdminCheckMiddleware(BaseMiddleware):
    """Пропускает только пользователей из ADMIN_IDS."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_id = self._extract_user_id(event)

        if user_id is None or user_id not in settings.ADMIN_IDS:
            await self._deny(event)
            logger.warning(
                "Admin access denied for user_id=%s",
                user_id,
            )
            return None

        return await handler(event, data)

    @staticmethod
    def _extract_user_id(event: TelegramObject) -> int | None:
        """Извлекает user_id из события."""
        if isinstance(event, Message) and event.from_user:
            return event.from_user.id
        if isinstance(event, CallbackQuery) and event.from_user:
            return event.from_user.id
        return None

    @staticmethod
    async def _deny(event: TelegramObject) -> None:
        """Отправляет сообщение об отказе."""
        if isinstance(event, Message):
            await event.answer("У вас нет доступа к этой команде.")
        elif isinstance(event, CallbackQuery):
            await event.answer("Нет доступа.", show_alert=True)
