"""
Менториум Telegram Bot — точка входа.
Инициализирует базу данных, загружает контент, регистрирует хендлеры и запускает polling.
"""

import asyncio
import logging
import sys

from bot.config import settings
from bot.loader import bot, dp
from bot.db.database import init_db
from bot.content.loader import content_manager
from bot.handlers import start, screen_navigation, cta_handlers, menu_handlers, fallback
from bot.handlers.admin import admin_menu, broadcast, drafts
from bot.middlewares.user_tracking import UserTrackingMiddleware
from bot.scheduler.setup import setup_scheduler, start_scheduler, shutdown_scheduler


def setup_logging() -> None:
    """Настройка логирования."""
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def register_routers() -> None:
    """Регистрация всех роутеров в Dispatcher.

    Порядок важен: более специфичные роутеры идут первыми,
    fallback — последним.
    """
    # Админские роутеры (до пользовательских, чтобы /admin обрабатывался раньше)
    dp.include_router(admin_menu.router)
    dp.include_router(broadcast.router)
    dp.include_router(drafts.router)

    # Пользовательские роутеры
    dp.include_router(start.router)
    dp.include_router(cta_handlers.router)
    dp.include_router(screen_navigation.router)
    dp.include_router(menu_handlers.router)
    dp.include_router(fallback.router)


def register_middlewares() -> None:
    """Регистрация мидлварей."""
    dp.update.middleware(UserTrackingMiddleware())


async def main() -> None:
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Инициализация базы данных...")
    await init_db()

    logger.info("Загрузка контента из YAML...")
    content_manager.load_all()
    screen_count = len(content_manager.screens)
    logger.info("Загружено экранов: %d", screen_count)

    register_middlewares()
    register_routers()

    logger.info("Настройка scheduler...")
    setup_scheduler()
    start_scheduler()

    logger.info("Запуск бота...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        shutdown_scheduler()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
