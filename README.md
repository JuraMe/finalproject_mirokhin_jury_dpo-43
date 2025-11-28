# ValutaTrade Hub

**Платформа для отслеживания и симуляции торговли валютами**

---

## Описание проекта

ValutaTrade Hub — это комплексная платформа, которая позволяет пользователям:
- Регистрироваться и управлять виртуальным портфелем фиатных и криптовалют
- Совершать сделки по покупке и продаже валют
- Отслеживать актуальные курсы валют в реальном времени
- Просматривать историю изменения курсов

### Архитектура

Система состоит из двух основных сервисов:

1. **Parser Service** — отдельный модуль для работы с внешними API:
   - Получает актуальные курсы от CoinGecko (криптовалюты) и ExchangeRate-API (фиатные валюты)
   - Сохраняет данные в кеш (rates.json) и историю (exchange_rates.json)
   - Поддерживает ручное обновление и автоматическое по расписанию

2. **Core Service** — основное приложение с CLI интерфейсом:
   - Управление пользователями (регистрация, авторизация)
   - Управление портфелями и кошельками
   - Торговые операции (покупка/продажа валют)
   - Получение актуальных курсов из кеша

### Поддерживаемые валюты

**Фиатные валюты:**
- USD (доллар США)
- EUR (евро)
- GBP (британский фунт)
- RUB (российский рубль)
- CNY (китайский юань)
- JPY (японская иена)

**Криптовалюты:**
- BTC (Bitcoin)
- ETH (Ethereum)
- SOL (Solana)

---

## Структура проекта

```
finalproject_mirokhin_jury_dpo-43/
├── valutatrade_hub/           # Основной пакет приложения
│   ├── core/                  # Core Service - бизнес-логика
│   │   ├── models.py          # Модели данных (User, Portfolio, Wallet)
│   │   ├── usecases.py        # Бизнес-логика (buy, sell, register, login)
│   │   ├── currencies.py      # Реестр валют
│   │   ├── utils.py           # Вспомогательные функции
│   │   └── exceptions.py      # Доменные исключения
│   ├── parser_service/        # Parser Service - работа с API
│   │   ├── api_clients.py     # API клиенты (CoinGecko, ExchangeRate-API)
│   │   ├── updater.py         # Координатор обновления курсов
│   │   ├── storage.py         # Работа с файлами данных
│   │   ├── scheduler.py       # Планировщик автообновления
│   │   └── config.py          # Конфигурация Parser Service
│   ├── cli/                   # CLI интерфейс
│   │   └── interface.py       # Команды CLI
│   ├── infra/                 # Инфраструктурный слой
│   │   ├── settings.py        # SettingsLoader (Singleton)
│   │   └── database.py        # DatabaseManager (Singleton)
│   ├── logging_config.py      # Конфигурация логирования
│   └── decorators.py          # Декоратор @log_action
├── data/                      # Файлы данных (создаются автоматически)
│   ├── users.json             # База пользователей
│   ├── portfolios.json        # Портфели пользователей
│   ├── rates.json             # Кеш актуальных курсов
│   ├── exchange_rates.json    # История изменения курсов
│   └── config.json            # Конфигурация приложения
├── logs/                      # Логи (создаются автоматически)
│   ├── valutatrade.log        # Общие логи приложения
│   └── actions.log            # Логи доменных операций (buy, sell, etc.)
├── tests/                     # Тесты
├── main.py                    # Точка входа в приложение
├── pyproject.toml             # Конфигурация проекта и зависимостей
├── Makefile                   # Автоматизация команд
└── README.md                  # Документация

```

---

## Установка

### Требования

- Python 3.10 или выше
- pip (устанавливается вместе с Python)

### Процесс установки

1. **Клонировать репозиторий:**
```bash
git clone https://github.com/yourusername/finalproject_mirokhin_jury_dpo-43.git
cd finalproject_mirokhin_jury_dpo-43
```

2. **Установить зависимости:**
```bash
make install
```

Эта команда выполнит:
- Установку проекта в режиме разработки (`pip install -e .`)
- Создание необходимых директорий (`data/`, `logs/`)

3. **(Опционально) Установить dev-зависимости для разработки:**
```bash
make dev
```

Это установит дополнительные инструменты:
- `ruff` — линтер и форматтер
- `mypy` — проверка типов
- `pytest` — тестирование

---

## Запуск приложения

### Базовый запуск

```bash
make run
# или
python main.py <команда> [аргументы]
```

### Примеры команд

Все команды выполняются в формате: `python main.py <команда> [опции]`

---

## Команды CLI

### 1. Регистрация и авторизация

**Регистрация нового пользователя:**
```bash
python main.py register --username alice --password secret123
```

**Вход в систему:**
```bash
python main.py login --username alice --password secret123
```

**Выход из системы:**
```bash
python main.py logout
```

---

### 2. Управление портфелем

**Пополнение кошелька:**
```bash
python main.py deposit --currency USD --amount 10000
python main.py deposit --currency BTC --amount 0.5
```

**Просмотр портфеля:**
```bash
python main.py show-portfolio
python main.py show-portfolio --base EUR  # показать стоимость в евро
```

---

### 3. Торговые операции

**Покупка валюты за USD:**
```bash
python main.py buy --currency BTC --amount 0.1
python main.py buy --currency EUR --amount 500
```

**Продажа валюты за USD:**
```bash
python main.py sell --currency BTC --amount 0.05
python main.py sell --currency EUR --amount 200
```

---

### 4. Получение курсов валют

**Курс обмена между двумя валютами:**
```bash
python main.py get-rate --from BTC --to USD
python main.py get-rate --from EUR --to GBP
```

**Показать все актуальные курсы из кеша:**
```bash
python main.py show-rates
```

---

### 5. Parser Service - обновление курсов

**Обновить все курсы вручную:**
```bash
python main.py update-rates
python main.py update-rates --source all          # все источники (по умолчанию)
python main.py update-rates --source crypto       # только криптовалюты
python main.py update-rates --source fiat         # только фиатные валюты
```

---

## Кеш и TTL (Time To Live)

### Механизм кеширования

Приложение использует двухуровневую систему хранения данных:

1. **rates.json** — кеш актуальных курсов:
   - Хранит последние известные курсы валют
   - Используется для быстрого доступа при операциях buy/sell/get-rate
   - Формат: `{"pairs": {"BTC_USD": {"rate": 95000.0, "updated_at": "2025-11-28T12:00:00Z", "source": "CoinGecko"}}, ...}`

2. **exchange_rates.json** — полная история изменений:
   - Сохраняет каждое обновление курса с метаданными
   - Позволяет анализировать динамику курсов
   - Формат: `{"history": [{"id": "BTC_USD_2025-11-28T12:00:00Z", "from": "BTC", "to": "USD", "rate": 95000.0, ...}], ...}`

### TTL (Time To Live)

Настройка TTL позволяет контролировать актуальность кеша:

**Конфигурация в `data/config.json`:**
```json
{
  "ttl_seconds": 3600,
  "cache_enabled": true
}
```

**Параметры:**
- `ttl_seconds` — время жизни кеша в секундах (по умолчанию: 3600 = 1 час)
- `cache_enabled` — включить/выключить использование кеша

**Как работает:**
1. При запросе курса система проверяет время последнего обновления (`last_refresh`)
2. Если данные старше TTL → показывается сообщение о необходимости обновления
3. Пользователь может обновить курсы командой `update-rates`
4. Новые данные сохраняются с актуальной меткой времени

**Рекомендации:**
- Для активной торговли: TTL = 300-600 секунд (5-10 минут)
- Для тестирования: TTL = 3600 секунд (1 час)
- Для демонстрации: TTL = 86400 секунд (24 часа)

---

## Parser Service - настройка API ключей

### Получение API ключей

**1. ExchangeRate-API (для фиатных валют):**
- Регистрация: https://www.exchangerate-api.com/
- Бесплатный план: 1500 запросов/месяц
- После регистрации получите API ключ

**2. CoinGecko API (для криптовалют):**
- CoinGecko предоставляет бесплатный доступ без ключа
- Лимит: 10-50 запросов/минуту
- Для расширенных возможностей: https://www.coingecko.com/en/api/pricing

### Настройка ключей

**Способ 1: Переменные окружения (рекомендуется)**

Создайте файл `.env` в корне проекта:
```bash
# .env
EXCHANGERATE_API_KEY=ваш_ключ_здесь
```

**Способ 2: Файл конфигурации**

Отредактируйте `valutatrade_hub/parser_service/config.py`:
```python
EXCHANGERATE_API_KEY = os.getenv("EXCHANGERATE_API_KEY", "ваш_ключ_здесь")
```

**Важно:** Не коммитьте API ключи в Git! Файл `.env` уже добавлен в `.gitignore`.

### Автоматическое обновление курсов

Для периодического обновления курсов используйте планировщик:

```python
from valutatrade_hub.parser_service.scheduler import run_scheduler

# Запустить обновление каждый час (3600 секунд)
scheduler = run_scheduler(interval=3600)

# Остановить планировщик
scheduler.stop()
```

---

## Разработка

### Линтинг и проверка кода

```bash
make lint          # Запустить ruff и mypy
make format        # Форматировать код с помощью ruff
```

### Тестирование

```bash
make test          # Запустить тесты
make test-cov      # Запустить тесты с покрытием
```

### Очистка

```bash
make clean         # Удалить временные файлы и кеш
```

---

## Логирование

Приложение ведет два типа логов:

1. **valutatrade.log** — общие логи работы приложения:
   - Запуск команд
   - Ошибки и предупреждения
   - Работа Parser Service

2. **actions.log** — логи доменных операций:
   - Регистрация пользователей (REGISTER)
   - Авторизация (LOGIN)
   - Покупка валют (BUY)
   - Продажа валют (SELL)

**Формат лога:**
```
INFO  2025-11-28T12:05:22 BUY user='alice' currency='BTC' amount=0.1000 rate=95000.00 base='USD' result=OK
```

Логи автоматически ротируются при достижении 10 MB (хранится 5 копий).

---

## Примеры использования

### Сценарий 1: Первый запуск

```bash
# 1. Регистрация
python main.py register --username trader1 --password pass123

# 2. Вход в систему
python main.py login --username trader1 --password pass123

# 3. Пополнение кошелька USD
python main.py deposit --currency USD --amount 10000

# 4. Обновление курсов
python main.py update-rates

# 5. Просмотр курсов
python main.py show-rates

# 6. Покупка Bitcoin
python main.py buy --currency BTC --amount 0.1

# 7. Просмотр портфеля
python main.py show-portfolio
```

### Сценарий 2: Торговля

```bash
# Вход
python main.py login --username trader1 --password pass123

# Проверка курса EUR/USD
python main.py get-rate --from EUR --to USD

# Покупка евро
python main.py buy --currency EUR --amount 1000

# Продажа части евро
python main.py sell --currency EUR --amount 500

# Итоговый портфель
python main.py show-portfolio
```

---

## Архитектурные решения

### Паттерны проектирования

1. **Singleton** — `SettingsLoader`, `DatabaseManager`
   - Гарантирует единственный экземпляр для конфигурации и БД

2. **Strategy** — `BaseApiClient` с реализациями `CoinGeckoClient`, `ExchangeRateApiClient`
   - Позволяет легко добавлять новые источники данных

3. **Decorator** — `@log_action`
   - Автоматическое логирование доменных операций

### Принципы SOLID

- **Single Responsibility** — каждый класс отвечает за одну задачу
- **Open/Closed** — легко расширяется новыми валютами и API клиентами
- **Dependency Inversion** — зависимости от абстракций, не от конкретных реализаций

---

### Демонстрация (asciinema)
[![asciicast](https://asciinema.org/a/YIeZ8jYbRO3Ysjj4ieE7FPhIb.svg)](https://asciinema.org/a/YIeZ8jYbRO3Ysjj4ieE7FPhIb)

---

## Лицензия

MIT License

---

## Автор

- Jury Mirokhin (m@jura.me)
- МИФИ-ДПО-43 

Проект выполнен в рамках курса **«Специалист по работе с данными и применению ИИ»** МИФИ-ДПО.