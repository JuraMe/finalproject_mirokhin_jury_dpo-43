"""Планировщик периодического обновления курсов.

Модуль для автоматического обновления курсов валют
по расписанию (например, каждый час).
"""

import logging
import threading
from datetime import datetime

from valutatrade_hub.parser_service.config import ParserConfig, get_parser_config
from valutatrade_hub.parser_service.updater import update_all_rates

# Настройка логирования
logger = logging.getLogger(__name__)


class RatesScheduler:
    """Планировщик автоматического обновления курсов.

    Запускает обновление курсов с заданным интервалом в фоновом потоке.

    Attributes:
        config: Конфигурация Parser Service.
        interval: Интервал обновления в секундах.
        running: Флаг работы планировщика.
        thread: Фоновый поток для обновлений.
    """

    def __init__(self, interval: int = 3600, config: ParserConfig | None = None):
        """Инициализация планировщика.

        Args:
            interval: Интервал между обновлениями в секундах
                (по умолчанию 3600 = 1 час).
            config: Конфигурация Parser Service (опционально).
        """
        self.config = config or get_parser_config()
        self.interval = interval
        self.running = False
        self.thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def _run_scheduler(self) -> None:
        """Основной цикл планировщика (выполняется в отдельном потоке)."""
        logger.info(
            f"Scheduler started with interval: {self.interval}s "
            f"({self.interval / 3600:.1f}h)"
        )

        while self.running and not self._stop_event.is_set():
            try:
                logger.info(
                    f"\n[Scheduler] Starting scheduled update at "
                    f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                )
                update_all_rates(self.config)

                logger.info(
                    f"[Scheduler] Update completed. Next update in {self.interval}s"
                )

            except Exception as e:
                logger.error(f"[Scheduler] Update failed: {str(e)}", exc_info=True)

            # Ждать до следующего обновления (с возможностью прерывания)
            self._stop_event.wait(self.interval)

        logger.info("Scheduler stopped")

    def start(self) -> None:
        """Запустить планировщик в фоновом потоке.

        Raises:
            RuntimeError: Если планировщик уже запущен.
        """
        if self.running:
            raise RuntimeError("Scheduler is already running")

        self.running = True
        self._stop_event.clear()
        self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.thread.start()

        logger.info("Scheduler thread started")

    def stop(self, timeout: float = 5.0) -> None:
        """Остановить планировщик.

        Args:
            timeout: Максимальное время ожидания остановки потока в секундах.
        """
        if not self.running:
            logger.warning("Scheduler is not running")
            return

        logger.info("Stopping scheduler...")
        self.running = False
        self._stop_event.set()

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=timeout)

            if self.thread.is_alive():
                logger.warning("Scheduler thread did not stop gracefully")
            else:
                logger.info("Scheduler stopped successfully")

    def is_running(self) -> bool:
        """Проверить работает ли планировщик.

        Returns:
            True если планировщик запущен, False иначе.
        """
        return self.running and self.thread is not None and self.thread.is_alive()


def run_scheduler(
    interval: int = 3600, config: ParserConfig | None = None
) -> RatesScheduler:
    """Создать и запустить планировщик обновления курсов.

    Args:
        interval: Интервал между обновлениями в секундах
            (по умолчанию 3600 = 1 час).
        config: Конфигурация Parser Service (опционально).

    Returns:
        Запущенный экземпляр RatesScheduler.

    Example:
        >>> from valutatrade_hub.parser_service.scheduler import run_scheduler
        >>> scheduler = run_scheduler(interval=3600)  # Обновление каждый час
        >>> # Планировщик работает в фоновом потоке
        >>> scheduler.stop()  # Остановить планировщик
    """
    scheduler = RatesScheduler(interval=interval, config=config)
    scheduler.start()
    return scheduler
