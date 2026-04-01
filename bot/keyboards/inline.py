"""
Генерация inline-клавиатур из конфигурации экрана.

Каждая кнопка из YAML превращается в InlineKeyboardButton
с callback_data формата: "action:target"
Для CTA-кнопок, ведущих на внешние ссылки, используется url-кнопка.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


# Максимальная длина callback_data в Telegram — 64 байта.
# Наши action:target укладываются.
MAX_CALLBACK_DATA_LEN = 64


def build_inline_keyboard(
    buttons_config: List[Dict[str, Any]],
) -> Optional[InlineKeyboardMarkup]:
    """Строит InlineKeyboardMarkup из списка кнопок экрана.

    Каждая кнопка в конфиге имеет:
        text: str — надпись на кнопке
        action: str — тип действия
        target: str — целевой screen_id, goal, role или manager target

    Callback_data формат: "action:target"
    """
    if not buttons_config:
        return None

    rows: List[List[InlineKeyboardButton]] = []

    for btn_cfg in buttons_config:
        text = btn_cfg.get("text", "")
        action = btn_cfg.get("action", "")
        target = btn_cfg.get("target", "")

        callback_data = f"{action}:{target}"

        # Обрезаем если вдруг длина превышена
        if len(callback_data.encode("utf-8")) > MAX_CALLBACK_DATA_LEN:
            callback_data = callback_data[:MAX_CALLBACK_DATA_LEN]

        button = InlineKeyboardButton(text=text, callback_data=callback_data)
        rows.append([button])

    return InlineKeyboardMarkup(inline_keyboard=rows)
