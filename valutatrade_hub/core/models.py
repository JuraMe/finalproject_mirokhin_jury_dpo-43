"""Модели данных для ValutaTrade Hub."""

import hashlib
import secrets
from datetime import datetime


class User:
    """Модель пользователя системы.

    Attributes:
        _user_id: Уникальный идентификатор пользователя.
        _username: Имя пользователя.
        _hashed_password: Пароль в зашифрованном виде.
        _salt: Уникальная соль для пользователя.
        _registration_date: Дата регистрации пользователя.
    """

    def __init__(
        self,
        user_id: int,
        username: str,
        password: str,
        registration_date: datetime | None = None,
    ) -> None:
        """Инициализация пользователя.

        Args:
            user_id: Уникальный идентификатор.
            username: Имя пользователя (не пустое).
            password: Пароль (минимум 4 символа).
            registration_date: Дата регистрации (по умолчанию — текущая).
        """
        if len(password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")
        self._user_id = user_id
        self.username = username  # через сеттер с проверкой
        self._salt = secrets.token_hex(16)
        self._hashed_password = self._hash_password(password)
        self._registration_date = registration_date or datetime.now()

    def _hash_password(self, password: str) -> str:
        """Хеширование пароля с солью.

        Args:
            password: Пароль для хеширования.

        Returns:
            Хешированный пароль.
        """
        salted = password + self._salt
        return hashlib.sha256(salted.encode()).hexdigest()

    # --- Геттеры ---

    @property
    def user_id(self) -> int:
        """Получить ID пользователя."""
        return self._user_id

    @property
    def username(self) -> str:
        """Получить имя пользователя."""
        return self._username

    @property
    def registration_date(self) -> datetime:
        """Получить дату регистрации."""
        return self._registration_date

    @property
    def salt(self) -> str:
        """Получить соль (только для чтения)."""
        return self._salt

    # --- Сеттеры ---

    @username.setter
    def username(self, value: str) -> None:
        """Установить имя пользователя.

        Args:
            value: Новое имя пользователя.

        Raises:
            ValueError: Если имя пустое.
        """
        if not value or not value.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        self._username = value.strip()

    # --- Методы ---

    def get_user_info(self) -> dict:
        """Получить информацию о пользователе (без пароля).

        Returns:
            Словарь с информацией о пользователе.
        """
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat(),
        }

    def change_password(self, new_password: str) -> None:
        """Изменить пароль пользователя.

        Args:
            new_password: Новый пароль (минимум 4 символа).

        Raises:
            ValueError: Если пароль короче 4 символов.
        """
        if len(new_password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")
        self._salt = secrets.token_hex(16)  # новая соль при смене пароля
        self._hashed_password = self._hash_password(new_password)

    def verify_password(self, password: str) -> bool:
        """Проверить введённый пароль на совпадение.

        Args:
            password: Пароль для проверки.

        Returns:
            True если пароль верный, False иначе.
        """
        return self._hashed_password == self._hash_password(password)


class Portfolio:
    """Модель портфеля."""

    pass


class Wallet:
    """Модель кошелька."""

    pass


class Currency:
    """Модель валюты."""

    pass
