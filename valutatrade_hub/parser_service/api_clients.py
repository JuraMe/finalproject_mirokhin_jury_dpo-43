"""API клиенты для получения курсов валют.

Модуль содержит классы для работы с внешними API:
- ExchangeRate-API (для фиатных валют)
- CoinGecko API (для криптовалют)

Цель: Изолировать логику работы с каждым внешним сервисом.
Создать унифицированный интерфейс для получения курсов,
скрывая детали реализации (разные URL, форматы ответов).
"""

import logging
import time
from abc import ABC, abstractmethod

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.config import ParserConfig, get_parser_config

# Настройка логирования
logger = logging.getLogger(__name__)


class BaseApiClient(ABC):
    """Абстрактный базовый класс для API клиентов.

    Определяет единый интерфейс для получения курсов валют
    из различных источников.

    Attributes:
        config: Конфигурация Parser Service.
        session: HTTP сессия для повторного использования соединений.
    """

    def __init__(self, config: ParserConfig | None = None):
        """Инициализация API клиента.

        Args:
            config: Конфигурация Parser Service (опционально).
        """
        self.config = config or get_parser_config()
        self.session = requests.Session()

    @abstractmethod
    def fetch_rates(self) -> dict[str, float]:
        """Получить курсы валют от API.

        Returns:
            Словарь курсов в стандартизированном формате:
            {"BTC_USD": 59337.21, "EUR_USD": 1.0786, ...}

        Raises:
            ApiRequestError: При ошибке запроса к API.
        """
        pass

    def _make_request(
        self, url: str, max_retries: int | None = None
    ) -> requests.Response:
        """Выполнить HTTP запрос с retry логикой.

        Args:
            url: URL для запроса.
            max_retries: Максимальное количество попыток (из конфига по умолчанию).

        Returns:
            Объект Response от requests.

        Raises:
            ApiRequestError: При ошибке запроса после всех попыток.
        """
        retries = max_retries or self.config.MAX_RETRIES
        last_exception = None

        for attempt in range(retries):
            try:
                logger.debug(
                    f"Запрос к API (попытка {attempt + 1}/{retries}): {url[:80]}..."
                )

                response = self.session.get(
                    url, timeout=self.config.REQUEST_TIMEOUT
                )

                # Проверка статус кода
                if response.status_code == 200:
                    logger.debug(
                        f"✓ Успешный ответ от API (status: {response.status_code})"
                    )
                    return response

                elif response.status_code == 429:
                    # Rate limit - ждем дольше
                    wait_time = self.config.RETRY_DELAY * (attempt + 2)
                    logger.warning(
                        f"Rate limit (429). Ожидание {wait_time}s перед повтором..."
                    )
                    time.sleep(wait_time)
                    continue

                else:
                    # Другие ошибки HTTP
                    raise ApiRequestError(
                        f"HTTP {response.status_code}: {response.text[:200]}"
                    )

            except requests.exceptions.Timeout as e:
                last_exception = e
                logger.warning(
                    f"Timeout при запросе к API (попытка {attempt + 1}/{retries})"
                )

            except requests.exceptions.ConnectionError as e:
                last_exception = e
                logger.warning(
                    f"Ошибка соединения (попытка {attempt + 1}/{retries}): {str(e)[:100]}"
                )

            except requests.exceptions.RequestException as e:
                last_exception = e
                logger.error(f"Ошибка запроса: {str(e)[:100]}")
                raise ApiRequestError(f"Ошибка при обращении к API: {str(e)}") from e

            # Ждем перед повторной попыткой (кроме последней)
            if attempt < retries - 1:
                time.sleep(self.config.RETRY_DELAY)

        # Все попытки исчерпаны
        raise ApiRequestError(
            f"Не удалось получить данные после {retries} попыток. "
            f"Последняя ошибка: {str(last_exception)}"
        )

    def __del__(self):
        """Закрыть сессию при удалении объекта."""
        if hasattr(self, "session"):
            self.session.close()


class CoinGeckoClient(BaseApiClient):
    """Клиент для получения курсов криптовалют от CoinGecko API.

    Получает курсы BTC, ETH, SOL и других криптовалют к доллару.

    Формат ответа API:
        {
            "bitcoin": {"usd": 59337.21},
            "ethereum": {"usd": 3401.17}
        }

    Формат возврата:
        {"BTC_USD": 59337.21, "ETH_USD": 3401.17}
    """

    def fetch_rates(self) -> dict[str, float]:
        """Получить курсы криптовалют от CoinGecko API.

        Returns:
            Словарь курсов в формате {"BTC_USD": 59337.21, ...}

        Raises:
            ApiRequestError: При ошибке запроса или парсинга ответа.
        """
        url = self.config.get_coingecko_url()

        try:
            response = self._make_request(url)
            data = response.json()

            # Парсинг ответа и преобразование в стандартный формат
            rates = {}
            for crypto_code, crypto_id in self.config.CRYPTO_ID_MAP.items():
                if crypto_id in data:
                    usd_key = self.config.BASE_CURRENCY.lower()
                    if usd_key in data[crypto_id]:
                        rate = data[crypto_id][usd_key]
                        pair = f"{crypto_code}_{self.config.BASE_CURRENCY}"
                        rates[pair] = float(rate)
                        logger.debug(f"  {pair}: {rate}")
                    else:
                        logger.warning(
                            f"Ключ '{usd_key}' не найден для {crypto_id}"
                        )
                else:
                    logger.warning(f"Данные для {crypto_id} ({crypto_code}) не найдены")

            if not rates:
                raise ApiRequestError(
                    "CoinGecko API вернул пустой результат или данные в неожиданном формате"
                )

            logger.info(f"✓ Получено {len(rates)} курсов криптовалют от CoinGecko")
            return rates

        except (ValueError, KeyError) as e:
            raise ApiRequestError(
                f"Ошибка парсинга ответа CoinGecko API: {str(e)}"
            ) from e


class ExchangeRateApiClient(BaseApiClient):
    """Клиент для получения курсов фиатных валют от ExchangeRate-API.

    Получает курсы EUR, GBP, RUB и других фиатных валют к доллару.

    Формат ответа API:
        {
            "result": "success",
            "base_code": "USD",
            "conversion_rates": {
                "EUR": 0.92,
                "GBP": 0.79,
                ...
            }
        }

    Формат возврата:
        {"EUR_USD": 1.0869, "GBP_USD": 1.2658}
    """

    def fetch_rates(self) -> dict[str, float]:
        """Получить курсы фиатных валют от ExchangeRate-API.

        Returns:
            Словарь курсов в формате {"EUR_USD": 1.0869, ...}

        Raises:
            ApiRequestError: При ошибке запроса или парсинга ответа.
        """
        url = self.config.get_exchangerate_url()

        try:
            response = self._make_request(url)
            data = response.json()

            # Проверка результата API
            if data.get("result") != "success":
                error_type = data.get("error-type", "unknown")
                raise ApiRequestError(
                    f"ExchangeRate-API вернул ошибку: {error_type}"
                )

            # Извлечение курсов из вложенного словаря
            conversion_rates = data.get("conversion_rates", {})
            if not conversion_rates:
                raise ApiRequestError(
                    "ExchangeRate-API не вернул курсы (пустой conversion_rates)"
                )

            # Преобразование в стандартный формат
            # ExchangeRate-API возвращает курсы ОТ доллара (USD -> EUR: 0.92)
            # Нам нужны курсы К доллару (EUR -> USD: 1.087)
            rates = {}
            for fiat_code in self.config.FIAT_CURRENCIES:
                if fiat_code in conversion_rates:
                    # Обратный курс: если USD -> EUR = 0.92, то EUR -> USD = 1/0.92
                    usd_to_fiat = conversion_rates[fiat_code]
                    fiat_to_usd = 1.0 / usd_to_fiat if usd_to_fiat != 0 else 0.0

                    pair = f"{fiat_code}_{self.config.BASE_CURRENCY}"
                    rates[pair] = float(fiat_to_usd)
                    logger.debug(f"  {pair}: {fiat_to_usd:.6f}")
                else:
                    logger.warning(
                        f"Курс для {fiat_code} не найден в ответе ExchangeRate-API"
                    )

            if not rates:
                raise ApiRequestError(
                    "ExchangeRate-API: ни одна из запрошенных валют не найдена"
                )

            logger.info(
                f"✓ Получено {len(rates)} курсов фиатных валют от ExchangeRate-API"
            )
            return rates

        except (ValueError, KeyError, ZeroDivisionError) as e:
            raise ApiRequestError(
                f"Ошибка парсинга ответа ExchangeRate-API: {str(e)}"
            ) from e


# =============================================================================
# Фабричная функция для создания клиентов
# =============================================================================


def get_api_clients(
    config: ParserConfig | None = None,
) -> tuple[CoinGeckoClient, ExchangeRateApiClient]:
    """Создать клиенты для всех API.

    Args:
        config: Конфигурация Parser Service (опционально).

    Returns:
        Кортеж (CoinGeckoClient, ExchangeRateApiClient).

    Example:
        >>> from valutatrade_hub.parser_service.api_clients import get_api_clients
        >>> coingecko, exchangerate = get_api_clients()
        >>> crypto_rates = coingecko.fetch_rates()
        >>> fiat_rates = exchangerate.fetch_rates()
    """
    cfg = config or get_parser_config()
    return CoinGeckoClient(cfg), ExchangeRateApiClient(cfg)
