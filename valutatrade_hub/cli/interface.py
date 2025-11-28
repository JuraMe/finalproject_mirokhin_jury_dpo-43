"""Интерфейс командной строки.

CLI является единственной точкой входа для пользовательских команд.
Бизнес-логика вызывается из core/usecases.py.
"""

import argparse
import json
import sys
from pathlib import Path

from valutatrade_hub.core import usecases
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
    StorageError,
)
from valutatrade_hub.core.models import User
from valutatrade_hub.parser_service.api_clients import (
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.config import get_parser_config
from valutatrade_hub.parser_service.storage import read_rates_cache
from valutatrade_hub.parser_service.updater import RatesUpdater, update_all_rates

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
            f"Пользователь '{user.username}' "
            f"успешно зарегистрирован (ID: {user.user_id})"
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

        print(f"\n{'=' * 50}")
        print(f"Портфель пользователя: {info['username']} (ID: {info['user_id']})")
        print(f"{'=' * 50}")

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

        print(f"{'=' * 50}\n")
    except (ValueError, PermissionError) as e:
        _print_error(str(e))


def cmd_deposit(args: argparse.Namespace) -> None:
    """Команда deposit — пополнить кошелёк валютой.

    Аргументы:
        --currency <str> — код валюты.
        --amount <float> — сумма пополнения.
    """
    if _current_user is None:
        _print_error("Требуется авторизация. Выполните команду login.")
        return

    try:
        result = usecases.deposit(_current_user, args.currency, args.amount)

        print(f"\n{'=' * 50}")
        print("Пополнение кошелька выполнено успешно!")
        print(f"{'=' * 50}")
        print(f"Валюта:    {result['currency_code']}")
        print(f"Баланс:    {result['balance']:.4f}")
        print(f"{'=' * 50}\n")

        _print_success(
            f"Добавлено {args.amount:.4f} {args.currency}. "
            f"Новый баланс: {result['balance']:.4f} {result['currency_code']}"
        )

    except CurrencyNotFoundError as e:
        _print_error(str(e))
        print(
            "Подсказка: поддерживаемые валюты — USD, EUR, GBP, RUB, CNY, JPY, BTC, ETH"
        )

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

        print(f"\n{'=' * 50}")
        print("Покупка валюты выполнена успешно!")
        print(f"{'=' * 50}")
        print(f"Валюта:          {result['currency']}")
        print(f"Количество:      {result['amount']:.4f}")
        print(f"Курс к USD:      {result['rate']:.4f}")
        print(f"Стоимость в USD: {result['cost_usd']:.2f}")
        print(f"{'=' * 50}\n")

        _print_success(
            f"Куплено {result['amount']:.4f} {result['currency']} "
            f"за {result['cost_usd']:.2f} USD"
        )

    except CurrencyNotFoundError as e:
        _print_error(str(e))
        print(
            "Подсказка: поддерживаемые валюты — USD, EUR, GBP, RUB, CNY, JPY, BTC, ETH"
        )
        print("Используйте 'valutatrade get-rate --help' для получения курсов")

    except InsufficientFundsError as e:
        _print_error(str(e))

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

        print(f"\n{'=' * 50}")
        print("Продажа валюты выполнена успешно!")
        print(f"{'=' * 50}")
        print(f"Валюта:           {result['currency']}")
        print(f"Количество:       {result['amount']:.4f}")
        print(f"Курс к USD:       {result['rate']:.4f}")
        print(f"Получено USD:     {result['received_usd']:.2f}")
        print(f"{'=' * 50}\n")

        _print_success(
            f"Продано {result['amount']:.4f} {result['currency']} "
            f"за {result['received_usd']:.2f} USD"
        )

    except CurrencyNotFoundError as e:
        _print_error(str(e))
        print(
            "Подсказка: поддерживаемые валюты — USD, EUR, GBP, RUB, CNY, JPY, BTC, ETH"
        )
        print("Используйте 'valutatrade get-rate --help' для получения курсов")

    except InsufficientFundsError as e:
        _print_error(str(e))

    except (ValueError, PermissionError) as e:
        _print_error(str(e))


def cmd_get_rate(args: argparse.Namespace) -> None:
    """Команда get-rate — получить курс обмена валют.

    Аргументы:
        --from <str> — исходная валюта (например, USD).
        --to <str> — целевая валюта (например, BTC).
    """
    try:
        result = usecases.get_exchange_rate_between(args.from_currency, args.to)

        print(f"\n{'=' * 50}")
        print("Курс обмена валют")
        print(f"{'=' * 50}")
        print(f"{result['description']}")
        print(f"\nИсходная валюта:  {result['from_currency']}")
        print(f"Целевая валюта:   {result['to_currency']}")
        print(f"Курс обмена:      {result['rate']:.6f}")
        print(f"Базовая валюта:   {result['base_currency']}")

        if result["updated_at"]:
            print(f"Обновлено:        {result['updated_at']}")
        else:
            print("Обновлено:        Дефолтные курсы")

        print(f"{'=' * 50}\n")

    except CurrencyNotFoundError as e:
        _print_error(str(e))
        print(
            "Подсказка: поддерживаемые валюты — USD, EUR, GBP, RUB, CNY, JPY, BTC, ETH"
        )
        print("Используйте 'valutatrade get-rate --from USD --to BTC' для примера")

    except ApiRequestError as e:
        _print_error(str(e))
        print("Совет: повторите попытку позже или проверьте подключение к сети")

    except ValueError as e:
        _print_error(str(e))


def cmd_show_rates(args: argparse.Namespace) -> None:
    """Команда show-rates — показать актуальные курсы из локального кеша.

    Аргументы:
        --currency <str> — показать курс только для указанной валюты
        --top <int> — показать N самых дорогих криптовалют
        --base <str> — показать курсы относительно указанной базы
    """
    try:
        # Чтение данных из кеша
        cache_data = read_rates_cache()

        # Определение формата файла и извлечение данных
        if "pairs" in cache_data:
            # Новый формат
            pairs = cache_data["pairs"]
            last_refresh = cache_data.get("last_refresh")
        else:
            # Старый формат - конвертируем в новый
            old_rates = cache_data.get("rates", {})
            base_currency = cache_data.get("base_currency", "USD")
            updated_at = cache_data.get("updated_at")

            pairs = {}
            for currency, rate in old_rates.items():
                if currency != base_currency:
                    pair_key = f"{currency}_{base_currency}"
                    pairs[pair_key] = {
                        "rate": float(rate),
                        "updated_at": updated_at,
                        "source": "legacy",
                    }
            last_refresh = updated_at

        if not pairs:
            print("\nКеш курсов пуст.")
            print("Выполните команду 'update-rates' для получения актуальных данных.")
            return

        # Применение фильтров
        filtered_pairs = {}

        # Фильтр --currency
        if hasattr(args, "currency") and args.currency:
            currency_upper = args.currency.upper()
            for pair_key, pair_data in pairs.items():
                from_currency, to_currency = pair_key.split("_")
                if from_currency == currency_upper:
                    filtered_pairs[pair_key] = pair_data
        else:
            filtered_pairs = pairs.copy()

        # Фильтр --top (для криптовалют)
        if hasattr(args, "top") and args.top:
            config = get_parser_config()
            crypto_pairs = {}
            for pair_key, pair_data in filtered_pairs.items():
                from_currency, _ = pair_key.split("_")
                if from_currency in config.CRYPTO_CURRENCIES:
                    crypto_pairs[pair_key] = pair_data

            # Сортировка по убыванию курса и ограничение топа
            sorted_crypto = sorted(
                crypto_pairs.items(), key=lambda x: x[1]["rate"], reverse=True
            )
            filtered_pairs = dict(sorted_crypto[: args.top])

        # Пересчет относительно другой базы (--base)
        if hasattr(args, "base") and args.base:
            base_upper = args.base.upper()

            # Находим курс базовой валюты к USD
            base_to_usd = None
            for pair_key, pair_data in pairs.items():
                from_currency, to_currency = pair_key.split("_")
                if from_currency == base_upper and to_currency == "USD":
                    base_to_usd = pair_data["rate"]
                    break

            if base_to_usd is None:
                _print_error(
                    f"Не удалось найти курс {base_upper}_USD для пересчета. "
                    f"Доступные валюты: {', '.join(set(p.split('_')[0] for p in pairs.keys()))}"
                )
                return

            # Пересчет всех курсов относительно новой базы
            recalculated_pairs = {}
            for pair_key, pair_data in filtered_pairs.items():
                from_currency, to_currency = pair_key.split("_")
                if from_currency != base_upper:  # Не показываем базу к самой себе
                    # Курс от валюты к USD, затем к новой базе
                    rate_to_usd = pair_data["rate"]
                    rate_to_base = rate_to_usd / base_to_usd
                    new_pair_key = f"{from_currency}_{base_upper}"
                    recalculated_pairs[new_pair_key] = {
                        "rate": rate_to_base,
                        "updated_at": pair_data["updated_at"],
                        "source": pair_data.get("source", "unknown"),
                    }
            filtered_pairs = recalculated_pairs

        if not filtered_pairs:
            print("\nНе найдено курсов по заданным фильтрам.")
            return

        # Сортировка по алфавиту (по умолчанию)
        sorted_pairs = sorted(filtered_pairs.items())

        # Вывод отформатированной таблицы
        print("\n" + "=" * 80)
        print("Актуальные курсы валют (из локального кеша)")
        if last_refresh:
            print(f"Последнее обновление: {last_refresh}")
        print("=" * 80)

        # Заголовок таблицы
        print(
            f"{'Пара':<15} {'Курс':>18} {'Источник':<20} {'Обновлено':<25}"
        )
        print("-" * 80)

        # Вывод данных
        for pair_key, pair_data in sorted_pairs:
            rate = pair_data["rate"]
            source = pair_data.get("source", "unknown")
            updated_at = pair_data.get("updated_at", "N/A")

            print(
                f"{pair_key:<15} {rate:>18,.6f} {source:<20} {updated_at:<25}"
            )

        print("-" * 80)
        print(f"Всего пар: {len(sorted_pairs)}")
        print("=" * 80 + "\n")

    except FileNotFoundError:
        _print_error("Файл кеша rates.json не найден.")
        print("Выполните команду 'update-rates' для создания кеша.")

    except StorageError as e:
        _print_error(f"Ошибка чтения кеша: {str(e)}")

    except Exception as e:
        _print_error(f"Неожиданная ошибка: {str(e)}")
        print("Совет: проверьте формат файла rates.json")


def cmd_update_rates(args: argparse.Namespace) -> None:
    """Команда update-rates — обновить курсы валют из внешних API.

    Получает актуальные курсы от CoinGecko и/или ExchangeRate-API,
    сохраняет в кеш и историю.

    Аргументы:
        --source <str> (опционально) — источник данных:
            - 'coingecko' — только криптовалюты
            - 'exchangerate' — только фиат
            - по умолчанию — все источники
    """
    try:
        # Определение источника
        source = args.source if hasattr(args, "source") and args.source else None

        # Вывод заголовка
        print("\nОбновление курсов валют...")
        if source:
            source_name = {
                "coingecko": "CoinGecko (криптовалюты)",
                "exchangerate": "ExchangeRate-API (фиат)",
            }.get(source, source)
            print(f"Источник: {source_name}")
        else:
            print("Источники: все (CoinGecko + ExchangeRate-API)")
        print("=" * 60)

        # Инициализация RatesUpdater с выбранными клиентами
        if source:
            # Создание клиента для конкретного источника
            clients = []
            if source == "coingecko":
                clients.append(CoinGeckoClient())
            elif source == "exchangerate":
                clients.append(ExchangeRateApiClient())
            else:
                _print_error(
                    f"Неизвестный источник: {source}. "
                    "Допустимые значения: coingecko, exchangerate"
                )
                return

            # Использование RatesUpdater с выбранными клиентами
            updater = RatesUpdater(clients=clients)
            stats = updater.run_update()
        else:
            # Обновление от всех источников
            stats = update_all_rates()

        # Вывод результатов
        print("\n" + "=" * 60)
        print("Результаты обновления:")
        print("=" * 60)
        print(f"  Всего пар обновлено:      {stats['total_count']}")
        print(f"  Криптовалютные пары:      {stats['crypto_count']}")
        print(f"  Фиатные валютные пары:    {stats['fiat_count']}")
        if "success" in stats:
            print(f"  Успешных источников:      {stats['success']}")
            print(f"  Неудачных источников:     {stats['failed']}")
        print(f"  Ошибок при обновлении:    {stats['errors']}")
        print("=" * 60)

        if stats["errors"] == 0:
            _print_success(
                f"Курсы успешно обновлены! "
                f"Обновлено {stats['total_count']} валютных пар."
            )
        else:
            print(
                "\nВнимание: при обновлении произошли ошибки. "
                "Проверьте логи для деталей."
            )

    except ApiRequestError as e:
        _print_error(f"Ошибка при запросе к API: {str(e)}")
        print("Совет: проверьте подключение к интернету и API ключи")

    except StorageError as e:
        _print_error(f"Ошибка при сохранении данных: {str(e)}")
        print("Совет: проверьте права доступа к директории data/")

    except Exception as e:
        _print_error(f"Неожиданная ошибка: {str(e)}")
        print("Совет: повторите попытку или обратитесь к документации")


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

    # --- deposit ---
    deposit_parser = subparsers.add_parser(
        "deposit",
        help="Пополнить кошелёк валютой",
    )
    deposit_parser.add_argument(
        "--currency",
        type=str,
        required=True,
        help="Код валюты (например, USD, EUR, BTC)",
    )
    deposit_parser.add_argument(
        "--amount",
        type=float,
        required=True,
        help="Сумма пополнения",
    )
    deposit_parser.set_defaults(func=cmd_deposit)

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

    # --- get-rate ---
    get_rate_parser = subparsers.add_parser(
        "get-rate",
        help="Получить курс обмена валют",
    )
    get_rate_parser.add_argument(
        "--from",
        dest="from_currency",
        type=str,
        required=True,
        help="Исходная валюта (например, USD)",
    )
    get_rate_parser.add_argument(
        "--to",
        type=str,
        required=True,
        help="Целевая валюта (например, BTC)",
    )
    get_rate_parser.set_defaults(func=cmd_get_rate)

    # --- show-rates ---
    show_rates_parser = subparsers.add_parser(
        "show-rates",
        help="Показать актуальные курсы из локального кеша",
    )
    show_rates_parser.add_argument(
        "--currency",
        type=str,
        help="Показать курс только для указанной валюты (например, BTC)",
    )
    show_rates_parser.add_argument(
        "--top",
        type=int,
        help="Показать N самых дорогих криптовалют (например, --top 3)",
    )
    show_rates_parser.add_argument(
        "--base",
        type=str,
        help="Показать курсы относительно указанной базовой валюты (например, EUR)",
    )
    show_rates_parser.set_defaults(func=cmd_show_rates)

    # --- update-rates ---
    update_rates_parser = subparsers.add_parser(
        "update-rates",
        help="Обновить курсы валют из внешних API (CoinGecko, ExchangeRate-API)",
    )
    update_rates_parser.add_argument(
        "--source",
        type=str,
        choices=["coingecko", "exchangerate"],
        help="Источник данных: 'coingecko' (криптовалюты) или 'exchangerate' (фиат). "
        "По умолчанию обновляются все источники.",
    )
    update_rates_parser.set_defaults(func=cmd_update_rates)

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
