# NeuroKaraoke

НейроКараоке превращает любую песню в караоке-трек. Мы интегрировали
[Demucs](https://github.com/adefossez/demucs?tab=readme-ov-file) для отделения
вокала, API Яндекс Музыки для поиска/скачивания треков и веб-интерфейс на
Streamlit.

## Возможности

- Поиск треков по названию через неофициальный API Яндекс Музыки [[2]].
- Скачивание аудио и текста (включая LRC с тайм-кодами, если они есть).
- Отделение вокала/инструмента одной кнопкой (Demucs + GPU при наличии).
- Онлайн-микшер: воспроизведение результата и регулировка громкости вокала.
- Караоке-виджет с «бегущей строкой» для синхронного текста.
- Экспорты отдельных дорожек и собранного микса.

## Структура проекта

```
sirius-audio-project/
├── assets/songs/                 # Примеры треков
├── downloads/                    # Кэш скачанных аудио из Яндекс Музыки
├── outputs/separated/            # Результаты Demucs
├── streamlit_app.py              # Веб-интерфейс
├── src/neuro_karaoke/
│   ├── separation.py             # Обёртка над Demucs CLI
│   ├── audio_utils.py            # Микширование дорожек
│   └── yandex_music_service.py   # Работа с API Яндекс Музыки
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Установка

```bash
cd /home/kravcov.vladimir14/personal/sirius-audio-project
uv venv && source .venv/bin/activate     # или python -m venv .venv
uv pip install -r requirements.txt       # или pip install -r requirements.txt
```

> Установка Demucs тянет PyTorch и torchaudio, поэтому процесс может занять
> несколько минут и потребовать скачивания ~1 ГБ.

## Токен Яндекс Музыки

API требует пользовательский токен. Получить его можно по инструкции из
документации проекта MarshalX [[2]]. Передайте токен через:

- переменную окружения `YANDEX_MUSIC_TOKEN`, или
- поле ввода в Streamlit.

## Веб-интерфейс (Streamlit)

```bash
source .venv/bin/activate
streamlit run streamlit_app.py
```

1. Введите токен Яндекс Музыки в сайдбаре.
2. Задайте название трека и нажмите «Найти».
3. Выберите нужный результат → «Скачать и подготовить трек».
4. После завершения доступны микшер, скачивание дорожек и караоке-текст.

## CLI (Demucs)

```bash
PYTHONPATH=src python -m neuro_karaoke.separation \
  --song assets/songs/Slipknot_-_Wait_and_Bleed_79496406.mp3 \
  --output-root outputs/separated
```

Полный набор флагов смотрите через `--help`. Полезные опции:

- `--segment 7` — безопасное значение для семейства `htdemucs`.
- `--mp3 --mp3-bitrate 256` — экспорт в MP3.
- `--keep-intermediate` — оставить структуру Demucs без очистки.

## Программный API

```python
from pathlib import Path
from neuro_karaoke import DemucsSeparator, YandexMusicService

service = YandexMusicService(token="...")          # поиск и загрузка с Яндекс Музыки
separator = DemucsSeparator(output_root=Path("outputs/separated"))

track_path, track, lyrics = service.download_track_with_lyrics("123456", Path("downloads"))
result = separator.separate_track(track_path)
print(result.vocals_path, result.instrumental_path)
```

## Требования к железу

- Demucs использует ~3 GB VRAM (7 GB по умолчанию). Снижайте `--segment` или
  переключайтесь на `-d cpu`, если память заканчивается [[1]].
- **htdemucs / htdemucs_ft / htdemucs_6s** поддерживают максимум `segment=7.8`
  секунды. В проекте по умолчанию используется `segment=7`.
- Веб-приложение выполняет лёгкое микширование в памяти, поэтому дополнительной
  GPU-нагрузки оно не даёт.

## Ссылки

- [[1]](https://github.com/adefossez/demucs?tab=readme-ov-file) — документация Demucs.
- [[2]](https://yandex-music.readthedocs.io/en/main/readme.html) — документация неофициального Yandex Music API.

