"""Конфигурация системы логирования.

Настраивает логирование для всего приложения:
- Формат логов с временными метками (человекочитаемый)
- Ротацию лог-файлов по размеру
- Уровни логирования для разных компонентов
- Отдельный лог для доменных операций (actions.log)
"""

import logging
import logging.handlers
from pathlib import Path

# Директория для логов
LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Формат логов (человекочитаемый)
# Пример: "INFO 2025-10-09T12:05:22 BUY user='alice' currency='BTC'
#          amount=0.0500 rate=59300.00 base='USD' result=OK"
LOG_FORMAT = "%(levelname)-8s %(asctime)s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

# Формат для доменных операций (упрощенный)
ACTION_LOG_FORMAT = "%(levelname)-5s %(asctime)s %(message)s"

# Уровень логирования по умолчанию
DEFAULT_LOG_LEVEL = logging.INFO


def setup_logging(
    level: int = DEFAULT_LOG_LEVEL,
    log_to_file: bool = True,
    log_to_console: bool = False,
    main_log_file: str = "valutatrade.log",
    action_log_file: str = "actions.log",
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
) -> None:
    """Настроить систему логирования.

    Args:
        level: Уровень логирования (logging.DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_to_file: Логировать в файл.
        log_to_console: Логировать в консоль.
        main_log_file: Имя основного файла логов.
        action_log_file: Имя файла для доменных операций.
        max_bytes: Максимальный размер файла лога перед ротацией.
        backup_count: Количество резервных копий логов.
    """
    # Создаём корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Очищаем существующие обработчики
    root_logger.handlers.clear()

    # Форматтер для основных логов
    main_formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # Обработчик для основного лог-файла с ротацией
    if log_to_file:
        main_file_handler = logging.handlers.RotatingFileHandler(
            LOGS_DIR / main_log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        main_file_handler.setLevel(level)
        main_file_handler.setFormatter(main_formatter)
        root_logger.addHandler(main_file_handler)

    # Обработчик для консоли (опционально)
    if log_to_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(main_formatter)
        root_logger.addHandler(console_handler)


def setup_action_logger(
    name: str = "valutatrade.actions",
    level: int = logging.INFO,
    log_file: str = "actions.log",
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
) -> logging.Logger:
    """Настроить специальный логгер для доменных операций.

    Args:
        name: Имя логгера.
        level: Уровень логирования.
        log_file: Имя файла логов.
        max_bytes: Максимальный размер файла перед ротацией.
        backup_count: Количество резервных копий.

    Returns:
        Настроенный логгер для доменных операций.
    """
    # Создаём логгер для действий
    action_logger = logging.getLogger(name)
    action_logger.setLevel(level)
    action_logger.propagate = False  # Не передавать в корневой логгер

    # Очищаем существующие обработчики
    action_logger.handlers.clear()

    # Форматтер для доменных операций
    action_formatter = logging.Formatter(ACTION_LOG_FORMAT, datefmt=DATE_FORMAT)

    # Обработчик с ротацией
    action_file_handler = logging.handlers.RotatingFileHandler(
        LOGS_DIR / log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    action_file_handler.setLevel(level)
    action_file_handler.setFormatter(action_formatter)
    action_logger.addHandler(action_file_handler)

    return action_logger


def get_logger(name: str) -> logging.Logger:
    """Получить логгер для модуля.

    Args:
        name: Имя модуля (обычно __name__).

    Returns:
        Настроенный логгер.
    """
    return logging.getLogger(name)


def get_action_logger() -> logging.Logger:
    """Получить логгер для доменных операций.

    Returns:
        Логгер для записи BUY/SELL/REGISTER/LOGIN операций.
    """
    return logging.getLogger("valutatrade.actions")


# Инициализация логирования при импорте модуля
setup_logging()
setup_action_logger()
