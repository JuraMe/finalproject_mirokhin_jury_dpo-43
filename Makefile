.PHONY: install dev test lint format run clean

# Установка зависимостей
install:
	pip install -e .

# Установка dev зависимостей
dev:
	pip install -e ".[dev]"

# Запуск тестов
test:
	pytest

# Запуск тестов с покрытием
test-cov:
	pytest --cov=valutatrade_hub --cov-report=term-missing

# Линтинг
lint:
	ruff check valutatrade_hub tests
	mypy valutatrade_hub

# Форматирование кода
format:
	ruff format valutatrade_hub tests
	ruff check --fix valutatrade_hub tests

# Запуск приложения
run:
	python main.py

# Очистка
clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
	rm -rf dist build *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
