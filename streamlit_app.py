"""Streamlit front-end for NeuroKaraoke."""

from __future__ import annotations

import base64
import json
import os
from html import escape
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

from neuro_karaoke.audio_utils import read_binary_audio
from neuro_karaoke.separation import DemucsSeparator, SeparationResult
from neuro_karaoke.yandex_music_service import (
    KaraokeLine,
    LyricsPayload,
    TrackChoice,
    YandexMusicService,
)

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR = Path("outputs/separated")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="НейроКараоке", page_icon="🎤", layout="wide")


def _init_state() -> None:
    st.session_state.setdefault("ym_token", os.getenv("YANDEX_MUSIC_TOKEN", ""))
    st.session_state.setdefault("search_results", [])
    st.session_state.setdefault("selected_track_index", 0)
    st.session_state.setdefault("downloaded_track_path", None)
    st.session_state.setdefault("separation_result", None)
    st.session_state.setdefault("lyrics_payload", None)
    st.session_state.setdefault("track_metadata", None)


@st.cache_resource(show_spinner=False)
def get_separator() -> DemucsSeparator:
    return DemucsSeparator(output_root=OUTPUT_DIR, model_name="htdemucs", segment=7)


@st.cache_resource(show_spinner=False)
def get_service(token: str) -> YandexMusicService:
    return YandexMusicService(token)


@st.cache_data(show_spinner=False)
def get_audio_data_url(path: str, mtime: float) -> str:
    """Return a data: URL for the provided audio file."""

    file_path = Path(path)
    _ = mtime  # ensure Streamlit cache invalidates when file changes
    data = read_binary_audio(file_path)
    encoded = base64.b64encode(data).decode("utf-8")
    return f"data:audio/wav;base64,{encoded}"


def render_audio_player(
    instrumental_path: Path,
    vocals_path: Path,
    cues: list[KaraokeLine],
) -> None:
    """Custom HTML player that keeps playback running while changing levels."""

    instrumental_path = Path(instrumental_path)
    vocals_path = Path(vocals_path)
    instrumental_url = get_audio_data_url(
        str(instrumental_path), instrumental_path.stat().st_mtime
    )
    vocals_url = get_audio_data_url(str(vocals_path), vocals_path.stat().st_mtime)

    cues_payload = [{"time": round(c.time, 3), "text": c.text} for c in cues]
    cues_json = escape(json.dumps(cues_payload, ensure_ascii=False))
    initial_line = escape(cues_payload[0]["text"]) if cues_payload else "Тайм-коды недоступны"

    html = f"""
    <style>
    .nk-player {{
        background: #0f172a;
        color: #f8fafc;
        padding: 1.5rem;
        border-radius: 16px;
        box-shadow: 0 10px 40px rgba(15, 23, 42, 0.4);
    }}
    .nk-player audio {{
        width: 100%;
        margin-bottom: 1rem;
        outline: none;
    }}
    .nk-slider {{
        display: flex;
        flex-direction: column;
        gap: 0.4rem;
        margin-bottom: 1.2rem;
    }}
    .nk-slider label {{
        font-weight: 600;
        font-size: 0.95rem;
    }}
    .nk-slider input[type=range] {{
        -webkit-appearance: none;
        height: 6px;
        border-radius: 999px;
        background: linear-gradient(90deg, #f59e0b, #f97316);
    }}
    .nk-slider input[type=range]::-webkit-slider-thumb {{
        -webkit-appearance: none;
        width: 18px;
        height: 18px;
        border-radius: 50%;
        background: #f8fafc;
        box-shadow: 0 2px 10px rgba(0,0,0,0.35);
        cursor: pointer;
    }}
    .nk-karaoke {{
        background: rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
    }}
    .nk-karaoke-label {{
        text-transform: uppercase;
        font-size: 0.75rem;
        letter-spacing: 0.08em;
        color: #94a3b8;
        margin-bottom: 0.6rem;
    }}
    #nk-karaoke-line {{
        font-size: 1.4rem;
        font-weight: 600;
        min-height: 2.5rem;
    }}
    </style>
    <div class="nk-player" id="nk-player-root" data-cues='{cues_json}'>
        <audio id="nk-audio" controls preload="auto">
            <source src="{instrumental_url}" type="audio/wav" />
            Ваш браузер не поддерживает аудио воспроизведение.
        </audio>
        <audio id="nk-vocals" preload="auto" style="display:none">
            <source src="{vocals_url}" type="audio/wav" />
        </audio>
        <div class="nk-slider">
            <label for="nk-vocal-slider">
                Громкость вокала: <span id="nk-vocal-value">100%</span>
            </label>
            <input type="range"
                   id="nk-vocal-slider"
                   min="0"
                   max="1.2"
                   step="0.05"
                   value="1.0" />
        </div>
        <div class="nk-karaoke">
            <div class="nk-karaoke-label">Бегущая строка</div>
            <div id="nk-karaoke-line">{initial_line}</div>
        </div>
    </div>
    <script>
    (function() {{
        const root = document.getElementById("nk-player-root");
        if (!root) return;
        const cuesData = root.dataset.cues;
        const cues = cuesData ? JSON.parse(cuesData) : [];
        const audio = document.getElementById("nk-audio");
        const vocals = document.getElementById("nk-vocals");
        const slider = document.getElementById("nk-vocal-slider");
        const valueEl = document.getElementById("nk-vocal-value");
        const lineEl = document.getElementById("nk-karaoke-line");
        const hasCues = cues.length > 0;

        const setLabel = (value) => {{
            valueEl.textContent = Math.round(value * 100) + "%";
        }};

        const setVolume = (value) => {{
            vocals.volume = value;
            setLabel(value);
        }};

        setVolume(parseFloat(slider.value));

        slider.addEventListener("input", (event) => {{
            setVolume(parseFloat(event.target.value));
        }});

        const syncVocals = (force = false) => {{
            if (!vocals.duration) return;
            const diff = Math.abs(vocals.currentTime - audio.currentTime);
            if (force || diff > 0.05) {{
                try {{
                    vocals.currentTime = audio.currentTime;
                }} catch (err) {{
                    console.warn("Sync error", err);
                }}
            }}
        }};

        const playVocals = () => {{
            syncVocals(true);
            const promise = vocals.play();
            if (promise) {{
                promise.catch(() => {{}});
            }}
        }};

        audio.addEventListener("play", playVocals);
        audio.addEventListener("pause", () => vocals.pause());
        audio.addEventListener("seeking", () => syncVocals(true));
        audio.addEventListener("ratechange", () => {{
            vocals.playbackRate = audio.playbackRate;
            syncVocals(true);
        }});
        audio.addEventListener("timeupdate", () => {{
            syncVocals(false);
            if (!hasCues) return;
            updateLyrics(audio.currentTime);
        }});
        audio.addEventListener("ended", () => vocals.pause());

        let lastIndex = -1;
        const findCueIndex = (currentTime) => {{
            if (!cues.length) return 0;
            let left = 0;
            let right = cues.length - 1;
            let best = 0;
            while (left <= right) {{
                const mid = Math.floor((left + right) / 2);
                if (cues[mid].time <= currentTime) {{
                    best = mid;
                    left = mid + 1;
                }} else {{
                    right = mid - 1;
                }}
            }}
            return best;
        }};

        const updateLyrics = (currentTime) => {{
            const idx = findCueIndex(currentTime);
            if (idx !== lastIndex && cues[idx]) {{
                lineEl.textContent = cues[idx].text;
                lastIndex = idx;
            }}
        }};

        if (hasCues) {{
            lineEl.textContent = cues[0].text;
        }}
    }})();
    </script>
    """
    st.components.v1.html(html, height=470)


def _reuse_existing(separator: DemucsSeparator, song_path: Path) -> SeparationResult:
    target_dir = separator.output_root / song_path.stem
    if not target_dir.exists():
        raise FileNotFoundError(f"Existing stems for {song_path.stem} not found")

    vocals_candidates = sorted(target_dir.glob("*_vocals.*"))
    instrumental_candidates = sorted(target_dir.glob("*_instrumental.*"))
    if not vocals_candidates or not instrumental_candidates:
        raise FileNotFoundError(
            f"Stems for {song_path.stem} exist but files are missing in {target_dir}"
        )

    return SeparationResult(
        song_path=song_path,
        vocals_path=vocals_candidates[0],
        instrumental_path=instrumental_candidates[0],
        output_dir=target_dir,
        model_name=separator.model_name,
        device=separator.device,
    )


def _track_option_label(track: TrackChoice) -> str:
    return f"{track.title} — {track.artists} ({track.duration_str})"


def _render_track_table(results: list[TrackChoice]) -> None:
    table = pd.DataFrame(
        [
            {
                "Название": track.title,
                "Исполнители": track.artists,
                "Альбом": track.album,
                "Длительность": track.duration_str,
                "Синхр. текст": "Да" if track.has_sync_lyrics else "—",
            }
            for track in results
        ]
    )
    st.dataframe(table, use_container_width=True, hide_index=True)


def _render_plain_lyrics(text: str) -> None:
    st.text_area("Текст песни", value=text, height=300, disabled=True)


def main() -> None:
    _init_state()

    st.title("🎤 НейроКараоке")
    st.caption(
        "Загружайте любимые треки с Яндекс Музыки, отделяйте вокал от инструмента и тренируйте вокал."
    )

    with st.sidebar:
        st.header("⚙️ Настройки")
        token = st.text_input(
            "Токен Яндекс Музыки",
            value=st.session_state["ym_token"],
            type="password",
            help="Получите токен по инструкции из документации (см. README).",
        )
        if token != st.session_state["ym_token"]:
            st.session_state["ym_token"] = token
            st.session_state["search_results"] = []
            st.session_state["selected_track_index"] = 0
            st.session_state["separation_result"] = None
            st.session_state["lyrics_payload"] = None
            st.session_state["track_metadata"] = None

        overwrite = st.checkbox("Перегенерировать демикс при повторном запуске", value=False)

    token_to_use = st.session_state["ym_token"].strip()
    service: Optional[YandexMusicService] = None
    if token_to_use:
        try:
            service = get_service(token_to_use)
        except Exception as exc:  # noqa: BLE001 - хотим показать пользователю текст ошибки
            st.error(f"Не удалось инициализировать клиент Яндекс Музыки: {exc}")

    search_col, button_col = st.columns([3, 1])
    query = search_col.text_input("Название трека", placeholder="Например, Звери — Районы-кварталы")
    limit = button_col.number_input("Лимит", min_value=3, max_value=20, value=10, step=1)

    if st.button("🔍 Найти треки", disabled=service is None):
        if not query.strip():
            st.warning("Введите название трека для поиска.")
        else:
            with st.spinner("Ищем композиции в Яндекс Музыке..."):
                st.session_state["search_results"] = service.search_tracks(query.strip(), limit=int(limit))
                st.session_state["selected_track_index"] = 0

    results: list[TrackChoice] = st.session_state.get("search_results", [])
    selected_track: Optional[TrackChoice] = None
    if results:
        _render_track_table(results)
        options = list(range(len(results)))
        idx = st.radio(
            "Выберите трек",
            options=options,
            format_func=lambda i: _track_option_label(results[i]),
            index=min(st.session_state.get("selected_track_index", 0), len(results) - 1),
            horizontal=True,
        )
        st.session_state["selected_track_index"] = idx
        selected_track = results[idx]

    if selected_track and service:
        with st.expander("Детали трека", expanded=True):
            cols = st.columns([1, 2])
            if selected_track.cover_url:
                cols[0].image(selected_track.cover_url, caption=selected_track.title)
            cols[1].markdown(
                f"**Исполнители:** {selected_track.artists}\n\n"
                f"**Альбом:** {selected_track.album}\n\n"
                f"**Длительность:** {selected_track.duration_str}"
            )

        if st.button("⬇️ Скачать и подготовить трек", use_container_width=True):
            with st.spinner("Скачиваем аудио, получаем текст и запускаем Demucs..."):
                separator = get_separator()
                track_path, track_meta, lyrics_payload = service.download_track_with_lyrics(
                    selected_track.id, DOWNLOAD_DIR
                )
                try:
                    separation_result = separator.separate_track(track_path, overwrite=overwrite)
                except FileExistsError:
                    separation_result = _reuse_existing(separator, track_path)

                st.session_state["downloaded_track_path"] = track_path
                st.session_state["separation_result"] = separation_result
                st.session_state["lyrics_payload"] = lyrics_payload
                st.session_state["track_metadata"] = track_meta
                st.success("Готово! Микшер и текст доступны ниже ⬇️")

    separation_result: Optional[SeparationResult] = st.session_state.get("separation_result")
    lyrics_payload: Optional[LyricsPayload] = st.session_state.get("lyrics_payload")

    if separation_result:
        st.subheader("🎚️ Микшер и караоке")
        cues = []
        if lyrics_payload and lyrics_payload.is_synced:
            cues = lyrics_payload.cues[:500]
            st.caption("Тайм-коды обнаружены: текст синхронизирован автоматически.")
        elif lyrics_payload:
            st.caption("Тайм-коды отсутствуют — регулируйте громкость вручную, текст ниже.")
        else:
            st.caption("Текст не найден, но микшер доступен для прослушивания.")

        render_audio_player(
            separation_result.instrumental_path,
            separation_result.vocals_path,
            cues,
        )

        col1, col2 = st.columns(2)
        col1.download_button(
            "Скачать вокал",
            data=read_binary_audio(separation_result.vocals_path),
            file_name=f"{separation_result.song_path.stem}_vocals.wav",
            mime="audio/wav",
        )
        col2.download_button(
            "Скачать инструментал",
            data=read_binary_audio(separation_result.instrumental_path),
            file_name=f"{separation_result.song_path.stem}_instrumental.wav",
            mime="audio/wav",
        )

    if lyrics_payload:
        full_text = lyrics_payload.plain_text or lyrics_payload.raw_text
        if lyrics_payload.is_synced and full_text:
            with st.expander("Полный текст песни"):
                st.text_area("Синхронизированный текст", value=full_text, height=300)
        elif not lyrics_payload.is_synced and full_text:
            st.subheader("📝 Текст песни")
            _render_plain_lyrics(full_text)
    elif st.session_state.get("track_metadata"):
        st.info("Для выбранного трека текст не найден или доступ к нему ограничен.")


if __name__ == "__main__":
    main()

