"""Иерархия классов валют.

Содержит базовый абстрактный класс Currency и его наследников:
- FiatCurrency — фиатные валюты (USD, EUR, GBP и т.д.)
- CryptoCurrency — криптовалюты (BTC, ETH и т.д.)

Также содержит реестр валют и фабричный метод для получения валюты по коду.
"""

from abc import ABC, abstractmethod

from valutatrade_hub.core.exceptions import CurrencyNotFoundError, InvalidCurrencyCodeError


# =============================================================================
# Абстрактный базовый класс валюты
# =============================================================================


class Currency(ABC):
    """Абстрактный базовый класс для всех валют.

    Атрибуты:
        name: Человекочитаемое имя валюты (например, "US Dollar", "Bitcoin").
        code: ISO-код или общепринятый тикер ("USD", "EUR", "BTC", "ETH").

    Инварианты:
        - code должен быть в верхнем регистре, длиной 2-5 символов, без пробелов.
        - name не должен быть пустой строкой.
    """

    def __init__(self, name: str, code: str):
        """Инициализация валюты.

        Args:
            name: Человекочитаемое имя валюты.
            code: Код валюты (ISO или тикер).

        Raises:
            InvalidCurrencyCodeError: Если код не соответствует требованиям.
            ValueError: Если имя пустое.
        """
        # Валидация имени
        if not name or not name.strip():
            raise ValueError("Имя валюты не может быть пустым")

        # Валидация кода
        self._validate_code(code)

        self.name = name.strip()
        self.code = code.upper()

    @staticmethod
    def _validate_code(code: str) -> None:
        """Валидация кода валюты.

        Args:
            code: Код валюты для проверки.

        Raises:
            InvalidCurrencyCodeError: Если код не соответствует требованиям.
        """
        if not code:
            raise InvalidCurrencyCodeError(code, "код не может быть пустым")

        code_upper = code.upper()

        if len(code_upper) < 2 or len(code_upper) > 5:
            raise InvalidCurrencyCodeError(
                code, "длина кода должна быть 2-5 символов"
            )

        if " " in code_upper:
            raise InvalidCurrencyCodeError(code, "код не может содержать пробелы")

        if not code_upper.isalnum():
            raise InvalidCurrencyCodeError(
                code, "код должен содержать только буквы и цифры"
            )

    @abstractmethod
    def get_display_info(self) -> str:
        """Строковое представление валюты для UI/логов.

        Returns:
            Форматированная строка с информацией о валюте.
        """
        pass

    def __str__(self) -> str:
        """Строковое представление валюты."""
        return self.get_display_info()

    def __repr__(self) -> str:
        """Представление валюты для отладки."""
        return f"{self.__class__.__name__}(name='{self.name}', code='{self.code}')"


# =============================================================================
# Фиатная валюта
# =============================================================================


class FiatCurrency(Currency):
    """Фиатная валюта (государственная валюта).

    Дополнительные атрибуты:
        issuing_country: Страна или зона эмиссии (например, "United States", "Eurozone").

    Пример get_display_info():
        "[FIAT] USD — US Dollar (Issuing: United States)"
    """

    def __init__(self, name: str, code: str, issuing_country: str):
        """Инициализация фиатной валюты.

        Args:
            name: Человекочитаемое имя валюты.
            code: Код валюты.
            issuing_country: Страна или зона эмиссии.

        Raises:
            ValueError: Если issuing_country пустая строка.
        """
        super().__init__(name, code)

        if not issuing_country or not issuing_country.strip():
            raise ValueError("Страна эмиссии не может быть пустой")

        self.issuing_country = issuing_country.strip()

    def get_display_info(self) -> str:
        """Строковое представление фиатной валюты.

        Returns:
            Строка в формате: "[FIAT] USD — US Dollar (Issuing: United States)"
        """
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


# =============================================================================
# Криптовалюта
# =============================================================================


class CryptoCurrency(Currency):
    """Криптовалюта.

    Дополнительные атрибуты:
        algorithm: Алгоритм майнинга/консенсуса (например, "SHA-256", "Ethash").
        market_cap: Последняя известная рыночная капитализация в USD.

    Пример get_display_info():
        "[CRYPTO] BTC — Bitcoin (Algo: SHA-256, MCAP: 1.12e12)"
    """

    def __init__(self, name: str, code: str, algorithm: str, market_cap: float = 0.0):
        """Инициализация криптовалюты.

        Args:
            name: Человекочитаемое имя валюты.
            code: Код валюты (тикер).
            algorithm: Алгоритм майнинга/консенсуса.
            market_cap: Рыночная капитализация (по умолчанию 0.0).

        Raises:
            ValueError: Если algorithm пустая строка или market_cap отрицательная.
        """
        super().__init__(name, code)

        if not algorithm or not algorithm.strip():
            raise ValueError("Алгоритм не может быть пустым")

        if market_cap < 0:
            raise ValueError("Рыночная капитализация не может быть отрицательной")

        self.algorithm = algorithm.strip()
        self.market_cap = market_cap

    def get_display_info(self) -> str:
        """Строковое представление криптовалюты.

        Returns:
            Строка в формате: "[CRYPTO] BTC — Bitcoin (Algo: SHA-256, MCAP: 1.12e12)"
        """
        return (
            f"[CRYPTO] {self.code} — {self.name} "
            f"(Algo: {self.algorithm}, MCAP: {self.market_cap:.2e})"
        )


# =============================================================================
# Реестр валют
# =============================================================================

# Глобальный реестр валют: code -> Currency
_CURRENCY_REGISTRY: dict[str, Currency] = {}


def register_currency(currency: Currency) -> None:
    """Зарегистрировать валюту в реестре.

    Args:
        currency: Объект валюты для регистрации.
    """
    _CURRENCY_REGISTRY[currency.code] = currency


def get_currency(code: str) -> Currency:
    """Получить валюту из реестра по коду.

    Args:
        code: Код валюты (будет приведён к верхнему регистру).

    Returns:
        Объект валюты из реестра.

    Raises:
        CurrencyNotFoundError: Если валюта с указанным кодом не найдена.
    """
    code_upper = code.upper()

    if code_upper not in _CURRENCY_REGISTRY:
        raise CurrencyNotFoundError(code_upper)

    return _CURRENCY_REGISTRY[code_upper]


def get_all_currencies() -> dict[str, Currency]:
    """Получить все зарегистрированные валюты.

    Returns:
        Словарь {код: валюта}.
    """
    return _CURRENCY_REGISTRY.copy()


def is_currency_registered(code: str) -> bool:
    """Проверить, зарегистрирована ли валюта.

    Args:
        code: Код валюты.

    Returns:
        True, если валюта зарегистрирована, иначе False.
    """
    return code.upper() in _CURRENCY_REGISTRY


# =============================================================================
# Инициализация базовых валют
# =============================================================================

def _init_default_currencies() -> None:
    """Инициализация базового набора валют."""
    # Фиатные валюты
    register_currency(FiatCurrency("US Dollar", "USD", "United States"))
    register_currency(FiatCurrency("Euro", "EUR", "Eurozone"))
    register_currency(FiatCurrency("British Pound", "GBP", "United Kingdom"))
    register_currency(FiatCurrency("Russian Ruble", "RUB", "Russia"))
    register_currency(FiatCurrency("Chinese Yuan", "CNY", "China"))
    register_currency(FiatCurrency("Japanese Yen", "JPY", "Japan"))

    # Криптовалюты
    register_currency(
        CryptoCurrency("Bitcoin", "BTC", "SHA-256", market_cap=1.12e12)
    )
    register_currency(
        CryptoCurrency("Ethereum", "ETH", "Ethash", market_cap=4.5e11)
    )


# Инициализация при импорте модуля
_init_default_currencies()
