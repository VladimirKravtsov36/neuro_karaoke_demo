# Быстрый старт

## Установка с uv (рекомендуется)

1. Запустите скрипт настройки:
```bash
./setup.sh
```

Или вручную:

1. Создайте виртуальное окружение:
```bash
uv venv
```

2. Активируйте окружение:
```bash
source .venv/bin/activate
```

3. Установите зависимости:
```bash
uv pip install -r requirements.txt
```

4. Установите PyTorch с поддержкой CUDA (для GPU):
```bash
# Для CUDA 11.8
uv pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118

# Для CUDA 12.1
uv pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
```

## Использование

### Командная строка

**С активированным окружением:**
```bash
# Активируйте окружение (если еще не активировано)
source .venv/bin/activate

# Базовое использование (автоматически использует GPU если доступен)
python vocal_separator.py assets/songs/Anna_Asti_-_Carica_76886351.mp3

# С явным указанием GPU
python vocal_separator.py assets/songs/Anna_Asti_-_Carica_76886351.mp3 -d cuda

# Сохранение в MP3 формате
python vocal_separator.py assets/songs/Anna_Asti_-_Carica_76886351.mp3 --mp3
```

**Без активации окружения (используя uv run):**
```bash
# Базовое использование
uv run python vocal_separator.py assets/songs/Anna_Asti_-_Carica_76886351.mp3

# С явным указанием GPU
uv run python vocal_separator.py assets/songs/Anna_Asti_-_Carica_76886351.mp3 -d cuda
```

### Python код

```python
from vocal_separator import separate_vocals

# Простой способ
vocals_path, instrumental_path = separate_vocals(
    "assets/songs/your_song.mp3",
    device="cuda"  # или "cpu" или None для автоопределения
)

print(f"Вокал: {vocals_path}")
print(f"Инструментал: {instrumental_path}")
```

## Результаты

Результаты сохраняются в папку `separated/MODEL_NAME/TRACK_NAME/`:
- `vocals.wav` - вокал
- `no_vocals.wav` - инструментал (минус)

## Примеры

Запустите примеры из `example_usage.py`:
```bash
python example_usage.py
```

