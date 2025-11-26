"""Декораторы для логирования операций.

Содержит декоратор @log_action для трассировки доменных операций
(buy, sell, register, login).
"""

import functools
from typing import Any, Callable

from valutatrade_hub.logging_config import get_action_logger


def log_action(
    action_type: str | None = None, verbose: bool = False
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Декоратор для логирования доменных операций.

    Логирует операции BUY/SELL/REGISTER/LOGIN на уровне INFO.

    Структура лога:
        timestamp (ISO), action (BUY/SELL/REGISTER/LOGIN),
        username (или user_id), currency_code, amount,
        rate и base (если применимо),
        result (OK/ERROR), error_type/error_message при исключениях.

    Декоратор НЕ глотает исключения — пробрасывает дальше, но фиксирует их в лог.

    Args:
        action_type: Тип действия (BUY, SELL, REGISTER, LOGIN).
                     Если None, определяется автоматически из имени функции.
        verbose: Добавлять расширенный контекст (состояние "было→стало").

    Returns:
        Декоратор функции.

    Example:
        @log_action("BUY")
        def buy_currency(user: User, currency_code: str, amount: float) -> dict:
            # ... код операции
            pass

        # Лог: INFO 2025-10-09T12:05:22 BUY user='alice' currency='BTC' amount=0.0500 rate=59300.00 base='USD' result=OK
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Получаем логгер для действий
            logger = get_action_logger()

            # Определяем тип действия
            action = action_type
            if action is None:
                # Автоопределение из имени функции
                if "buy" in func.__name__.lower():
                    action = "BUY"
                elif "sell" in func.__name__.lower():
                    action = "SELL"
                elif "register" in func.__name__.lower():
                    action = "REGISTER"
                elif "login" in func.__name__.lower():
                    action = "LOGIN"
                else:
                    action = func.__name__.upper()

            # Извлекаем параметры из аргументов
            params = _extract_params(func.__name__, args, kwargs)

            # Формируем базовое сообщение
            log_parts = [action]

            # Добавляем пользователя
            if "user" in params:
                user = params["user"]
                if hasattr(user, "username"):
                    log_parts.append(f"user='{user.username}'")
                elif hasattr(user, "user_id"):
                    log_parts.append(f"user_id={user.user_id}")

            # Добавляем username для register/login
            if "username" in params:
                log_parts.append(f"user='{params['username']}'")

            # Добавляем валюту
            if "currency_code" in params:
                log_parts.append(f"currency='{params['currency_code']}'")

            # Добавляем количество
            if "amount" in params:
                log_parts.append(f"amount={params['amount']:.4f}")

            try:
                # Выполняем функцию
                result = func(*args, **kwargs)

                # Извлекаем данные из результата
                if isinstance(result, dict):
                    # Добавляем курс
                    if "rate" in result:
                        log_parts.append(f"rate={result['rate']:.2f}")

                    # Добавляем базовую валюту
                    if "base_currency" in result:
                        log_parts.append(f"base='{result['base_currency']}'")

                    # Verbose режим: добавляем детали
                    if verbose:
                        if "cost_usd" in result:
                            log_parts.append(f"cost={result['cost_usd']:.2f}")
                        if "received_usd" in result:
                            log_parts.append(f"received={result['received_usd']:.2f}")

                # Успешное выполнение
                log_parts.append("result=OK")

                # Логируем
                logger.info(" ".join(log_parts))

                return result

            except Exception as e:
                # Ошибка при выполнении
                error_type = type(e).__name__
                error_message = str(e)

                log_parts.append("result=ERROR")
                log_parts.append(f"error_type={error_type}")
                log_parts.append(f"error_message='{error_message}'")

                # Логируем ошибку
                logger.error(" ".join(log_parts))

                # Пробрасываем исключение дальше
                raise

        return wrapper

    return decorator


def _extract_params(func_name: str, args: tuple, kwargs: dict) -> dict[str, Any]:
    """Извлечь параметры из аргументов функции.

    Args:
        func_name: Имя функции.
        args: Позиционные аргументы.
        kwargs: Именованные аргументы.

    Returns:
        Словарь с извлечёнными параметрами.
    """
    params = {}

    # Параметры из kwargs
    params.update(kwargs)

    # Параметры из args (эвристика на основе имени функции)
    if "buy" in func_name or "sell" in func_name:
        # buy_currency(user, currency_code, amount)
        if len(args) >= 1:
            params["user"] = args[0]
        if len(args) >= 2:
            params["currency_code"] = args[1]
        if len(args) >= 3:
            params["amount"] = args[2]

    elif "register" in func_name or "login" in func_name:
        # register_user(username, password) / login_user(username, password)
        if len(args) >= 1:
            params["username"] = args[0]
        if len(args) >= 2:
            params["password"] = args[1]

    return params
