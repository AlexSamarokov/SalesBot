"""
Конфигурация приложения.
Читает переменные окружения из файла .env и валидирует их.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv

# Загружаем .env из корня проекта
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)


@dataclass(frozen=True)
class Settings:
    """Иммутабельные настройки приложения."""

    BOT_TOKEN: str
    ADMIN_IDS: List[int]
    MANAGER_CONTACT_LINK: str
    DATABASE_PATH: str
    LOG_LEVEL: str

    # Путь к директории с YAML-контентом
    CONTENT_DIR: str = str(Path(__file__).resolve().parent / "content")

    @classmethod
    def from_env(cls) -> Settings:
        """Создаёт Settings из переменных окружения."""
        bot_token = os.getenv("BOT_TOKEN", "")
        if not bot_token:
            raise ValueError("BOT_TOKEN не задан в .env")

        raw_admin_ids = os.getenv("ADMIN_IDS", "")
        admin_ids: List[int] = []
        if raw_admin_ids.strip():
            admin_ids = [int(x.strip()) for x in raw_admin_ids.split(",") if x.strip()]

        manager_link = os.getenv("MANAGER_CONTACT_LINK", "")
        if not manager_link:
            raise ValueError("MANAGER_CONTACT_LINK не задан в .env")

        database_path = os.getenv("DATABASE_PATH", "data/mentorium.db")
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()

        return cls(
            BOT_TOKEN=bot_token,
            ADMIN_IDS=admin_ids,
            MANAGER_CONTACT_LINK=manager_link,
            DATABASE_PATH=database_path,
            LOG_LEVEL=log_level,
        )


settings = Settings.from_env()
