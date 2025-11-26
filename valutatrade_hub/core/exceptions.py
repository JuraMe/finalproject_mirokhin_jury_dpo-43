"""Пользовательские исключения для ValutaTrade Hub.

Этот модуль содержит специализированные исключения для различных
ошибок в системе управления валютными портфелями.
"""


# =============================================================================
# Исключения для валют
# =============================================================================


class CurrencyNotFoundError(ValueError):
    """Исключение, когда валюта с указанным кодом не найдена в реестре.

    Сообщение: "Неизвестная валюта '{code}'"
    Выбрасывается: currencies.get_currency(), валидация в get-rate
    """

    def __init__(self, code: str):
        self.code = code
        super().__init__(f"Неизвестная валюта '{code}'")


class InvalidCurrencyCodeError(ValueError):
    """Исключение при невалидном коде валюты."""

    def __init__(self, code: str, reason: str):
        self.code = code
        self.reason = reason
        super().__init__(f"Невалидный код валюты '{code}': {reason}")


# =============================================================================
# Исключения для пользователей
# =============================================================================


class UserNotFoundError(ValueError):
    """Исключение, когда пользователь не найден."""

    def __init__(self, identifier: str):
        self.identifier = identifier
        super().__init__(f"Пользователь '{identifier}' не найден")


class UserAlreadyExistsError(ValueError):
    """Исключение при попытке создать пользователя с существующим именем."""

    def __init__(self, username: str):
        self.username = username
        super().__init__(f"Пользователь '{username}' уже существует")


class AuthenticationError(Exception):
    """Исключение при ошибке авторизации."""

    def __init__(self, message: str = "Ошибка авторизации"):
        super().__init__(message)


class UnauthorizedError(Exception):
    """Исключение при попытке выполнить операцию без авторизации."""

    def __init__(self, message: str = "Требуется авторизация"):
        super().__init__(message)


# =============================================================================
# Исключения для портфелей и кошельков
# =============================================================================


class PortfolioNotFoundError(ValueError):
    """Исключение, когда портфель не найден."""

    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(f"Портфель для пользователя с ID {user_id} не найден")


class WalletNotFoundError(ValueError):
    """Исключение, когда кошелёк с указанной валютой не найден."""

    def __init__(self, currency_code: str):
        self.currency_code = currency_code
        super().__init__(f"Кошелёк {currency_code} не найден")


class InsufficientFundsError(ValueError):
    """Исключение при недостаточном балансе для операции.

    Сообщение: "Недостаточно средств: доступно {available} {code}, требуется {required} {code}"
    Выбрасывается: Wallet.withdraw(), usecases.sell_currency()
    """

    def __init__(self, currency_code: str, required: float, available: float):
        self.currency_code = currency_code
        self.required = required
        self.available = available
        super().__init__(
            f"Недостаточно средств: доступно {available} {currency_code}, "
            f"требуется {required} {currency_code}"
        )


# =============================================================================
# Исключения для торговых операций
# =============================================================================


class InvalidAmountError(ValueError):
    """Исключение при невалидной сумме операции."""

    def __init__(self, amount: float, reason: str):
        self.amount = amount
        self.reason = reason
        super().__init__(f"Невалидная сумма {amount}: {reason}")


class TradingError(Exception):
    """Базовое исключение для ошибок торговых операций."""

    pass


# =============================================================================
# Исключения для данных
# =============================================================================


class DataValidationError(ValueError):
    """Исключение при ошибке валидации данных."""

    def __init__(self, field: str, value: any, reason: str):
        self.field = field
        self.value = value
        self.reason = reason
        super().__init__(f"Ошибка валидации поля '{field}' со значением '{value}': {reason}")


class DataNotFoundError(FileNotFoundError):
    """Исключение, когда файл данных не найден."""

    def __init__(self, filename: str):
        self.filename = filename
        super().__init__(f"Файл данных '{filename}' не найден")


# =============================================================================
# Исключения для внешних API
# =============================================================================


class ApiRequestError(Exception):
    """Исключение при сбое обращения к внешнему API.

    Сообщение: "Ошибка при обращении к внешнему API: {reason}"
    Выбрасывается: Слой получения курсов валют (parser/service)
    """

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Ошибка при обращении к внешнему API: {reason}")
