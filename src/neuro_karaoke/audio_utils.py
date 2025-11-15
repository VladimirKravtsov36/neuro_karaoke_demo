"""Helpers for lightweight audio post-processing inside the web UI."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Tuple

import numpy as np
import soundfile as sf


def _ensure_2d(audio: np.ndarray) -> np.ndarray:
    if audio.ndim == 1:
        return audio[:, None]
    return audio


def _match_channels(audio: np.ndarray, target_channels: int) -> np.ndarray:
    if audio.shape[1] == target_channels:
        return audio
    if audio.shape[1] == 1:
        return np.repeat(audio, target_channels, axis=1)

    # Fallback: truncate to target channels
    return audio[:, :target_channels]


def _trim_to_shortest(a: np.ndarray, b: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    length = min(a.shape[0], b.shape[0])
    return a[:length], b[:length]


def mix_stems(
    instrumental_path: Path | str,
    vocals_path: Path | str,
    vocal_gain: float,
) -> Tuple[BytesIO, int]:
    """Combine instrumental + scaled vocals and return an in-memory WAV."""

    instrumental, sr = sf.read(str(instrumental_path), dtype="float32")
    vocals, sr_v = sf.read(str(vocals_path), dtype="float32")
    if sr != sr_v:
        raise ValueError("Sample rates do not match for provided stems")

    instrumental = _ensure_2d(instrumental)
    vocals = _ensure_2d(vocals)
    instrumental, vocals = _trim_to_shortest(instrumental, vocals)

    channels = max(instrumental.shape[1], vocals.shape[1])
    instrumental = _match_channels(instrumental, channels)
    vocals = _match_channels(vocals, channels)

    mixed = instrumental + vocal_gain * vocals
    max_val = np.abs(mixed).max()
    if max_val > 1.0:
        mixed = mixed / max_val

    buffer = BytesIO()
    sf.write(buffer, mixed, sr, format="WAV")
    buffer.seek(0)
    return buffer, sr


def read_binary_audio(path: Path | str) -> bytes:
    with open(path, "rb") as file:
        return file.read()


__all__ = ["mix_stems", "read_binary_audio"]

