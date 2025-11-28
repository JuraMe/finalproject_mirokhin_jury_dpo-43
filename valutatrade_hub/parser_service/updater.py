"""Модуль координации обновления курсов.

Главный модуль Parser Service, который:
- Получает курсы от API клиентов
- Сохраняет данные в историю и кеш
- Обрабатывает ошибки и логирование
"""

import logging
import time
from datetime import datetime

from valutatrade_hub.core.exceptions import ApiRequestError, StorageError
from valutatrade_hub.parser_service.api_clients import get_api_clients
from valutatrade_hub.parser_service.config import ParserConfig, get_parser_config
from valutatrade_hub.parser_service.storage import (
    add_history_record,
    update_rates_cache,
)

# Настройка логирования
logger = logging.getLogger(__name__)


def update_all_rates(config: ParserConfig | None = None) -> dict[str, int]:
    """Обновить все курсы валют из внешних API.

    Получает курсы от CoinGecko (крипта) и ExchangeRate-API (фиат),
    сохраняет в историю и кеш.

    Args:
        config: ParserConfig instance (опционально)

    Returns:
        Статистика обновления:
        {
            "crypto_count": 3,
            "fiat_count": 5,
            "total_count": 8,
            "errors": 0
        }

    Raises:
        ApiRequestError: Если все API запросы завершились неудачей.
        StorageError: Если данные не могут быть сохранены.
    """
    cfg = config or get_parser_config()

    logger.info("=" * 60)
    logger.info("Starting currency rates update...")
    logger.info("=" * 60)

    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    start_time = time.time()

    stats = {
        "crypto_count": 0,
        "fiat_count": 0,
        "total_count": 0,
        "errors": 0,
    }

    all_rates = {}
    errors = []
    crypto_rates = {}
    fiat_rates = {}

    # Получение API клиентов
    coingecko, exchangerate = get_api_clients(cfg)

    # Получение курсов криптовалют
    logger.info("\n[1/2] Fetching cryptocurrency rates from CoinGecko...")
    crypto_start = time.time()
    try:
        crypto_rates = coingecko.fetch_rates()
        all_rates.update(crypto_rates)
        stats["crypto_count"] = len(crypto_rates)

        # Сохранение в историю
        for pair, rate in crypto_rates.items():
            from_currency, _ = pair.split("_")
            raw_id = cfg.CRYPTO_ID_MAP.get(from_currency)
            add_history_record(
                pair=pair,
                rate=rate,
                source="CoinGecko",
                timestamp=timestamp,
                raw_id=raw_id,
                request_ms=int((time.time() - crypto_start) * 1000),
                status_code=200,
                config=cfg,
            )

        logger.info(
            f"✓ Fetched {len(crypto_rates)} crypto rates "
            f"in {time.time() - crypto_start:.2f}s"
        )

    except ApiRequestError as e:
        logger.error(f"✗ Failed to fetch crypto rates: {str(e)}")
        errors.append(f"CoinGecko: {str(e)}")
        stats["errors"] += 1

    # Получение курсов фиатных валют
    logger.info("\n[2/2] Fetching fiat currency rates from ExchangeRate-API...")
    fiat_start = time.time()
    try:
        fiat_rates = exchangerate.fetch_rates()
        all_rates.update(fiat_rates)
        stats["fiat_count"] = len(fiat_rates)

        # Сохранение в историю
        for pair, rate in fiat_rates.items():
            add_history_record(
                pair=pair,
                rate=rate,
                source="ExchangeRate-API",
                timestamp=timestamp,
                request_ms=int((time.time() - fiat_start) * 1000),
                status_code=200,
                config=cfg,
            )

        logger.info(
            f"✓ Fetched {len(fiat_rates)} fiat rates "
            f"in {time.time() - fiat_start:.2f}s"
        )

    except ApiRequestError as e:
        logger.error(f"✗ Failed to fetch fiat rates: {str(e)}")
        errors.append(f"ExchangeRate-API: {str(e)}")
        stats["errors"] += 1

    # Проверка получения данных
    if not all_rates:
        error_msg = "Failed to fetch rates from all sources. " + "; ".join(errors)
        logger.error(f"✗ {error_msg}")
        raise ApiRequestError(error_msg)

    # Обновление кеша
    logger.info(f"\nUpdating rates cache with {len(all_rates)} pairs...")
    try:
        # Обновление курсов криптовалют в кеше
        if crypto_rates:
            update_rates_cache(
                crypto_rates,
                source="CoinGecko",
                timestamp=timestamp,
                config=cfg,
            )

        # Обновление курсов фиатных валют в кеше
        if fiat_rates:
            update_rates_cache(
                fiat_rates,
                source="ExchangeRate-API",
                timestamp=timestamp,
                config=cfg,
            )

        logger.info("✓ Cache updated successfully")

    except StorageError as e:
        logger.error(f"✗ Failed to update cache: {str(e)}")
        stats["errors"] += 1
        raise

    # Финальная статистика
    stats["total_count"] = len(all_rates)
    elapsed = time.time() - start_time

    logger.info("\n" + "=" * 60)
    logger.info("Update completed successfully!")
    logger.info(f"  Total pairs: {stats['total_count']}")
    logger.info(f"  Crypto pairs: {stats['crypto_count']}")
    logger.info(f"  Fiat pairs: {stats['fiat_count']}")
    logger.info(f"  Errors: {stats['errors']}")
    logger.info(f"  Elapsed time: {elapsed:.2f}s")
    logger.info("=" * 60)

    return stats


def update_crypto_rates(config: ParserConfig | None = None) -> dict[str, float]:
    """Обновить только курсы криптовалют.

    Args:
        config: ParserConfig instance (опционально)

    Returns:
        Dictionary of crypto rates: {"BTC_USD": 59337.21, ...}

    Raises:
        ApiRequestError: Если API запрос завершился неудачей.
        StorageError: Если данные не могут быть сохранены.
    """
    cfg = config or get_parser_config()
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    logger.info("Fetching cryptocurrency rates from CoinGecko...")
    coingecko, _ = get_api_clients(cfg)
    start_time = time.time()

    crypto_rates = coingecko.fetch_rates()

    # Сохранение в историю
    for pair, rate in crypto_rates.items():
        from_currency, _ = pair.split("_")
        raw_id = cfg.CRYPTO_ID_MAP.get(from_currency)
        add_history_record(
            pair=pair,
            rate=rate,
            source="CoinGecko",
            timestamp=timestamp,
            raw_id=raw_id,
            request_ms=int((time.time() - start_time) * 1000),
            status_code=200,
            config=cfg,
        )

    # Обновление кеша
    update_rates_cache(crypto_rates, source="CoinGecko", timestamp=timestamp, config=cfg)

    logger.info(f"✓ Updated {len(crypto_rates)} crypto rates")
    return crypto_rates


def update_fiat_rates(config: ParserConfig | None = None) -> dict[str, float]:
    """Обновить только курсы фиатных валют.

    Args:
        config: ParserConfig instance (опционально)

    Returns:
        Dictionary of fiat rates: {"EUR_USD": 1.0786, ...}

    Raises:
        ApiRequestError: Если API запрос завершился неудачей.
        StorageError: Если данные не могут быть сохранены.
    """
    cfg = config or get_parser_config()
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    logger.info("Fetching fiat currency rates from ExchangeRate-API...")
    _, exchangerate = get_api_clients(cfg)
    start_time = time.time()

    fiat_rates = exchangerate.fetch_rates()

    # Сохранение в историю
    for pair, rate in fiat_rates.items():
        add_history_record(
            pair=pair,
            rate=rate,
            source="ExchangeRate-API",
            timestamp=timestamp,
            request_ms=int((time.time() - start_time) * 1000),
            status_code=200,
            config=cfg,
        )

    # Обновление кеша
    update_rates_cache(
        fiat_rates, source="ExchangeRate-API", timestamp=timestamp, config=cfg
    )

    logger.info(f"✓ Updated {len(fiat_rates)} fiat rates")
    return fiat_rates
