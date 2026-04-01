"""
Выбор сегмента для рассылки.

Предоставляет клавиатуру с сегментами и функцию преобразования
выбранного сегмента в dict-фильтр для queries.get_users_by_segment().
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


# Определение всех доступных сегментов
# Формат: (segment_key, label, filter_dict)
SEGMENTS: list[Tuple[str, str, Dict[str, Any]]] = [
    ("all", "Все пользователи", {}),
    ("parents", "Только родители", {"role": "role_parent"}),
    ("students", "Только школьники", {"role": "role_student"}),
    ("goal_school_math", "Цель: школьная математика", {"goal": "goal_school_math"}),
    ("goal_exam", "Цель: ОГЭ / ЕГЭ", {"goal": "goal_exam"}),
    ("goal_olymp", "Цель: олимпиады", {"goal": "goal_olymp"}),
    ("goal_unsure", "Цель: не определились", {"goal": "goal_unsure"}),
    ("cta_clicked", "Кликнули CTA (пробное)", {"clicked_trial_cta": 1}),
    ("cta_not_clicked", "Не кликнули CTA", {"clicked_trial_cta": 0}),
    ("branch_parent_school_math", "Ветка: родитель + школьная", {"branch_id": "parent_school_math"}),
    ("branch_parent_exam", "Ветка: родитель + ОГЭ/ЕГЭ", {"branch_id": "parent_exam"}),
    ("branch_parent_olymp", "Ветка: родитель + олимпиады", {"branch_id": "parent_olymp"}),
    ("branch_parent_unsure", "Ветка: родитель + не знаю", {"branch_id": "parent_unsure"}),
    ("branch_student_school_math", "Ветка: школьник + школьная", {"branch_id": "student_school_math"}),
    ("branch_student_exam", "Ветка: школьник + ОГЭ/ЕГЭ", {"branch_id": "student_exam"}),
    ("branch_student_olymp", "Ветка: школьник + олимпиады", {"branch_id": "student_olymp"}),
    ("branch_student_unsure", "Ветка: школьник + не знаю", {"branch_id": "student_unsure"}),
    ("general_nurture", "Общий nurture-сегмент", {"segment": "general_useful_nurture"}),
]

# Индекс по ключу для быстрого доступа
_SEGMENT_INDEX = {seg[0]: seg for seg in SEGMENTS}


def get_segment_keyboard(page: int = 0, per_page: int = 8) -> InlineKeyboardMarkup:
    """Возвращает клавиатуру выбора сегмента с пагинацией.

    Args:
        page: номер страницы (0-based)
        per_page: сегментов на странице
    """
    total = len(SEGMENTS)
    start = page * per_page
    end = min(start + per_page, total)
    page_segments = SEGMENTS[start:end]

    rows: list[list[InlineKeyboardButton]] = []

    for seg_key, label, _ in page_segments:
        rows.append([
            InlineKeyboardButton(
                text=label,
                callback_data=f"adm:seg:{seg_key}",
            )
        ])

    # Навигация
    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton(text="← Назад", callback_data=f"adm:seg_page:{page - 1}")
        )
    if end < total:
        nav_row.append(
            InlineKeyboardButton(text="Дальше →", callback_data=f"adm:seg_page:{page + 1}")
        )
    if nav_row:
        rows.append(nav_row)

    # Кнопка отмены
    rows.append([
        InlineKeyboardButton(text="✕ Отмена", callback_data="adm:menu")
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_segment_filter(segment_key: str) -> Optional[Dict[str, Any]]:
    """Возвращает dict-фильтр для сегмента или None если не найден."""
    seg = _SEGMENT_INDEX.get(segment_key)
    if seg is None:
        return None
    return seg[2]


def get_segment_label(segment_key: str) -> str:
    """Возвращает человекочитаемое название сегмента."""
    seg = _SEGMENT_INDEX.get(segment_key)
    if seg is None:
        return segment_key
    return seg[1]
