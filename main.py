"""Точка входа в приложение ValutaTrade Hub."""

from valutatrade_hub.cli.interface import run_cli


def main() -> None:
    """Запуск приложения."""
    run_cli()


if __name__ == "__main__":
    main()
