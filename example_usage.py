"""
Пример использования модуля vocal_separator для отделения вокала от инструментала.
"""

from vocal_separator import VocalSeparator, separate_vocals
from pathlib import Path


def example_simple():
    """Простой пример использования."""
    print("=== Простой пример ===")
    
    # Используем простую функцию
    audio_file = "assets/songs/Slipknot_-_Wait_and_Bleed_79496406.mp3"
    
    if not Path(audio_file).exists():
        print(f"Файл {audio_file} не найден!")
        return
    
    try:
        vocals_path, instrumental_path = separate_vocals(
            audio_file,
            output_dir="separated",
            device="cuda",  # Используем GPU, если доступен
            segment=None  # Автоматический выбор на основе модели
        )
        print(f"\n✓ Успешно!")
        print(f"  Вокал: {vocals_path}")
        print(f"  Инструментал: {instrumental_path}")
    except Exception as e:
        print(f"Ошибка: {e}")


def example_advanced():
    """Расширенный пример использования."""
    print("\n=== Расширенный пример ===")
    
    audio_file = "assets/songs/Slipknot_-_Wait_and_Bleed_79496406.mp3"
    
    if not Path(audio_file).exists():
        print(f"Файл {audio_file} не найден!")
        return
    
    # Создаем сепаратор с настройками
    separator = VocalSeparator(
        model="htdemucs",  # Модель по умолчанию
        output_dir="separated",
        device="cuda",  # Используем GPU
        segment=None,  # Автоматический выбор (7 для htdemucs)
        mp3=False,  # Сохраняем как WAV
        float32=False  # Используем int16
    )
    
    try:
        vocals_path, instrumental_path = separator.separate(
            audio_file,
            # two_stems="vocals"  # Отделяем только вокал от остального
        )
        print(f"\n✓ Успешно!")
        print(f"  Вокал: {vocals_path}")
        print(f"  Инструментал: {instrumental_path}")
    except Exception as e:
        print(f"Ошибка: {e}")


def example_cpu():
    """Пример использования CPU вместо GPU."""
    print("\n=== Пример с CPU ===")
    
    audio_file = "assets/songs/Slipknot_-_Wait_and_Bleed_79496406.mp3"
    
    if not Path(audio_file).exists():
        print(f"Файл {audio_file} не найден!")
        return
    
    separator = VocalSeparator(
        model="htdemucs",
        output_dir="separated",
        device="cpu",  # Используем CPU
        segment=None  # Автоматический выбор
    )
    
    try:
        vocals_path, instrumental_path = separator.separate(
            audio_file,
            two_stems="vocals"
        )
        print(f"\n✓ Успешно!")
        print(f"  Вокал: {vocals_path}")
        print(f"  Инструментал: {instrumental_path}")
    except Exception as e:
        print(f"Ошибка: {e}")


if __name__ == "__main__":
    # Запускаем примеры
    # example_simple()
    # Раскомментируйте для запуска других примеров:
    example_advanced()
    # example_cpu()

