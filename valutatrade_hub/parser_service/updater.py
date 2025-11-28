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
from valutatrade_hub.parser_service.api_clients import (
    BaseApiClient,
    CoinGeckoClient,
    ExchangeRateApiClient,
    get_api_clients,
)
from valutatrade_hub.parser_service.config import ParserConfig, get_parser_config
from valutatrade_hub.parser_service.storage import (
    add_history_record,
    update_rates_cache,
)

# Настройка логирования
logger = logging.getLogger(__name__)


class RatesUpdater:
    """Координатор обновления курсов валют.

    Точка входа для логики парсинга. Опрашивает все API клиенты,
    объединяет данные и сохраняет в хранилище.

    Attributes:
        config: Конфигурация Parser Service.
        clients: Список API клиентов для опроса.
    """

    def __init__(
        self,
        clients: list[BaseApiClient] | None = None,
        config: ParserConfig | None = None,
    ):
        """Инициализация координатора обновлений.

        Args:
            clients: Список API клиентов (опционально).
                Если не указан, создаются клиенты для CoinGecko и ExchangeRate-API.
            config: Конфигурация Parser Service (опционально).
        """
        self.config = config or get_parser_config()

        if clients is None:
            # Создаем клиенты по умолчанию
            coingecko, exchangerate = get_api_clients(self.config)
            self.clients = [coingecko, exchangerate]
        else:
            self.clients = clients

    def run_update(self) -> dict[str, int]:
        """Выполнить обновление курсов валют.

        Основной метод координации:
        1. Вызывает fetch_rates() у каждого клиента
        2. Объединяет полученные словари с курсами
        3. Добавляет метаданные (source, last_refresh)
        4. Передает в storage для сохранения
        5. Ведет подробное логирование каждого шага

        Returns:
            Статистика обновления:
            {
                "crypto_count": 3,
                "fiat_count": 5,
                "total_count": 8,
                "errors": 0,
                "success": 2,
                "failed": 0
            }

        Raises:
            ApiRequestError: Если все API запросы завершились неудачей.
            StorageError: Если данные не могут быть сохранены.
        """
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
            "success": 0,
            "failed": 0,
        }

        all_rates = {}
        errors = []

        # Опрос каждого клиента
        for i, client in enumerate(self.clients, 1):
            client_name = client.__class__.__name__
            logger.info(
                f"\n[{i}/{len(self.clients)}] Fetching rates from {client_name}..."
            )
            client_start = time.time()

            try:
                # Получение курсов от клиента
                rates = client.fetch_rates()

                # Определение источника для метаданных
                if isinstance(client, CoinGeckoClient):
                    source = "CoinGecko"
                    stats["crypto_count"] = len(rates)
                elif isinstance(client, ExchangeRateApiClient):
                    source = "ExchangeRate-API"
                    stats["fiat_count"] = len(rates)
                else:
                    source = client_name

                # Объединение с общим словарем
                all_rates.update(rates)

                # Сохранение каждой пары в историю
                for pair, rate in rates.items():
                    from_currency, _ = pair.split("_")
                    raw_id = self.config.CRYPTO_ID_MAP.get(from_currency)

                    add_history_record(
                        pair=pair,
                        rate=rate,
                        source=source,
                        timestamp=timestamp,
                        raw_id=raw_id,
                        request_ms=int((time.time() - client_start) * 1000),
                        status_code=200,
                        config=self.config,
                    )

                elapsed = time.time() - client_start
                logger.info(
                    f"✓ Successfully fetched {len(rates)} rates from {client_name} "
                    f"in {elapsed:.2f}s"
                )
                stats["success"] += 1

            except ApiRequestError as e:
                # Отказоустойчивость: логируем ошибку, но продолжаем
                logger.error(f"✗ Failed to fetch rates from {client_name}: {str(e)}")
                errors.append(f"{client_name}: {str(e)}")
                stats["errors"] += 1
                stats["failed"] += 1

            except Exception as e:
                # Неожиданная ошибка
                logger.error(
                    f"✗ Unexpected error from {client_name}: {str(e)}",
                    exc_info=True,
                )
                errors.append(f"{client_name}: {str(e)}")
                stats["errors"] += 1
                stats["failed"] += 1

        # Проверка получения данных
        if not all_rates:
            error_msg = "Failed to fetch rates from all sources. " + "; ".join(errors)
            logger.error(f"✗ {error_msg}")
            raise ApiRequestError(error_msg)

        # Обновление кеша
        logger.info(f"\nUpdating rates cache with {len(all_rates)} pairs...")
        try:
            # Группировка по источникам для сохранения метаданных
            crypto_rates = {}
            fiat_rates = {}

            for pair, rate in all_rates.items():
                from_currency, _ = pair.split("_")
                if from_currency in list(self.config.CRYPTO_CURRENCIES):
                    crypto_rates[pair] = rate
                else:
                    fiat_rates[pair] = rate

            # Обновление курсов криптовалют в кеше
            if crypto_rates:
                update_rates_cache(
                    crypto_rates,
                    source="CoinGecko",
                    timestamp=timestamp,
                    config=self.config,
                )

            # Обновление курсов фиатных валют в кеше
            if fiat_rates:
                update_rates_cache(
                    fiat_rates,
                    source="ExchangeRate-API",
                    timestamp=timestamp,
                    config=self.config,
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
        logger.info(f"  Successful clients: {stats['success']}")
        logger.info(f"  Failed clients: {stats['failed']}")
        logger.info(f"  Errors: {stats['errors']}")
        logger.info(f"  Elapsed time: {elapsed:.2f}s")
        logger.info("=" * 60)

        return stats


# =============================================================================
# Convenience functions для обратной совместимости
# =============================================================================


def update_all_rates(config: ParserConfig | None = None) -> dict[str, int]:
    """Обновить все курсы валют из внешних API.

    Convenience функция, которая создает RatesUpdater и вызывает run_update().

    Args:
        config: ParserConfig instance (опционально)

    Returns:
        Статистика обновления от RatesUpdater.run_update()

    Raises:
        ApiRequestError: Если все API запросы завершились неудачей.
        StorageError: Если данные не могут быть сохранены.
    """
    updater = RatesUpdater(config=config)
    return updater.run_update()


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
    update_rates_cache(
        crypto_rates, source="CoinGecko", timestamp=timestamp, config=cfg
    )

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
