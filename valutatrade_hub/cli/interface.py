"""Интерфейс командной строки.

CLI является единственной точкой входа для пользовательских команд.
Бизнес-логика вызывается из core/usecases.py.
"""

import argparse
import sys

from valutatrade_hub.core import usecases
from valutatrade_hub.core.models import User

# Текущий залогиненный пользователь (None = не авторизован)
_current_user: User | None = None


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

    return parser


def run_cli() -> None:
    """Запуск CLI интерфейса."""
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
