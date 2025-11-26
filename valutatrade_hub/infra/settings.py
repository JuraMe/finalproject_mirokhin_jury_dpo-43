"""Управление настройками приложения (Singleton).

Модуль содержит класс SettingsLoader, реализующий паттерн Singleton
для единой точки доступа к конфигурации приложения.
"""

import json
from pathlib import Path
from typing import Any


class SettingsLoader:
    """Singleton для загрузки и кеширования конфигурации приложения.

    Ответственность:
        - Загрузка конфигурации из config.json
        - Кеширование настроек
        - Единая точка доступа к конфигурации

    Гарантия: В приложении существует ровно один экземпляр.

    Реализация Singleton:
        Используется метод __new__ вместо метакласса по следующим причинам:
        1. Простота и читабельность — понятнее для большинства разработчиков
        2. Меньше кода — не требует создания отдельного метакласса
        3. Явность — логика создания единственного экземпляра видна в самом классе
        4. Совместимость — работает без дополнительных метаклассов

    Ключи конфигурации:
        - data_dir: Путь к директории с данными (по умолчанию "data")
        - rates_ttl_seconds: Время жизни курсов в секундах (по умолчанию 3600)
        - base_currency: Базовая валюта (по умолчанию "USD")
        - logs_dir: Путь к директории с логами (по умолчанию "logs")
        - log_level: Уровень логирования (по умолчанию "INFO")
        - log_format: Формат логов
        - max_log_size_mb: Максимальный размер лог-файла в MB
        - log_backup_count: Количество резервных копий логов
        - users_file: Имя файла с пользователями
        - portfolios_file: Имя файла с портфелями
        - rates_file: Имя файла с курсами
        - session_file: Имя файла сессии

    Пример использования:
        >>> settings = SettingsLoader()
        >>> data_dir = settings.get("data_dir")
        >>> ttl = settings.get("rates_ttl_seconds", 3600)
        >>> settings.reload()  # Перезагрузить конфигурацию
    """

    # Единственный экземпляр класса
    _instance: "SettingsLoader | None" = None

    # Флаг инициализации (чтобы __init__ выполнился только один раз)
    _initialized: bool = False

    def __new__(cls) -> "SettingsLoader":
        """Создать или вернуть единственный экземпляр класса.

        Returns:
            Единственный экземпляр SettingsLoader.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Инициализация загрузчика настроек.

        Выполняется только один раз при первом создании экземпляра.
        """
        # Если уже инициализирован, ничего не делаем
        if self._initialized:
            return

        # Путь к файлу конфигурации
        self._config_path = Path(__file__).parent.parent.parent / "data" / "config.json"

        # Кеш настроек
        self._settings: dict[str, Any] = {}

        # Дефолтные значения
        self._defaults: dict[str, Any] = {
            "data_dir": "data",
            "rates_ttl_seconds": 3600,
            "base_currency": "USD",
            "logs_dir": "logs",
            "log_level": "INFO",
            "log_format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            "max_log_size_mb": 10,
            "log_backup_count": 5,
            "users_file": "users.json",
            "portfolios_file": "portfolios.json",
            "rates_file": "rates.json",
            "session_file": ".session",
        }

        # Загрузка конфигурации
        self._load()

        # Помечаем как инициализированный
        self.__class__._initialized = True

    def _load(self) -> None:
        """Загрузить конфигурацию из файла.

        Если файл не существует или содержит ошибки,
        используются дефолтные значения.
        """
        try:
            if self._config_path.exists():
                with open(self._config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._settings = {**self._defaults, **data}
            else:
                # Если файл не существует, используем дефолты
                self._settings = self._defaults.copy()
        except (json.JSONDecodeError, OSError) as e:
            # При ошибке чтения используем дефолты
            print(f"Предупреждение: Не удалось загрузить конфигурацию ({e}), используются дефолтные значения")
            self._settings = self._defaults.copy()

    def get(self, key: str, default: Any = None) -> Any:
        """Получить значение настройки по ключу.

        Args:
            key: Ключ настройки.
            default: Значение по умолчанию, если ключ не найден.

        Returns:
            Значение настройки или default.

        Example:
            >>> settings = SettingsLoader()
            >>> ttl = settings.get("rates_ttl_seconds", 3600)
            >>> data_dir = settings.get("data_dir")
        """
        return self._settings.get(key, default)

    def reload(self) -> None:
        """Перезагрузить конфигурацию из файла.

        Полезно, если конфигурация была изменена во время работы приложения.

        Example:
            >>> settings = SettingsLoader()
            >>> settings.reload()  # Перечитать config.json
        """
        self._load()

    def get_data_path(self, filename: str = "") -> Path:
        """Получить полный путь к файлу в директории данных.

        Args:
            filename: Имя файла в директории данных (опционально).

        Returns:
            Полный путь к директории данных или файлу.

        Example:
            >>> settings = SettingsLoader()
            >>> users_path = settings.get_data_path("users.json")
            >>> data_dir = settings.get_data_path()
        """
        data_dir = Path(__file__).parent.parent.parent / self.get("data_dir", "data")
        if filename:
            return data_dir / filename
        return data_dir

    def get_logs_path(self) -> Path:
        """Получить путь к директории логов.

        Returns:
            Путь к директории логов.

        Example:
            >>> settings = SettingsLoader()
            >>> logs_dir = settings.get_logs_path()
        """
        return Path(__file__).parent.parent.parent / self.get("logs_dir", "logs")

    def get_all(self) -> dict[str, Any]:
        """Получить все настройки.

        Returns:
            Словарь со всеми настройками.

        Example:
            >>> settings = SettingsLoader()
            >>> all_settings = settings.get_all()
            >>> print(all_settings)
        """
        return self._settings.copy()

    def __repr__(self) -> str:
        """Представление объекта для отладки."""
        return f"SettingsLoader(config_path='{self._config_path}', settings_count={len(self._settings)})"


# Удобная функция для получения настроек
def get_settings() -> SettingsLoader:
    """Получить экземпляр SettingsLoader.

    Returns:
        Единственный экземпляр SettingsLoader.

    Example:
        >>> from valutatrade_hub.infra.settings import get_settings
        >>> settings = get_settings()
        >>> ttl = settings.get("rates_ttl_seconds")
    """
    return SettingsLoader()
