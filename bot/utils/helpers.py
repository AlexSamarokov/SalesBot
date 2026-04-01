"""
Общие вспомогательные утилиты.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def utc_now() -> datetime:
    """Возвращает текущее время в UTC."""
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Возвращает текущее время в ISO-формате (UTC)."""
    return utc_now().isoformat()


def parse_deep_link(text: str) -> tuple[Optional[str], Optional[str]]:
    """Парсит deep-link параметры из текста /start.

    Формат: /start source_campaign
    Возвращает: (source, campaign_tag)
    """
    parts = text.strip().split(maxsplit=1)
    if len(parts) < 2:
        return None, None

    deep_link = parts[1].strip()
    link_parts = deep_link.split("_", maxsplit=1)
    source = link_parts[0] if len(link_parts) >= 1 else None
    campaign = link_parts[1] if len(link_parts) >= 2 else None

    return source, campaign
