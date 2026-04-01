"""
Утилиты аналитики.

Предоставляет удобные обёртки для логирования событий.
Основная логика в db/queries.py — здесь вспомогательные функции.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from bot.db.queries import log_analytics_event


async def track_screen_view(
    user_id: int,
    screen_id: str,
    tags: Optional[Dict[str, Any]] = None,
) -> None:
    """Трекинг просмотра экрана."""
    await log_analytics_event(
        user_id=user_id,
        event_type="screen_view",
        screen_id=screen_id,
        event_data=tags,
    )


async def track_button_click(
    user_id: int,
    screen_id: str,
    button_text: str,
    action: str,
    target: str,
) -> None:
    """Трекинг клика по кнопке."""
    await log_analytics_event(
        user_id=user_id,
        event_type="button_click",
        screen_id=screen_id,
        event_data={
            "button_text": button_text,
            "action": action,
            "target": target,
        },
    )
