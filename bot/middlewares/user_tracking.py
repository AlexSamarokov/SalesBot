"""
Мидлварь для автоматического отслеживания активности пользователей.

При каждом входящем update обновляет last_activity_at в БД.
Также обнаруживает заблокированных пользователей.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Update

from bot.db.queries import update_last_activity, get_user

logger = logging.getLogger(__name__)


class UserTrackingMiddleware(BaseMiddleware):
    """Обновляет last_activity_at для каждого входящего update."""

    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        # Извлекаем telegram_id из update
        telegram_id = self._extract_user_id(event)

        if telegram_id:
            try:
                user = await get_user(telegram_id)
                if user:
                    await update_last_activity(telegram_id)
            except Exception as e:
                # Не блокируем обработку при ошибке трекинга
                logger.error("Error tracking user %s: %s", telegram_id, e)

        return await handler(event, data)

    @staticmethod
    def _extract_user_id(event: Update) -> int | None:
        """Извлекает telegram_id из любого типа update."""
        if event.message and event.message.from_user:
            return event.message.from_user.id
        if event.callback_query and event.callback_query.from_user:
            return event.callback_query.from_user.id
        if event.edited_message and event.edited_message.from_user:
            return event.edited_message.from_user.id
        return None
