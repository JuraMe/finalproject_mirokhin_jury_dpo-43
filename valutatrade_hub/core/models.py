"""Модели данных для ValutaTrade Hub."""

import hashlib
import secrets
from datetime import datetime

from valutatrade_hub.core.exceptions import (
    InsufficientFundsError,
    InvalidAmountError,
)


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
    """Управление всеми кошельками одного пользователя.

    Attributes:
        _user: Объект пользователя.
        _wallets: Словарь кошельков {код_валюты: Wallet}.
    """

    # Фиксированные курсы валют к USD (для упрощения)
    DEFAULT_EXCHANGE_RATES: dict[str, float] = {
        "USD": 1.0,
        "EUR": 1.08,
        "GBP": 1.27,
        "RUB": 0.011,
        "BTC": 95000.0,
        "ETH": 3500.0,
    }

    def __init__(self, user: "User") -> None:
        """Инициализация портфеля.

        Args:
            user: Объект пользователя-владельца портфеля.
        """
        self._user = user
        self._wallets: dict[str, "Wallet"] = {}

    # --- Properties ---

    @property
    def user(self) -> "User":
        """Получить объект пользователя (только чтение)."""
        return self._user

    @property
    def user_id(self) -> int:
        """Получить ID пользователя."""
        return self._user.user_id

    @property
    def wallets(self) -> dict[str, "Wallet"]:
        """Получить копию словаря кошельков."""
        return self._wallets.copy()

    # --- Методы ---

    def add_currency(self, currency_code: str, initial_balance: float = 0.0) -> "Wallet":
        """Добавить новый кошелёк в портфель.

        Args:
            currency_code: Код валюты (например, "USD", "BTC").
            initial_balance: Начальный баланс (по умолчанию 0.0).

        Returns:
            Созданный объект Wallet.

        Raises:
            ValueError: Если кошелёк с таким кодом уже существует.
        """
        code = currency_code.strip().upper()
        if code in self._wallets:
            raise ValueError(f"Кошелёк {code} уже существует в портфеле")
        wallet = Wallet(code, initial_balance)
        self._wallets[code] = wallet
        return wallet

    def get_wallet(self, currency_code: str) -> "Wallet | None":
        """Получить кошелёк по коду валюты.

        Args:
            currency_code: Код валюты.

        Returns:
            Объект Wallet или None, если не найден.
        """
        return self._wallets.get(currency_code.strip().upper())

    def get_total_value(
        self,
        base_currency: str = "USD",
        exchange_rates: dict[str, float] | None = None,
    ) -> float:
        """Получить общую стоимость всех валют в базовой валюте.

        Args:
            base_currency: Базовая валюта для расчёта (по умолчанию USD).
            exchange_rates: Курсы валют к USD (если None — используются дефолтные).

        Returns:
            Общая стоимость в базовой валюте.
        """
        rates = exchange_rates or self.DEFAULT_EXCHANGE_RATES
        base = base_currency.strip().upper()
        base_rate = rates.get(base, 1.0)

        total_usd = 0.0
        for code, wallet in self._wallets.items():
            rate_to_usd = rates.get(code, 1.0)
            total_usd += wallet.balance * rate_to_usd

        # Конвертируем из USD в базовую валюту
        return total_usd / base_rate

    def buy_currency(
        self,
        currency_code: str,
        amount: float,
        exchange_rates: dict[str, float] | None = None,
    ) -> None:
        """Купить валюту за USD.

        Args:
            currency_code: Код покупаемой валюты.
            amount: Количество покупаемой валюты.
            exchange_rates: Курсы валют к USD.

        Raises:
            ValueError: Если нет USD-кошелька или недостаточно средств.
        """
        rates = exchange_rates or self.DEFAULT_EXCHANGE_RATES
        code = currency_code.strip().upper()

        if code == "USD":
            raise ValueError("Нельзя купить USD за USD")

        usd_wallet = self._wallets.get("USD")
        if not usd_wallet:
            raise ValueError("Нет USD-кошелька для покупки")

        rate = rates.get(code, 1.0)
        cost_usd = amount * rate

        # Списываем USD
        usd_wallet.withdraw(cost_usd)

        # Добавляем купленную валюту
        if code not in self._wallets:
            self.add_currency(code)
        self._wallets[code].deposit(amount)

    def sell_currency(
        self,
        currency_code: str,
        amount: float,
        exchange_rates: dict[str, float] | None = None,
    ) -> None:
        """Продать валюту за USD.

        Args:
            currency_code: Код продаваемой валюты.
            amount: Количество продаваемой валюты.
            exchange_rates: Курсы валют к USD.

        Raises:
            ValueError: Если нет кошелька или недостаточно средств.
        """
        rates = exchange_rates or self.DEFAULT_EXCHANGE_RATES
        code = currency_code.strip().upper()

        if code == "USD":
            raise ValueError("Нельзя продать USD за USD")

        wallet = self._wallets.get(code)
        if not wallet:
            raise ValueError(f"Нет кошелька {code} для продажи")

        # Списываем продаваемую валюту
        wallet.withdraw(amount)

        rate = rates.get(code, 1.0)
        received_usd = amount * rate

        # Начисляем USD
        if "USD" not in self._wallets:
            self.add_currency("USD")
        self._wallets["USD"].deposit(received_usd)

    def get_portfolio_info(self) -> dict:
        """Получить информацию о портфеле.

        Returns:
            Словарь с информацией о портфеле.
        """
        return {
            "user_id": self._user.user_id,
            "wallets": {
                code: wallet.get_balance_info()
                for code, wallet in self._wallets.items()
            },
            "total_value_usd": self.get_total_value("USD"),
        }


class Wallet:
    """Кошелёк пользователя для одной конкретной валюты.

    Attributes:
        currency_code: Код валюты (например, "USD", "BTC").
        _balance: Баланс в данной валюте.
    """

    def __init__(self, currency_code: str, balance: float = 0.0) -> None:
        """Инициализация кошелька.

        Args:
            currency_code: Код валюты (например, "USD", "BTC").
            balance: Начальный баланс (по умолчанию 0.0).

        Raises:
            ValueError: Если код валюты пустой.
        """
        if not currency_code or not currency_code.strip():
            raise ValueError("Код валюты не может быть пустым")
        self.currency_code = currency_code.strip().upper()
        self.balance = balance  # через сеттер с проверкой

    # --- Геттеры и сеттеры ---

    @property
    def balance(self) -> float:
        """Получить текущий баланс."""
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        """Установить баланс.

        Args:
            value: Новое значение баланса.

        Raises:
            TypeError: Если значение не число.
            ValueError: Если значение отрицательное.
        """
        if not isinstance(value, (int, float)):
            raise TypeError("Баланс должен быть числом")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным")
        self._balance = float(value)

    # --- Методы ---

    def deposit(self, amount: float) -> None:
        """Пополнение баланса.

        Args:
            amount: Сумма пополнения.

        Raises:
            TypeError: Если сумма не число.
            InvalidAmountError: Если сумма не положительная.
        """
        if not isinstance(amount, (int, float)):
            raise TypeError("Сумма должна быть числом")
        if amount <= 0:
            raise InvalidAmountError(amount, "сумма должна быть положительной")
        self._balance += amount

    def withdraw(self, amount: float) -> None:
        """Снятие средств.

        Args:
            amount: Сумма снятия.

        Raises:
            TypeError: Если сумма не число.
            InvalidAmountError: Если сумма не положительная.
            InsufficientFundsError: Если сумма превышает баланс.
        """
        if not isinstance(amount, (int, float)):
            raise TypeError("Сумма должна быть числом")
        if amount <= 0:
            raise InvalidAmountError(amount, "сумма должна быть положительной")
        if amount > self._balance:
            raise InsufficientFundsError(
                self.currency_code, required=amount, available=self._balance
            )
        self._balance -= amount

    def get_balance_info(self) -> dict:
        """Получить информацию о текущем балансе.

        Returns:
            Словарь с информацией о кошельке.
        """
        return {
            "currency_code": self.currency_code,
            "balance": self._balance,
        }
