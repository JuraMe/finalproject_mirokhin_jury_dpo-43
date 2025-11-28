"""Конфигурация Parser Service.

Модуль содержит настройки для работы с внешними API
и параметры обновления курсов валют.

Цель: Вынести все изменяемые параметры в один файл для удобства
управления и безопасности, избегая жесткого кодирования (hardcoding).
"""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParserConfig:
    """Конфигурация Parser Service.

    Хранит все настройки для работы с внешними API,
    списки валют, пути к файлам и параметры запросов.

    Attributes:
        EXCHANGERATE_API_KEY: API ключ для ExchangeRate-API
            (загружается из переменной окружения).
        COINGECKO_API_KEY: API ключ для CoinGecko API
            (загружается из переменной окружения).
        COINGECKO_URL: URL эндпоинта CoinGecko API.
        EXCHANGERATE_API_URL: Базовый URL эндпоинта ExchangeRate-API.
        BASE_CURRENCY: Базовая валюта для всех операций (по умолчанию USD).
        FIAT_CURRENCIES: Список фиатных валют для отслеживания.
        CRYPTO_CURRENCIES: Список криптовалют для отслеживания.
        CRYPTO_ID_MAP: Сопоставление кодов валют и ID для CoinGecko API.
        RATES_FILE_PATH: Путь к файлу rates.json (кеш для Core Service).
        HISTORY_FILE_PATH: Путь к файлу exchange_rates.json (история).
        REQUEST_TIMEOUT: Таймаут ожидания ответа от API (секунды).
        MAX_RETRIES: Максимальное количество попыток при ошибке запроса.
        RETRY_DELAY: Задержка между повторными попытками (секунды).
    """

    # =============================================================================
    # API Ключи (загружаются из переменных окружения)
    # =============================================================================

    EXCHANGERATE_API_KEY: str = field(
        default_factory=lambda: os.getenv(
            "EXCHANGERATE_API_KEY", "2e717b403eb73c96f3612bc6"
        )
    )
    COINGECKO_API_KEY: str = field(
        default_factory=lambda: os.getenv(
            "COINGECKO_API_KEY", "CG-SY7XWWzPzooW8A8JZYJ2RL93"
        )
    )

    # =============================================================================
    # Эндпоинты API
    # =============================================================================

    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"

    # =============================================================================
    # Базовая валюта
    # =============================================================================

    BASE_CURRENCY: str = "USD"

    # =============================================================================
    # Списки валют для отслеживания
    # =============================================================================

    FIAT_CURRENCIES: tuple = ("EUR", "GBP", "RUB", "CNY", "JPY")
    CRYPTO_CURRENCIES: tuple = ("BTC", "ETH", "SOL")

    # =============================================================================
    # Сопоставление кодов криптовалют и ID для CoinGecko API
    # =============================================================================

    CRYPTO_ID_MAP: dict = field(
        default_factory=lambda: {
            "BTC": "bitcoin",
            "ETH": "ethereum",
            "SOL": "solana",
        }
    )

    # =============================================================================
    # Пути к файлам данных
    # =============================================================================

    RATES_FILE_PATH: str = field(
        default_factory=lambda: str(
            Path(__file__).parent.parent.parent / "data" / "rates.json"
        )
    )
    HISTORY_FILE_PATH: str = field(
        default_factory=lambda: str(
            Path(__file__).parent.parent.parent / "data" / "exchange_rates.json"
        )
    )

    # =============================================================================
    # Параметры сетевых запросов
    # =============================================================================

    REQUEST_TIMEOUT: int = 10  # секунды
    MAX_RETRIES: int = 3  # количество попыток
    RETRY_DELAY: int = 2  # секунды между попытками

    # =============================================================================
    # Методы
    # =============================================================================

    def get_exchangerate_url(self) -> str:
        """Получить полный URL для ExchangeRate-API.

        Returns:
            Полный URL с API ключом.

        Example:
            >>> config = ParserConfig()
            >>> url = config.get_exchangerate_url()
            >>> # https://v6.exchangerate-api.com/v6/{API_KEY}/latest/USD
        """
        return (
            f"{self.EXCHANGERATE_API_URL}/{self.EXCHANGERATE_API_KEY}"
            f"/latest/{self.BASE_CURRENCY}"
        )

    def get_coingecko_url(self) -> str:
        """Получить полный URL для CoinGecko API.

        Returns:
            Полный URL с параметрами запроса.

        Example:
            >>> config = ParserConfig()
            >>> url = config.get_coingecko_url()
            >>> # https://api.coingecko.com/api/v3/simple/price?vs_currencies=usd&ids=bitcoin,ethereum,solana&x_cg_demo_api_key={API_KEY}
        """
        crypto_ids = ",".join(self.CRYPTO_ID_MAP.values())
        return (
            f"{self.COINGECKO_URL}"
            f"?vs_currencies={self.BASE_CURRENCY.lower()}"
            f"&ids={crypto_ids}"
            f"&x_cg_demo_api_key={self.COINGECKO_API_KEY}"
        )

    def validate_config(self) -> bool:
        """Валидация конфигурации.

        Проверяет наличие обязательных параметров и корректность путей.

        Returns:
            True если конфигурация валидна, False иначе.

        Raises:
            ValueError: Если отсутствуют обязательные параметры.
        """
        # Проверка API ключей
        if not self.EXCHANGERATE_API_KEY:
            raise ValueError(
                "EXCHANGERATE_API_KEY не найден. "
                "Установите переменную окружения EXCHANGERATE_API_KEY"
            )

        if not self.COINGECKO_API_KEY:
            raise ValueError(
                "COINGECKO_API_KEY не найден. "
                "Установите переменную окружения COINGECKO_API_KEY"
            )

        # Проверка наличия валют
        if not self.FIAT_CURRENCIES and not self.CRYPTO_CURRENCIES:
            raise ValueError(
                "Не указаны валюты для отслеживания. "
                "Добавьте валюты в FIAT_CURRENCIES или CRYPTO_CURRENCIES"
            )

        # Проверка путей к файлам
        rates_path = Path(self.RATES_FILE_PATH)
        history_path = Path(self.HISTORY_FILE_PATH)

        if not rates_path.parent.exists():
            raise ValueError(
                f"Директория для rates.json не существует: {rates_path.parent}"
            )

        if not history_path.parent.exists():
            raise ValueError(
                f"Директория для exchange_rates.json не существует: "
                f"{history_path.parent}"
            )

        return True

    def __repr__(self) -> str:
        """Представление конфигурации для отладки."""
        return (
            f"ParserConfig("
            f"fiat={len(self.FIAT_CURRENCIES)}, "
            f"crypto={len(self.CRYPTO_CURRENCIES)}, "
            f"timeout={self.REQUEST_TIMEOUT}s)"
        )


# =============================================================================
# Глобальный экземпляр конфигурации
# =============================================================================


def get_parser_config() -> ParserConfig:
    """Получить экземпляр конфигурации Parser Service.

    Returns:
        Экземпляр ParserConfig с загруженными настройками.

    Example:
        >>> from valutatrade_hub.parser_service.config import get_parser_config
        >>> config = get_parser_config()
        >>> print(config.BASE_CURRENCY)
        USD
    """
    return ParserConfig()
