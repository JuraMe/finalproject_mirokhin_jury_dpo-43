"""Вспомогательные функции."""

from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"


def load_json(filename: str) -> dict | list:
    """Загрузить данные из JSON файла."""
    import json

    filepath = DATA_DIR / filename
    with filepath.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(filename: str, data: dict | list) -> None:
    """Сохранить данные в JSON файл."""
    import json

    filepath = DATA_DIR / filename
    with filepath.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
