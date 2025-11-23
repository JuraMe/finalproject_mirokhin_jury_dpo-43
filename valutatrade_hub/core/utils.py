"""Вспомогательные функции, сервис курсов и валидаторы."""

import json
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"

# =============================================================================
# JSON Storage
# =============================================================================


def load_json(filename: str) -> dict | list:
    """Загрузить данные из JSON файла.

    Args:
        filename: Имя файла в папке data/.

    Returns:
        Данные из файла (dict или list).
    """
    filepath = DATA_DIR / filename
    with filepath.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(filename: str, data: dict | list) -> None:
    """Сохранить данные в JSON файл.

    Args:
        filename: Имя файла в папке data/.
        data: Данные для сохранения.
    """
    filepath = DATA_DIR / filename
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# =============================================================================
# Validators
# =============================================================================


def validate_amount(amount: float) -> float:
    """Валидация суммы (amount > 0).

    Args:
        amount: Сумма для проверки.

    Returns:
        Валидная сумма.

    Raises:
        TypeError: Если amount не число.
        ValueError: Если amount <= 0.
    """
    if not isinstance(amount, (int, float)):
        raise TypeError("Сумма должна быть числом")
    if amount <= 0:
        raise ValueError("Сумма должна быть положительной")
    return float(amount)


def validate_currency_code(code: str) -> str:
    """Валидация кода валюты (непустая строка, верхний регистр).

    Args:
        code: Код валюты.

    Returns:
        Валидный код валюты в верхнем регистре.

    Raises:
        TypeError: Если code не строка.
        ValueError: Если code пустой.
    """
    if not isinstance(code, str):
        raise TypeError("Код валюты должен быть строкой")
    code = code.strip().upper()
    if not code:
        raise ValueError("Код валюты не может быть пустым")
    return code


def require_login(current_user: object | None) -> None:
    """Проверка, что пользователь залогинен.

    Args:
        current_user: Текущий пользователь или None.

    Raises:
        PermissionError: Если пользователь не залогинен.
    """
    if current_user is None:
        raise PermissionError("Требуется авторизация. Выполните команду login.")


# =============================================================================
# Exchange Rates Service
# =============================================================================

# Дефолтные курсы (заглушка)
DEFAULT_RATES: dict[str, float] = {
    "USD": 1.0,
    "EUR": 1.08,
    "GBP": 1.27,
    "RUB": 0.011,
    "CNY": 0.14,
    "JPY": 0.0067,
    "BTC": 95000.0,
    "ETH": 3500.0,
}


def get_rates() -> dict[str, float]:
    """Получить курсы валют из кеша или дефолтные.

    Returns:
        Словарь {код_валюты: курс_к_USD}.
    """
    try:
        data = load_json("rates.json")
        return data.get("rates", DEFAULT_RATES)
    except (FileNotFoundError, json.JSONDecodeError):
        return DEFAULT_RATES.copy()


def get_rate(currency_code: str) -> float:
    """Получить курс конкретной валюты к USD.

    Args:
        currency_code: Код валюты.

    Returns:
        Курс валюты к USD.

    Raises:
        ValueError: Если валюта не найдена.
    """
    code = validate_currency_code(currency_code)
    rates = get_rates()
    if code not in rates:
        raise ValueError(f"Курс для валюты {code} не найден")
    return rates[code]


def update_rates(new_rates: dict[str, float]) -> None:
    """Обновить курсы валют в кеше.

    Args:
        new_rates: Новые курсы валют.
    """
    data = {
        "rates": new_rates,
        "base_currency": "USD",
        "updated_at": datetime.now().isoformat(),
    }
    save_json("rates.json", data)


def get_rates_info() -> dict:
    """Получить информацию о курсах валют.

    Returns:
        Словарь с курсами и временем обновления.
    """
    try:
        data = load_json("rates.json")
        return {
            "rates": data.get("rates", DEFAULT_RATES),
            "base_currency": data.get("base_currency", "USD"),
            "updated_at": data.get("updated_at"),
        }
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "rates": DEFAULT_RATES,
            "base_currency": "USD",
            "updated_at": None,
        }


def convert_currency(
    amount: float,
    from_currency: str,
    to_currency: str,
    rates: dict[str, float] | None = None,
) -> float:
    """Конвертировать сумму из одной валюты в другую.

    Args:
        amount: Сумма для конвертации.
        from_currency: Исходная валюта.
        to_currency: Целевая валюта.
        rates: Курсы валют (если None — используются текущие).

    Returns:
        Сумма в целевой валюте.
    """
    amount = validate_amount(amount)
    from_code = validate_currency_code(from_currency)
    to_code = validate_currency_code(to_currency)

    if rates is None:
        rates = get_rates()

    if from_code not in rates:
        raise ValueError(f"Курс для валюты {from_code} не найден")
    if to_code not in rates:
        raise ValueError(f"Курс для валюты {to_code} не найден")

    # Конвертация через USD
    amount_usd = amount * rates[from_code]
    return amount_usd / rates[to_code]
