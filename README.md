# NeuroKaraoke

НейроКараоке — приложение для практики вокала. Первый модуль проекта отделяет
вокал от инструментала в любой загруженной песне при помощи
[Demucs](https://github.com/adefossez/demucs?tab=readme-ov-file), который умеет
работать на CPU и GPU.

## Структура проекта

```
sirius-audio-project/
├── assets/songs/                # Примеры входных песен
├── outputs/separated/           # Будет создано автоматически
├── requirements.txt             # Основные зависимости (Demucs)
└── src/neuro_karaoke/           # Исходный код модуля разделения
```

## Установка зависимостей

```bash
cd /home/kravcov.vladimir14/personal/sirius-audio-project
python3 -m venv .venv && source .venv/bin/activate  # опционально
pip install -r requirements.txt
```

> Установка Demucs автоматически подтягивает PyTorch и torchaudio с поддержкой
> GPU, поэтому процесс может занять несколько минут.

## Запуск разделения

```bash
cd /home/kravcov.vladimir14/personal/sirius-audio-project
PYTHONPATH=src python -m neuro_karaoke.separation \
  --song assets/songs/Anna_Asti_-_Carica_76886351.mp3 \
  --output-root outputs/separated
```

Результат: в `outputs/separated/<имя_трека>/` появятся файлы
`<имя>_vocals.wav` и `<имя>_instrumental.wav`. По умолчанию модуль выбирает
устройство `cuda`, если в системе доступен GPU.

### Полезные параметры CLI

```bash
PYTHONPATH=src python -m neuro_karaoke.separation --help
```

- `--segment 8` — уменьшает длину сегмента, помогает при ограниченной VRAM
  (рекомендуют >=10 с для лучшего качества) [[1]].
- `--mp3 --mp3-bitrate 256` — сохраняет результат в MP3 вместо WAV.
- `--keep-intermediate` — оставляет исходную структуру Demucs в
  `outputs/separated/_demucs_raw`.
- `--overwrite` — пересобирает дорожки, даже если они уже существуют.

## Программный API

```python
from pathlib import Path
from neuro_karaoke import DemucsSeparator

separator = DemucsSeparator(output_root=Path("outputs/separated"))
result = separator.separate_track("assets/songs/Anna_Asti_-_Carica_76886351.mp3")
print(result.vocals_path, result.instrumental_path)
```

Класс возвращает `SeparationResult` с путями к вокалу и инструменталу, что
позволяет легко встроить модуль в будущие части приложения (визуализация текстов,
оценка интонации и т.д.).

## Требования к железу

- Demucs использует ~3 GB VRAM на GPU и ~7 GB по умолчанию, поэтому при
  нехватке памяти запустите с `--segment` или `-d cpu` [[1]].
- Для больших партий файлов увеличивайте `-j` аккуратно: параметр умножает
  потребление RAM.

### Важно: ограничения моделей htdemucs

- **Модели htdemucs** (htdemucs, htdemucs_ft, htdemucs_6s) имеют ограничение на максимальную длину сегмента: **7.8 секунд**.
- По умолчанию модуль автоматически устанавливает `segment=7` для этих моделей.
- Если вы получаете ошибку `FATAL: Cannot use a Transformer model with a longer segment`, уменьшите `--segment` до 7 или меньше.
- Для других моделей (mdx, mdx_extra) можно использовать большие значения segment (до 10 секунд и более).

## Дальнейшие шаги

- Добавить загрузку песен пользователем и автоматический запуск модуля.
- Настроить визуализацию текста и тональности на основе полученных дорожек.

---

[[1]](https://github.com/adefossez/demucs?tab=readme-ov-file)

 
