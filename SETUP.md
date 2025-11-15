# Настройка проекта с uv

## Активация виртуального окружения

### Способ 1: Классическая активация (рекомендуется для интерактивной работы)

```bash
source .venv/bin/activate
```

После активации в начале строки терминала появится `(.venv)`, что означает, что окружение активно.

Для деактивации:
```bash
deactivate
```

### Способ 2: Использование `uv run` (без активации)

Можно запускать команды напрямую без активации окружения:

```bash
# Запуск Python скрипта
uv run python vocal_separator.py assets/songs/your_song.mp3

# Запуск Python с аргументами
uv run python example_usage.py

# Установка пакетов
uv pip install package_name
```

### Способ 3: Использование `uv shell` (активация в текущей оболочке)

```bash
uv shell
```

Эта команда активирует окружение в текущей оболочке. Для выхода используйте `exit` или `deactivate`.

## Установка зависимостей

После создания окружения установите зависимости:

```bash
# Активируйте окружение
source .venv/bin/activate

# Установите зависимости из requirements.txt
uv pip install -r requirements.txt

# Или установите PyTorch с CUDA поддержкой
uv pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118
```

## Быстрый старт

1. Создайте виртуальное окружение (если еще не создано):
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
uv pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118
```

4. Используйте проект:
```bash
python vocal_separator.py assets/songs/your_song.mp3 -d cuda
```

## Проверка активации

После активации проверьте, что окружение активно:

```bash
which python  # Должен показать путь к .venv/bin/python
python --version
pip list  # Покажет установленные пакеты в окружении
```

