"""
Инициализация APScheduler.

Создаёт AsyncIOScheduler, добавляет периодические джобы
для nurture-отправок и отложенных рассылок.
Запускается из run.py.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from bot.scheduler.nurture_jobs import process_pending_nurture
from bot.scheduler.broadcast_jobs import process_scheduled_broadcasts

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def setup_scheduler() -> AsyncIOScheduler:
    """Настраивает и возвращает scheduler с зарегистрированными джобами.

    Джобы:
    - nurture_processor: каждые 5 минут проверяет nurture_queue
    - broadcast_processor: каждую минуту проверяет запланированные рассылки
    """
    # Проверка nurture-очереди каждые 5 минут
    scheduler.add_job(
        process_pending_nurture,
        trigger=IntervalTrigger(minutes=5),
        id="nurture_processor",
        name="Nurture queue processor",
        replace_existing=True,
        max_instances=1,
    )

    # Проверка запланированных рассылок каждую минуту
    scheduler.add_job(
        process_scheduled_broadcasts,
        trigger=IntervalTrigger(minutes=1),
        id="broadcast_processor",
        name="Broadcast scheduler processor",
        replace_existing=True,
        max_instances=1,
    )

    logger.info("Scheduler настроен: nurture каждые 5 мин, broadcasts каждую 1 мин")
    return scheduler


def start_scheduler() -> None:
    """Запускает scheduler."""
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler запущен")


def shutdown_scheduler() -> None:
    """Останавливает scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler остановлен")
