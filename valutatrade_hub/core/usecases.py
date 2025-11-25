"""Бизнес-логика приложения (usecases).

Этот модуль содержит функции бизнес-логики, которые вызываются из CLI.
Вся работа с данными и моделями происходит здесь.
"""

from datetime import datetime

from valutatrade_hub.core.models import Portfolio, User, Wallet
from valutatrade_hub.core.utils import (
    get_rate,
    get_rates,
    get_rates_info,
    load_json,
    require_login,
    save_json,
    validate_amount,
    validate_currency_code,
)

# =============================================================================
# User Management
# =============================================================================


def register_user(username: str, password: str) -> User:
    """Регистрация нового пользователя.

    Args:
        username: Имя пользователя.
        password: Пароль (минимум 4 символа).

    Returns:
        Созданный объект User.

    Raises:
        ValueError: Если пользователь уже существует.
    """
    users_data = load_json("users.json")

    # Проверка уникальности username
    for u in users_data:
        if u["username"] == username:
            raise ValueError(f"Пользователь '{username}' уже существует")

    # Генерация нового user_id
    user_id = max((u["user_id"] for u in users_data), default=0) + 1

    # Создание пользователя
    user = User(user_id, username, password)

    # Сохранение в JSON
    users_data.append({
        "user_id": user.user_id,
        "username": user.username,
        "hashed_password": user._hashed_password,
        "salt": user.salt,
        "registration_date": user.registration_date.isoformat(),
    })
    save_json("users.json", users_data)

    # Создаём пустой портфель для пользователя
    _create_portfolio(user)

    return user


def login_user(username: str, password: str) -> User:
    """Авторизация пользователя.

    Args:
        username: Имя пользователя.
        password: Пароль.

    Returns:
        Объект User при успешной авторизации.

    Raises:
        ValueError: Если пользователь не найден или пароль неверный.
    """
    users_data = load_json("users.json")

    for u in users_data:
        if u["username"] == username:
            # Восстанавливаем User для проверки пароля
            user = _restore_user(u)
            if user.verify_password(password):
                return user
            raise ValueError("Неверный пароль")

    raise ValueError(f"Пользователь '{username}' не найден")


def get_user_info(user: User) -> dict:
    """Получить информацию о пользователе.

    Args:
        user: Объект пользователя.

    Returns:
        Словарь с информацией о пользователе.
    """
    require_login(user)
    return user.get_user_info()


def _restore_user(data: dict) -> User:
    """Восстановить объект User из данных JSON.

    Args:
        data: Словарь с данными пользователя.

    Returns:
        Объект User.
    """
    # Создаём временный объект с фиктивным паролем
    user = User(
        user_id=data["user_id"],
        username=data["username"],
        password="temp",  # будет перезаписан
        registration_date=datetime.fromisoformat(data["registration_date"]),
    )
    # Восстанавливаем хеш и соль
    user._salt = data["salt"]
    user._hashed_password = data["hashed_password"]
    return user


# =============================================================================
# Portfolio Management
# =============================================================================


def _create_portfolio(user: User) -> None:
    """Создать пустой портфель для пользователя.

    Args:
        user: Объект пользователя.
    """
    portfolios_data = load_json("portfolios.json")
    portfolios_data.append({
        "user_id": user.user_id,
        "wallets": {},
    })
    save_json("portfolios.json", portfolios_data)


def get_portfolio(user: User) -> Portfolio:
    """Получить портфель пользователя.

    Args:
        user: Объект пользователя.

    Returns:
        Объект Portfolio.

    Raises:
        ValueError: Если портфель не найден.
    """
    require_login(user)
    portfolios_data = load_json("portfolios.json")

    for p in portfolios_data:
        if p["user_id"] == user.user_id:
            portfolio = Portfolio(user)
            # Восстанавливаем кошельки
            for code, wallet_data in p.get("wallets", {}).items():
                wallet = Wallet(code, wallet_data["balance"])
                portfolio._wallets[code] = wallet
            return portfolio

    raise ValueError("Портфель не найден")


def _save_portfolio(portfolio: Portfolio) -> None:
    """Сохранить портфель в JSON.

    Args:
        portfolio: Объект Portfolio.
    """
    portfolios_data = load_json("portfolios.json")

    for p in portfolios_data:
        if p["user_id"] == portfolio.user_id:
            p["wallets"] = {
                code: {"balance": wallet.balance}
                for code, wallet in portfolio._wallets.items()
            }
            break
    else:
        # Если портфель не найден, создаём новый
        portfolios_data.append({
            "user_id": portfolio.user_id,
            "wallets": {
                code: {"balance": wallet.balance}
                for code, wallet in portfolio._wallets.items()
            },
        })

    save_json("portfolios.json", portfolios_data)


def get_portfolio_info(user: User, base_currency: str = "USD") -> dict:
    """Получить информацию о портфеле.

    Args:
        user: Объект пользователя.
        base_currency: Базовая валюта для расчёта общей стоимости.

    Returns:
        Словарь с информацией о портфеле.
    """
    portfolio = get_portfolio(user)
    rates = get_rates()

    return {
        "user_id": user.user_id,
        "username": user.username,
        "wallets": {
            code: {
                "balance": wallet.balance,
                "value_in_base": wallet.balance * rates.get(code, 1.0) / rates.get(base_currency, 1.0)
            }
            for code, wallet in portfolio._wallets.items()
        },
        "total_value": portfolio.get_total_value(base_currency, rates),
        "base_currency": base_currency,
    }


# =============================================================================
# Wallet Operations
# =============================================================================


def add_wallet(user: User, currency_code: str, initial_balance: float = 0.0) -> Wallet:
    """Добавить кошелёк в портфель.

    Args:
        user: Объект пользователя.
        currency_code: Код валюты.
        initial_balance: Начальный баланс.

    Returns:
        Созданный объект Wallet.
    """
    require_login(user)
    code = validate_currency_code(currency_code)
    if initial_balance > 0:
        validate_amount(initial_balance)

    portfolio = get_portfolio(user)
    wallet = portfolio.add_currency(code, initial_balance)
    _save_portfolio(portfolio)
    return wallet


def deposit(user: User, currency_code: str, amount: float) -> dict:
    """Пополнить кошелёк.

    Args:
        user: Объект пользователя.
        currency_code: Код валюты.
        amount: Сумма пополнения.

    Returns:
        Информация о кошельке после пополнения.
    """
    require_login(user)
    code = validate_currency_code(currency_code)
    amount = validate_amount(amount)

    portfolio = get_portfolio(user)
    wallet = portfolio.get_wallet(code)

    if not wallet:
        # Создаём кошелёк, если его нет
        wallet = portfolio.add_currency(code, 0.0)

    wallet.deposit(amount)
    _save_portfolio(portfolio)
    return wallet.get_balance_info()


def withdraw(user: User, currency_code: str, amount: float) -> dict:
    """Снять средства с кошелька.

    Args:
        user: Объект пользователя.
        currency_code: Код валюты.
        amount: Сумма снятия.

    Returns:
        Информация о кошельке после снятия.
    """
    require_login(user)
    code = validate_currency_code(currency_code)
    amount = validate_amount(amount)

    portfolio = get_portfolio(user)
    wallet = portfolio.get_wallet(code)

    if not wallet:
        raise ValueError(f"Кошелёк {code} не найден")

    wallet.withdraw(amount)
    _save_portfolio(portfolio)
    return wallet.get_balance_info()


def get_balance(user: User, currency_code: str) -> dict:
    """Получить баланс кошелька.

    Args:
        user: Объект пользователя.
        currency_code: Код валюты.

    Returns:
        Информация о балансе.
    """
    require_login(user)
    code = validate_currency_code(currency_code)

    portfolio = get_portfolio(user)
    wallet = portfolio.get_wallet(code)

    if not wallet:
        raise ValueError(f"Кошелёк {code} не найден")

    return wallet.get_balance_info()


# =============================================================================
# Trading Operations
# =============================================================================


def buy_currency(user: User, currency_code: str, amount: float) -> dict:
    """Купить валюту за USD.

    Args:
        user: Объект пользователя.
        currency_code: Код покупаемой валюты.
        amount: Количество покупаемой валюты.

    Returns:
        Результат операции.
    """
    require_login(user)
    code = validate_currency_code(currency_code)
    amount = validate_amount(amount)

    portfolio = get_portfolio(user)
    rates = get_rates()

    portfolio.buy_currency(code, amount, rates)
    _save_portfolio(portfolio)

    rate = rates.get(code, 1.0)
    cost_usd = amount * rate

    return {
        "operation": "buy",
        "currency": code,
        "amount": amount,
        "rate": rate,
        "cost_usd": cost_usd,
        "portfolio": portfolio.get_portfolio_info(),
    }


def sell_currency(user: User, currency_code: str, amount: float) -> dict:
    """Продать валюту за USD.

    Args:
        user: Объект пользователя.
        currency_code: Код продаваемой валюты.
        amount: Количество продаваемой валюты.

    Returns:
        Результат операции.
    """
    require_login(user)
    code = validate_currency_code(currency_code)
    amount = validate_amount(amount)

    portfolio = get_portfolio(user)
    rates = get_rates()

    portfolio.sell_currency(code, amount, rates)
    _save_portfolio(portfolio)

    rate = rates.get(code, 1.0)
    received_usd = amount * rate

    return {
        "operation": "sell",
        "currency": code,
        "amount": amount,
        "rate": rate,
        "received_usd": received_usd,
        "portfolio": portfolio.get_portfolio_info(),
    }


# =============================================================================
# Exchange Rates
# =============================================================================


def get_exchange_rate(currency_code: str) -> dict:
    """Получить курс валюты.

    Args:
        currency_code: Код валюты.

    Returns:
        Информация о курсе.
    """
    code = validate_currency_code(currency_code)
    rate = get_rate(code)
    return {
        "currency": code,
        "rate_to_usd": rate,
        "base_currency": "USD",
    }


def get_all_rates() -> dict:
    """Получить все курсы валют.

    Returns:
        Информация о всех курсах.
    """
    return get_rates_info()


def get_exchange_rate_between(from_currency: str, to_currency: str) -> dict:
    """Получить курс обмена между двумя валютами.

    Args:
        from_currency: Исходная валюта.
        to_currency: Целевая валюта.

    Returns:
        Информация о курсе обмена.
    """
    from_code = validate_currency_code(from_currency)
    to_code = validate_currency_code(to_currency)

    rates_info = get_rates_info()
    rates = rates_info["rates"]
    updated_at = rates_info["updated_at"]

    if from_code not in rates:
        raise ValueError(f"Курс для валюты {from_code} не найден")
    if to_code not in rates:
        raise ValueError(f"Курс для валюты {to_code} не найден")

    # Конвертация через USD
    from_rate = rates[from_code]
    to_rate = rates[to_code]
    exchange_rate = from_rate / to_rate

    return {
        "from_currency": from_code,
        "to_currency": to_code,
        "rate": exchange_rate,
        "description": f"1 {from_code} = {exchange_rate:.6f} {to_code}",
        "updated_at": updated_at,
        "base_currency": rates_info.get("base_currency", "USD"),
    }
