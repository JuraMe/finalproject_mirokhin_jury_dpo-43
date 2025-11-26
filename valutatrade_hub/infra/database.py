"""Управление базой данных (Singleton).

Модуль содержит класс DatabaseManager, реализующий паттерн Singleton
для единой точки доступа к операциям с данными (JSON файлы).
"""

import json
import threading
from pathlib import Path
from typing import Any, Callable

from valutatrade_hub.core.exceptions import DataNotFoundError
from valutatrade_hub.infra.settings import get_settings


class DatabaseManager:
    """Singleton для управления операциями с базой данных (JSON файлы).

    Ответственность:
        - Безопасное чтение и запись JSON файлов
        - Кеширование данных для производительности
        - Потокобезопасные операции (с блокировками)
        - Единая точка доступа к данным

    Гарантия: В приложении существует ровно один экземпляр.

    Реализация Singleton:
        Используется метод __new__ вместо метакласса по следующим причинам:
        1. Простота и читабельность — понятнее для большинства разработчиков
        2. Меньше кода — не требует создания отдельного метакласса
        3. Явность — логика создания единственного экземпляра видна в самом классе
        4. Совместимость — работает без дополнительных метаклассов

    Пример использования:
        >>> db = DatabaseManager()
        >>> users = db.load("users.json")
        >>> db.save("users.json", users)
        >>> # Безопасное обновление
        >>> def add_user(data):
        ...     data.append({"user_id": 1, "username": "alice"})
        ...     return data
        >>> db.update("users.json", add_user)
    """

    # Единственный экземпляр класса
    _instance: "DatabaseManager | None" = None

    # Флаг инициализации
    _initialized: bool = False

    def __new__(cls) -> "DatabaseManager":
        """Создать или вернуть единственный экземпляр класса.

        Returns:
            Единственный экземпляр DatabaseManager.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Инициализация менеджера базы данных.

        Выполняется только один раз при первом создании экземпляра.
        """
        if self._initialized:
            return

        # Получаем настройки
        self._settings = get_settings()

        # Блокировка для потокобезопасности
        self._lock = threading.Lock()

        # Кеш загруженных данных {filename: data}
        self._cache: dict[str, Any] = {}

        # Флаг использования кеша
        self._use_cache = True

        # Помечаем как инициализированный
        self.__class__._initialized = True

    def get_file_path(self, filename: str) -> Path:
        """Получить полный путь к файлу данных.

        Args:
            filename: Имя файла (например, "users.json").

        Returns:
            Полный путь к файлу.

        Example:
            >>> db = DatabaseManager()
            >>> path = db.get_file_path("users.json")
            >>> print(path)
            /path/to/data/users.json
        """
        return self._settings.get_data_path(filename)

    def load(self, filename: str, use_cache: bool = True) -> Any:
        """Загрузить данные из JSON файла.

        Args:
            filename: Имя файла данных.
            use_cache: Использовать кеш (по умолчанию True).

        Returns:
            Данные из файла (list или dict).

        Raises:
            DataNotFoundError: Если файл не найден.
            json.JSONDecodeError: Если файл содержит невалидный JSON.

        Example:
            >>> db = DatabaseManager()
            >>> users = db.load("users.json")
            >>> print(len(users))
            2
        """
        # Проверяем кеш
        if use_cache and self._use_cache and filename in self._cache:
            return self._cache[filename]

        file_path = self.get_file_path(filename)

        # Проверяем существование файла
        if not file_path.exists():
            raise DataNotFoundError(filename)

        # Загружаем данные с блокировкой
        with self._lock:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Сохраняем в кеш
                if self._use_cache:
                    self._cache[filename] = data

                return data

            except json.JSONDecodeError as e:
                raise json.JSONDecodeError(
                    f"Ошибка чтения файла {filename}: {e.msg}",
                    e.doc,
                    e.pos,
                )

    def save(self, filename: str, data: Any, invalidate_cache: bool = True) -> None:
        """Сохранить данные в JSON файл.

        Args:
            filename: Имя файла данных.
            data: Данные для сохранения (должны быть JSON-сериализуемыми).
            invalidate_cache: Очистить кеш после сохранения (по умолчанию True).

        Raises:
            TypeError: Если данные не могут быть сериализованы в JSON.
            OSError: Если не удалось записать файл.

        Example:
            >>> db = DatabaseManager()
            >>> users = [{"user_id": 1, "username": "alice"}]
            >>> db.save("users.json", users)
        """
        file_path = self.get_file_path(filename)

        # Создаём директорию, если не существует
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Сохраняем данные с блокировкой
        with self._lock:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                # Обновляем кеш
                if invalidate_cache and self._use_cache:
                    self._cache[filename] = data

            except (TypeError, OSError) as e:
                raise OSError(f"Ошибка записи файла {filename}: {str(e)}")

    def update(
        self, filename: str, updater: Callable[[Any], Any], use_cache: bool = True
    ) -> Any:
        """Безопасное обновление данных (чтение → модификация → запись).

        Эта функция обеспечивает атомарность операции обновления
        с использованием блокировки.

        Args:
            filename: Имя файла данных.
            updater: Функция-модификатор, принимающая данные и возвращающая обновлённые.
            use_cache: Использовать кеш (по умолчанию True).

        Returns:
            Обновлённые данные.

        Raises:
            DataNotFoundError: Если файл не найден.
            Exception: Если updater бросил исключение.

        Example:
            >>> db = DatabaseManager()
            >>> def add_user(users):
            ...     users.append({"user_id": 3, "username": "charlie"})
            ...     return users
            >>> updated_users = db.update("users.json", add_user)
        """
        with self._lock:
            # Загружаем данные
            data = self.load(filename, use_cache=use_cache)

            # Применяем модификатор
            updated_data = updater(data)

            # Сохраняем обновлённые данные
            self.save(filename, updated_data, invalidate_cache=True)

            return updated_data

    def clear_cache(self, filename: str | None = None) -> None:
        """Очистить кеш.

        Args:
            filename: Имя файла для очистки кеша (если None — очищается весь кеш).

        Example:
            >>> db = DatabaseManager()
            >>> db.clear_cache("users.json")  # Очистить кеш для users.json
            >>> db.clear_cache()  # Очистить весь кеш
        """
        with self._lock:
            if filename is None:
                self._cache.clear()
            elif filename in self._cache:
                del self._cache[filename]

    def set_cache_enabled(self, enabled: bool) -> None:
        """Включить/выключить использование кеша.

        Args:
            enabled: True — использовать кеш, False — не использовать.

        Example:
            >>> db = DatabaseManager()
            >>> db.set_cache_enabled(False)  # Отключить кеширование
        """
        self._use_cache = enabled
        if not enabled:
            self.clear_cache()

    def file_exists(self, filename: str) -> bool:
        """Проверить существование файла.

        Args:
            filename: Имя файла.

        Returns:
            True, если файл существует, иначе False.

        Example:
            >>> db = DatabaseManager()
            >>> exists = db.file_exists("users.json")
            >>> print(exists)
            True
        """
        return self.get_file_path(filename).exists()

    def __repr__(self) -> str:
        """Представление объекта для отладки."""
        data_path = self._settings.get_data_path()
        cache_size = len(self._cache)
        return f"DatabaseManager(data_path='{data_path}', cache_size={cache_size}, cache_enabled={self._use_cache})"


# Удобная функция для получения DatabaseManager
def get_db() -> DatabaseManager:
    """Получить экземпляр DatabaseManager.

    Returns:
        Единственный экземпляр DatabaseManager.

    Example:
        >>> from valutatrade_hub.infra.database import get_db
        >>> db = get_db()
        >>> users = db.load("users.json")
    """
    return DatabaseManager()
