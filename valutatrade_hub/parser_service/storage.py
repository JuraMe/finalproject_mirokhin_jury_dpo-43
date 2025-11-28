"""Модуль для работы с хранилищем курсов валют.

Операции чтения/записи файла exchange_rates.json:
- Сохранение исторических данных
- Получение последних курсов
- Управление историей изменений.
"""

import json
import logging
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from valutatrade_hub.core.exceptions import StorageError
from valutatrade_hub.parser_service.config import ParserConfig, get_parser_config

# Настройка логирования
logger = logging.getLogger(__name__)

# =============================================================================
# Validation patterns
# =============================================================================

CURRENCY_CODE_PATTERN = re.compile(r"^[A-Z]{2,5}$")


def validate_currency_code(code: str) -> bool:
    """Валидация формата кода валюты.

    Args:
        code: Код валюты для проверки (например, "BTC", "EUR")

    Returns:
        True если код валиден, False иначе.

    Правила валидации:
        - Должен быть в верхнем регистре (UPPERCASE)
        - Длина 2-5 символов
        - Только буквы A-Z
    """
    return bool(CURRENCY_CODE_PATTERN.match(code))


def generate_record_id(from_currency: str, to_currency: str, timestamp: str) -> str:
    """Генерация уникального ID записи для exchange_rates.json.

    Args:
        from_currency: Код исходной валюты (например, "BTC")
        to_currency: Код целевой валюты (например, "USD")
        timestamp: ISO 8601 UTC timestamp

    Returns:
        ID записи в формате: {FROM}_{TO}_{timestamp}

    Example:
        >>> generate_record_id("BTC", "USD", "2025-10-10T12:00:01Z")
        "BTC_USD_2025-10-10T12:00:01Z"

    Raises:
        ValueError: Если коды валют невалидны.
    """
    if not validate_currency_code(from_currency):
        raise ValueError(f"Invalid FROM currency code: {from_currency}")
    if not validate_currency_code(to_currency):
        raise ValueError(f"Invalid TO currency code: {to_currency}")

    return f"{from_currency}_{to_currency}_{timestamp}"


def parse_pair(pair: str) -> tuple[str, str]:
    """Парсинг строки валютной пары в FROM и TO валюты.

    Args:
        pair: Валютная пара в формате "FROM_TO" (например, "BTC_USD")

    Returns:
        Кортеж (from_currency, to_currency)

    Example:
        >>> parse_pair("BTC_USD")
        ("BTC", "USD")

    Raises:
        ValueError: Если формат пары невалиден.
    """
    parts = pair.split("_")
    if len(parts) != 2:
        raise ValueError(f"Invalid pair format: {pair}. Expected FROM_TO")

    from_currency, to_currency = parts
    if not validate_currency_code(from_currency):
        raise ValueError(f"Invalid FROM currency in pair: {from_currency}")
    if not validate_currency_code(to_currency):
        raise ValueError(f"Invalid TO currency in pair: {to_currency}")

    return from_currency, to_currency


# =============================================================================
# exchange_rates.json - История курсов
# =============================================================================


def read_exchange_rates_history(config: ParserConfig | None = None) -> dict[str, Any]:
    """Чтение файла истории exchange_rates.json.

    Args:
        config: Экземпляр ParserConfig (опционально)

    Returns:
        Словарь со структурой:
        {
            "history": [
                {
                    "id": "BTC_USD_2025-10-10T12:00:01Z",
                    "from": "BTC",
                    "to": "USD",
                    "rate": 59337.21,
                    "updated_at": "2025-10-10T12:00:01Z",
                    "source": "CoinGecko",
                    "raw_id": "bitcoin",
                    "request_ms": 234,
                    "status_code": 200,
                    "etag": "abc123"
                },
                ...
            ],
            "last_updated": "2025-10-10T12:00:01Z"
        }

    Raises:
        StorageError: Если чтение файла не удалось или JSON невалиден.
    """
    cfg = config or get_parser_config()
    filepath = Path(cfg.HISTORY_FILE_PATH)

    try:
        if not filepath.exists():
            logger.warning(
                f"History file not found: {filepath}. Creating default structure."
            )
            return {"history": [], "last_updated": None}

        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        # Валидация структуры
        if not isinstance(data, dict):
            raise StorageError(
                f"Invalid history file format: expected dict, got {type(data)}"
            )

        if "history" not in data:
            logger.warning("Missing 'history' key in file, initializing empty history")
            data["history"] = []

        logger.debug(
            f"✓ Loaded {len(data.get('history', []))} history records from {filepath}"
        )
        return data

    except json.JSONDecodeError as e:
        raise StorageError(f"Invalid JSON in history file: {str(e)}") from e
    except OSError as e:
        raise StorageError(f"Error reading history file: {str(e)}") from e


def write_exchange_rates_history(
    data: dict[str, Any], config: ParserConfig | None = None
) -> None:
    """Запись файла истории exchange_rates.json с атомарной записью.

    Использует паттерн temp file → rename для атомарности.

    Args:
        data: Данные истории для записи
        config: Экземпляр ParserConfig (опционально)

    Raises:
        StorageError: Если запись не удалась.
    """
    cfg = config or get_parser_config()
    filepath = Path(cfg.HISTORY_FILE_PATH)

    try:
        # Убедиться что директория существует
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Сначала записать во временный файл
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=filepath.parent,
            delete=False,
            suffix=".tmp",
        ) as tmp_file:
            json.dump(data, tmp_file, indent=2, ensure_ascii=False)
            tmp_path = tmp_file.name

        # Атомарное переименование
        os.replace(tmp_path, filepath)

        logger.debug(
            f"✓ Saved {len(data.get('history', []))} history records to {filepath}"
        )

    except OSError as e:
        # Очистить временный файл если он существует
        if "tmp_path" in locals() and Path(tmp_path).exists():
            Path(tmp_path).unlink()
        raise StorageError(f"Error writing history file: {str(e)}") from e


def add_history_record(
    pair: str,
    rate: float,
    source: str,
    timestamp: str | None = None,
    raw_id: str | None = None,
    request_ms: int | None = None,
    status_code: int = 200,
    etag: str | None = None,
    config: ParserConfig | None = None,
) -> dict[str, Any]:
    """Добавление новой записи в историю exchange_rates.json.

    Args:
        pair: Валютная пара в формате "FROM_TO" (например, "BTC_USD")
        rate: Значение курса обмена
        source: Название источника данных (например, "CoinGecko")
        timestamp: ISO 8601 UTC timestamp (текущее время если None)
        raw_id: Оригинальный ID из внешнего API (опционально)
        request_ms: Длительность запроса в миллисекундах (опционально)
        status_code: HTTP статус код (по умолчанию: 200)
        etag: Значение заголовка ETag (опционально)
        config: Экземпляр ParserConfig (опционально)

    Returns:
        Созданный словарь записи

    Raises:
        StorageError: Если валидация не удалась или запись не удалась.
    """
    # Парсинг и валидация пары
    from_currency, to_currency = parse_pair(pair)

    # Генерация timestamp если не предоставлен
    if timestamp is None:
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    # Генерация ID записи
    record_id = generate_record_id(from_currency, to_currency, timestamp)

    # Создание записи
    record = {
        "id": record_id,
        "from": from_currency,
        "to": to_currency,
        "rate": float(rate),
        "updated_at": timestamp,
        "source": source,
    }

    # Добавление опциональных мета-полей
    if raw_id is not None:
        record["raw_id"] = raw_id
    if request_ms is not None:
        record["request_ms"] = request_ms
    if status_code is not None:
        record["status_code"] = status_code
    if etag is not None:
        record["etag"] = etag

    # Чтение текущей истории
    history_data = read_exchange_rates_history(config)

    # Добавление новой записи
    history_data["history"].append(record)
    history_data["last_updated"] = timestamp

    # Запись обратно
    write_exchange_rates_history(history_data, config)

    logger.info(f"✓ Added history record: {record_id}")
    return record


# =============================================================================
# rates.json - Кеш текущих курсов
# =============================================================================


def read_rates_cache(config: ParserConfig | None = None) -> dict[str, Any]:
    """Чтение файла кеша rates.json.

    Args:
        config: Экземпляр ParserConfig (опционально)

    Returns:
        Словарь со структурой:
        {
            "pairs": {
                "EUR_USD": {
                    "rate": 1.0786,
                    "updated_at": "2025-10-10T12:00:01Z",
                    "source": "ExchangeRate-API"
                },
                ...
            },
            "last_refresh": "2025-10-10T12:00:01Z"
        }

    Raises:
        StorageError: Если чтение файла не удалось или JSON невалиден.
    """
    cfg = config or get_parser_config()
    filepath = Path(cfg.RATES_FILE_PATH)

    try:
        if not filepath.exists():
            logger.warning(
                f"Cache file not found: {filepath}. Creating default structure."
            )
            return {"pairs": {}, "last_refresh": None}

        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        # Поддержка миграции старого формата
        if "rates" in data and "pairs" not in data:
            logger.info("Migrating old rates.json format to new format")
            # Старый формат: {"rates": {"USD": 1.0, "EUR": 1.08},
            #                 "base_currency": "USD", ...}
            # Новый формат: {"pairs": {"EUR_USD": {"rate": 1.08, ...}}, ...}
            old_rates = data.get("rates", {})
            base_currency = data.get("base_currency", "USD")
            updated_at = data.get(
                "updated_at", datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            )

            pairs = {}
            for currency, rate in old_rates.items():
                if currency != base_currency:
                    pair_key = f"{currency}_{base_currency}"
                    pairs[pair_key] = {
                        "rate": float(rate),
                        "updated_at": updated_at,
                        "source": "migrated",
                    }

            data = {"pairs": pairs, "last_refresh": updated_at}

        # Валидация структуры
        if not isinstance(data, dict):
            raise StorageError(
                f"Invalid cache file format: expected dict, got {type(data)}"
            )

        if "pairs" not in data:
            logger.warning("Missing 'pairs' key in file, initializing empty pairs")
            data["pairs"] = {}

        logger.debug(
            f"✓ Loaded {len(data.get('pairs', {}))} cached pairs from {filepath}"
        )
        return data

    except json.JSONDecodeError as e:
        raise StorageError(f"Invalid JSON in cache file: {str(e)}") from e
    except OSError as e:
        raise StorageError(f"Error reading cache file: {str(e)}") from e


def write_rates_cache(
    data: dict[str, Any], config: ParserConfig | None = None
) -> None:
    """Запись файла кеша rates.json с атомарной записью.

    Использует паттерн temp file → rename для атомарности.

    Args:
        data: Данные кеша для записи
        config: Экземпляр ParserConfig (опционально)

    Raises:
        StorageError: Если запись не удалась.
    """
    cfg = config or get_parser_config()
    filepath = Path(cfg.RATES_FILE_PATH)

    try:
        # Убедиться что директория существует
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Сначала записать во временный файл
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=filepath.parent,
            delete=False,
            suffix=".tmp",
        ) as tmp_file:
            json.dump(data, tmp_file, indent=2, ensure_ascii=False)
            tmp_path = tmp_file.name

        # Атомарное переименование
        os.replace(tmp_path, filepath)

        logger.debug(f"✓ Saved {len(data.get('pairs', {}))} cached pairs to {filepath}")

    except OSError as e:
        # Очистить временный файл если он существует
        if "tmp_path" in locals() and Path(tmp_path).exists():
            Path(tmp_path).unlink()
        raise StorageError(f"Error writing cache file: {str(e)}") from e


def update_rates_cache(
    rates: dict[str, float],
    source: str,
    timestamp: str | None = None,
    config: ParserConfig | None = None,
) -> None:
    """Обновление кеша rates.json новыми курсами.

    Обновляет только если новый timestamp свежее кешированного.

    Args:
        rates: Словарь курсов в формате {"BTC_USD": 59337.21, ...}
        source: Название источника данных (например, "CoinGecko")
        timestamp: ISO 8601 UTC timestamp (текущее время если None)
        config: Экземпляр ParserConfig (опционально)

    Raises:
        StorageError: Если валидация не удалась или запись не удалась.
    """
    # Генерация timestamp если не предоставлен
    if timestamp is None:
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    # Чтение текущего кеша
    cache_data = read_rates_cache(config)

    # Обновление пар
    updated_count = 0
    for pair, rate in rates.items():
        # Валидация формата пары
        parse_pair(pair)  # Вызовет ValueError если невалидно

        # Проверка нужно ли обновление
        if pair in cache_data["pairs"]:
            cached_timestamp = cache_data["pairs"][pair].get("updated_at", "")
            if cached_timestamp >= timestamp:
                logger.debug(f"Skipping {pair}: cached data is fresher")
                continue

        # Обновление пары
        cache_data["pairs"][pair] = {
            "rate": float(rate),
            "updated_at": timestamp,
            "source": source,
        }
        updated_count += 1

    # Обновление last_refresh
    cache_data["last_refresh"] = timestamp

    # Запись обратно
    write_rates_cache(cache_data, config)

    logger.info(f"✓ Updated {updated_count} pairs in cache (source: {source})")
