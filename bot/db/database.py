"""
Подключение к SQLite через aiosqlite.
Предоставляет функцию init_db() для создания таблиц
и контекстный менеджер get_db() для получения соединения.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import aiosqlite

from bot.config import settings
from bot.db.models import ALL_TABLES

logger = logging.getLogger(__name__)

# Глобальный путь к файлу БД
_db_path: str = settings.DATABASE_PATH


async def init_db() -> None:
    """Создаёт директорию и файл БД, выполняет CREATE TABLE IF NOT EXISTS."""
    db_file = Path(_db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(_db_path) as db:
        # Включаем WAL-режим для лучшей конкурентности
        await db.execute("PRAGMA journal_mode=WAL;")
        # Включаем поддержку внешних ключей
        await db.execute("PRAGMA foreign_keys=ON;")

        for table_sql in ALL_TABLES:
            await db.execute(table_sql)

        await db.commit()

    logger.info("База данных инициализирована: %s", _db_path)


@asynccontextmanager
async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """Контекстный менеджер для получения соединения с БД.

    Использование:
        async with get_db() as db:
            await db.execute(...)
    """
    db = await aiosqlite.connect(_db_path)
    db.row_factory = aiosqlite.Row
    try:
        await db.execute("PRAGMA foreign_keys=ON;")
        yield db
    finally:
        await db.close()
