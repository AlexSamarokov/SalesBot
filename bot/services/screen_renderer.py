"""
Универсальный рендерер экранов.

Принимает screen_id, достаёт конфигурацию из ContentManager,
формирует текст, опциональное медиа и inline-клавиатуру,
отправляет в чат вместе с persistent reply-клавиатурой.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from aiogram import Bot
from aiogram.types import (
    InputMediaPhoto,
    InputMediaVideo,
    InputMediaDocument,
)

from bot.content.loader import content_manager
from bot.keyboards.inline import build_inline_keyboard
from bot.keyboards.reply import get_persistent_menu
from bot.db.queries import log_analytics_event, update_user

logger = logging.getLogger(__name__)


async def render_screen(
    bot: Bot,
    chat_id: int,
    telegram_id: int,
    screen_id: str,
) -> bool:
    """Рендерит экран и отправляет его пользователю.

    Возвращает True если экран успешно отправлен, False если screen_id не найден.
    """
    screen = content_manager.get_screen(screen_id)
    if not screen:
        logger.error("Экран не найден: %s", screen_id)
        return False

    text = screen.get("text", "").strip()
    buttons = screen.get("buttons", [])
    media_cfg = screen.get("media", {})

    # Строим inline-клавиатуру
    inline_kb = build_inline_keyboard(buttons)

    # Persistent reply-клавиатура (постоянное меню)
    reply_kb = get_persistent_menu()

    # Определяем, есть ли медиа
    media_enabled = media_cfg.get("enabled", False) if media_cfg else False
    media_type = media_cfg.get("type") if media_cfg else None
    media_file_id = media_cfg.get("file_id") if media_cfg else None
    media_caption = media_cfg.get("caption") if media_cfg else None

    sent = False

    if media_enabled and media_type and media_file_id:
        # Отправляем медиа с текстом как caption
        caption = media_caption or text
        try:
            if media_type == "photo":
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=media_file_id,
                    caption=caption,
                    reply_markup=inline_kb,
                )
                sent = True
            elif media_type == "video":
                await bot.send_video(
                    chat_id=chat_id,
                    video=media_file_id,
                    caption=caption,
                    reply_markup=inline_kb,
                )
                sent = True
            elif media_type == "document":
                await bot.send_document(
                    chat_id=chat_id,
                    document=media_file_id,
                    caption=caption,
                    reply_markup=inline_kb,
                )
                sent = True
        except Exception as e:
            logger.error("Ошибка отправки медиа для экрана %s: %s", screen_id, e)
            sent = False

    if not sent:
        # Отправляем текстовое сообщение
        # Сначала отправляем reply keyboard (через отдельное невидимое сообщение
        # или вместе с основным — aiogram позволяет только одну клавиатуру на сообщение)
        # Отправляем основное сообщение с inline-клавиатурой
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=inline_kb,
        )

    # Обновляем reply-клавиатуру отдельным сообщением только если нет inline
    # Но лучше: отправляем reply keyboard как невидимый "маркер"
    # Однако в Telegram нельзя отправить два markup сразу.
    # Решение: отправляем reply keyboard через отдельный вызов если её ещё нет.
    # На практике reply keyboard сохраняется до замены, поэтому
    # достаточно отправить её один раз при /start.

    # Обновляем состояние пользователя
    update_fields: Dict[str, Any] = {
        "current_screen_id": screen_id,
    }

    # Если это CTA-экран, записываем время показа
    screen_type = screen.get("type", "")
    if screen_type == "cta":
        from bot.db.queries import _now
        update_fields["cta_shown_at"] = _now()

    await update_user(telegram_id, **update_fields)

    # Логируем просмотр экрана
    analytics_tags = screen.get("analytics_tags", {})
    await log_analytics_event(
        user_id=telegram_id,
        event_type="screen_view",
        screen_id=screen_id,
        event_data=analytics_tags,
    )

    return True


async def send_reply_keyboard(bot: Bot, chat_id: int) -> None:
    """Отправляет невидимое сообщение с reply-клавиатурой.

    Используется при /start для установки постоянного меню.
    """
    reply_kb = get_persistent_menu()
    # Отправляем минимальное сообщение с reply keyboard
    await bot.send_message(
        chat_id=chat_id,
        text="👇 Меню всегда доступно внизу",
        reply_markup=reply_kb,
    )
