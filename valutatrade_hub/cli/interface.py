"""Интерфейс командной строки.

CLI является единственной точкой входа для пользовательских команд.
Бизнес-логика вызывается из core/usecases.py.
"""

import argparse
import json
import sys
from pathlib import Path

from valutatrade_hub.core import usecases
from valutatrade_hub.core.models import User

# Файл сессии
SESSION_FILE = Path(__file__).parent.parent.parent / "data" / ".session"

# Текущий залогиненный пользователь (None = не авторизован)
_current_user: User | None = None


def _save_session(username: str) -> None:
    """Сохранить сессию пользователя."""
    SESSION_FILE.write_text(json.dumps({"username": username}), encoding="utf-8")


def _load_session() -> str | None:
    """Загрузить сессию пользователя."""
    if SESSION_FILE.exists():
        try:
            data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
            return data.get("username")
        except (json.JSONDecodeError, KeyError):
            return None
    return None


def _clear_session() -> None:
    """Очистить сессию."""
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()


def _restore_session_user() -> None:
    """Восстановить пользователя из сессии."""
    global _current_user
    username = _load_session()
    if username:
        try:
            # Восстанавливаем пользователя без повторной проверки пароля
            users_data = usecases.load_json("users.json")
            for u in users_data:
                if u["username"] == username:
                    _current_user = usecases._restore_user(u)
                    return
        except Exception:
            # Если не удалось восстановить, очищаем сессию
            _clear_session()


def _print_error(message: str) -> None:
    """Вывести сообщение об ошибке."""
    print(f"Ошибка: {message}")


def _print_success(message: str) -> None:
    """Вывести сообщение об успехе."""
    print(f"Успех: {message}")


# =============================================================================
# Commands
# =============================================================================


def cmd_register(args: argparse.Namespace) -> None:
    """Команда register — создание нового пользователя.

    Аргументы:
        --username <str> — обязателен, не пустой, уникален.
        --password <str> — обязателен, длина ≥ 4.
    """
    try:
        user = usecases.register_user(args.username, args.password)
        _print_success(
            f"Пользователь '{user.username}' успешно зарегистрирован (ID: {user.user_id})"
        )
    except ValueError as e:
        _print_error(str(e))


def cmd_login(args: argparse.Namespace) -> None:
    """Команда login — авторизация пользователя.

    Аргументы:
        --username <str> — обязателен.
        --password <str> — обязателен.
    """
    global _current_user
    try:
        user = usecases.login_user(args.username, args.password)
        _current_user = user
        _save_session(user.username)
        _print_success(f"Добро пожаловать, {user.username}!")
    except ValueError as e:
        _print_error(str(e))


def cmd_logout(args: argparse.Namespace) -> None:
    """Команда logout — выход из системы."""
    global _current_user
    if _current_user:
        username = _current_user.username
        _current_user = None
        _clear_session()
        _print_success(f"До свидания, {username}!")
    else:
        _print_error("Вы не авторизованы.")


def cmd_show_portfolio(args: argparse.Namespace) -> None:
    """Команда show-portfolio — показать портфель пользователя.

    Аргументы:
        --base <str> — базовая валюта (необязательно, по умолчанию USD).
    """
    if _current_user is None:
        _print_error("Требуется авторизация. Выполните команду login.")
        return

    try:
        base = args.base if hasattr(args, "base") and args.base else "USD"
        info = usecases.get_portfolio_info(_current_user, base)

        print(f"\n{'='*50}")
        print(f"Портфель пользователя: {info['username']} (ID: {info['user_id']})")
        print(f"{'='*50}")

        if not info["wallets"]:
            print("\nКошельков нет. Используйте команду 'deposit' для пополнения.")
        else:
            print("\nКошельки:")
            print(f"{'Валюта':<10} {'Баланс':>15} {'Стоимость в ' + base:>20}")
            print("-" * 50)
            for code, wallet_info in info["wallets"].items():
                balance = wallet_info["balance"]
                value_in_base = wallet_info["value_in_base"]
                print(f"{code:<10} {balance:>15.4f} {value_in_base:>20.4f}")

            print("-" * 50)
            print(f"{'ИТОГО':<10} {'':<15} {info['total_value']:>20.4f} {base}")

        print(f"{'='*50}\n")
    except (ValueError, PermissionError) as e:
        _print_error(str(e))


def cmd_buy(args: argparse.Namespace) -> None:
    """Команда buy — купить валюту за USD.

    Аргументы:
        --currency <str> — код покупаемой валюты.
        --amount <float> — количество покупаемой валюты.
    """
    if _current_user is None:
        _print_error("Требуется авторизация. Выполните команду login.")
        return

    try:
        result = usecases.buy_currency(_current_user, args.currency, args.amount)

        print(f"\n{'='*50}")
        print("Покупка валюты выполнена успешно!")
        print(f"{'='*50}")
        print(f"Валюта:          {result['currency']}")
        print(f"Количество:      {result['amount']:.4f}")
        print(f"Курс к USD:      {result['rate']:.4f}")
        print(f"Стоимость в USD: {result['cost_usd']:.2f}")
        print(f"{'='*50}\n")

        _print_success(f"Куплено {result['amount']:.4f} {result['currency']} за {result['cost_usd']:.2f} USD")
    except (ValueError, PermissionError) as e:
        _print_error(str(e))


def cmd_sell(args: argparse.Namespace) -> None:
    """Команда sell — продать валюту за USD.

    Аргументы:
        --currency <str> — код продаваемой валюты.
        --amount <float> — количество продаваемой валюты.
    """
    if _current_user is None:
        _print_error("Требуется авторизация. Выполните команду login.")
        return

    try:
        result = usecases.sell_currency(_current_user, args.currency, args.amount)

        print(f"\n{'='*50}")
        print("Продажа валюты выполнена успешно!")
        print(f"{'='*50}")
        print(f"Валюта:           {result['currency']}")
        print(f"Количество:       {result['amount']:.4f}")
        print(f"Курс к USD:       {result['rate']:.4f}")
        print(f"Получено USD:     {result['received_usd']:.2f}")
        print(f"{'='*50}\n")

        _print_success(f"Продано {result['amount']:.4f} {result['currency']} за {result['received_usd']:.2f} USD")
    except (ValueError, PermissionError) as e:
        _print_error(str(e))


# =============================================================================
# CLI Setup
# =============================================================================


def create_parser() -> argparse.ArgumentParser:
    """Создать парсер командной строки."""
    parser = argparse.ArgumentParser(
        prog="valutatrade",
        description="ValutaTrade Hub — система управления валютными портфелями",
    )
    subparsers = parser.add_subparsers(dest="command", help="Доступные команды")

    # --- register ---
    register_parser = subparsers.add_parser(
        "register",
        help="Регистрация нового пользователя",
    )
    register_parser.add_argument(
        "--username",
        type=str,
        required=True,
        help="Имя пользователя (уникальное, не пустое)",
    )
    register_parser.add_argument(
        "--password",
        type=str,
        required=True,
        help="Пароль (минимум 4 символа)",
    )
    register_parser.set_defaults(func=cmd_register)

    # --- login ---
    login_parser = subparsers.add_parser(
        "login",
        help="Авторизация пользователя",
    )
    login_parser.add_argument(
        "--username",
        type=str,
        required=True,
        help="Имя пользователя",
    )
    login_parser.add_argument(
        "--password",
        type=str,
        required=True,
        help="Пароль",
    )
    login_parser.set_defaults(func=cmd_login)

    # --- logout ---
    logout_parser = subparsers.add_parser(
        "logout",
        help="Выход из системы",
    )
    logout_parser.set_defaults(func=cmd_logout)

    # --- show-portfolio ---
    show_portfolio_parser = subparsers.add_parser(
        "show-portfolio",
        help="Показать портфель пользователя",
    )
    show_portfolio_parser.add_argument(
        "--base",
        type=str,
        default="USD",
        help="Базовая валюта для расчёта (по умолчанию USD)",
    )
    show_portfolio_parser.set_defaults(func=cmd_show_portfolio)

    # --- buy ---
    buy_parser = subparsers.add_parser(
        "buy",
        help="Купить валюту за USD",
    )
    buy_parser.add_argument(
        "--currency",
        type=str,
        required=True,
        help="Код покупаемой валюты (например, BTC, EUR)",
    )
    buy_parser.add_argument(
        "--amount",
        type=float,
        required=True,
        help="Количество покупаемой валюты",
    )
    buy_parser.set_defaults(func=cmd_buy)

    # --- sell ---
    sell_parser = subparsers.add_parser(
        "sell",
        help="Продать валюту за USD",
    )
    sell_parser.add_argument(
        "--currency",
        type=str,
        required=True,
        help="Код продаваемой валюты (например, BTC, EUR)",
    )
    sell_parser.add_argument(
        "--amount",
        type=float,
        required=True,
        help="Количество продаваемой валюты",
    )
    sell_parser.set_defaults(func=cmd_sell)

    return parser


def run_cli() -> None:
    """Запуск CLI интерфейса."""
    # Восстанавливаем сессию перед выполнением команды
    _restore_session_user()

    parser = create_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    # Выполнение команды
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


def main_menu() -> None:
    """Главное меню приложения (интерактивный режим)."""
    print("ValutaTrade Hub v0.1.0")
    print("=" * 40)
    print("Используйте: python main.py <команда> [аргументы]")
    print("Для справки: python main.py --help")
