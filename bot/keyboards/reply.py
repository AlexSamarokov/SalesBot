"""
Генерация ReplyKeyboardMarkup для постоянного меню.

Две кнопки: «Записаться на пробное» и «Написать менеджеру»
отображаются всегда внизу чата.
"""

from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from bot.content.loader import content_manager


# Тексты кнопок по умолчанию (используются если YAML не загружен)
_DEFAULT_TRIAL_TEXT = "Записаться на пробное"
_DEFAULT_MANAGER_TEXT = "Написать менеджеру"


def get_persistent_menu() -> ReplyKeyboardMarkup:
    """Возвращает ReplyKeyboardMarkup с двумя кнопками постоянного меню.

    Тексты берутся из global_menu.yaml, fallback — захардкоженные константы.
    """
    trial_text = _DEFAULT_TRIAL_TEXT
    manager_text = _DEFAULT_MANAGER_TEXT

    # Пытаемся взять тексты из YAML
    actions = content_manager.global_menu.get("actions", [])
    for action in actions:
        action_id = action.get("action_id", "")
        if action_id == "global_trial_signup":
            trial_text = action.get("text", trial_text)
        elif action_id == "global_contact_manager":
            manager_text = action.get("text", manager_text)

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=trial_text), KeyboardButton(text=manager_text)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )

    return keyboard


def get_menu_button_texts() -> tuple[str, str]:
    """Возвращает (trial_text, manager_text) для матчинга в хендлерах."""
    trial_text = _DEFAULT_TRIAL_TEXT
    manager_text = _DEFAULT_MANAGER_TEXT

    actions = content_manager.global_menu.get("actions", [])
    for action in actions:
        action_id = action.get("action_id", "")
        if action_id == "global_trial_signup":
            trial_text = action.get("text", trial_text)
        elif action_id == "global_contact_manager":
            manager_text = action.get("text", manager_text)

    return trial_text, manager_text
