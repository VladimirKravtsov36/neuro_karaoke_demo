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

### 1. Веб-интерфейс

```bash
source .venv/bin/activate
streamlit run streamlit_app.py
```

1. Введите токен Яндекс Музыки в сайдбаре (см. README, раздел «Токен»).
2. Найдите трек по названию и выберите нужный результат.
3. Нажмите «Скачать и подготовить трек», дождитесь Demucs.
4. Используйте слайдер громкости вокала, скачивайте дорожки, включайте караоке.

### 2. CLI (Demucs напрямую)

```bash
PYTHONPATH=src python -m neuro_karaoke.separation \
    --song assets/songs/Slipknot_-_Wait_and_Bleed_79496406.mp3 \
    --output-root outputs/separated
```

- `--segment 7` — безопасное значение для `htdemucs`.
- `--mp3` — сохранить в MP3.
- `--keep-intermediate` — не удалять структуру Demucs.

### 3. Python API

```python
from neuro_karaoke import DemucsSeparator

separator = DemucsSeparator()
result = separator.separate_track("assets/songs/Slipknot_-_Wait_and_Bleed_79496406.mp3")
print(result.vocals_path, result.instrumental_path)
```

## Куда складываются файлы

- Скачанные с Яндекс Музыки треки → `downloads/`.
- Готовые дорожки после Demucs → `outputs/separated/<название трека>/`.
  - `<track>_vocals.wav` — вокал.
  - `<track>_instrumental.wav` — инструментал.

