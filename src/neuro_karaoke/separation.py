"""Utilities for splitting songs into vocal and instrumental stems with Demucs.

The module exposes a small wrapper around the official Demucs CLI so the rest
of the NeuroKaraoke codebase can work with a straightforward Python API
without having to duplicate complex CLI calls each time.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    import torch  # type: ignore
except ImportError:  # pragma: no cover - torch is installed with demucs.
    torch = None

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class SeparationResult:
    """Holds the essential data that downstream modules need."""

    song_path: Path
    vocals_path: Path
    instrumental_path: Path
    output_dir: Path
    model_name: str
    device: str


class DemucsSeparator:
    """Encapsulates the interaction with Demucs.

    Parameters
    ----------
    output_root:
        Directory where the final stems should be written (defaults to
        ``outputs/separated``).
    model_name:
        Name of the pretrained model that Demucs should use. ``htdemucs`` works
        well on most tracks but users can experiment with others (`mdx_q`,
        `htdemucs_ft`, ...).
    device:
        Optional device override. When omitted the class automatically selects
        ``cuda`` if a GPU is available (torch must be installed) otherwise
        ``cpu``.
    two_stems:
        When provided, Demucs collapses all sources into two stems where the
        primary source is defined by the flag (``vocals`` by default). This is a
        great fit for karaoke since we only need the vocals and everything else.
    segment:
        Optional window size (in seconds). Reducing this value allows Demucs to
        run on GPUs with less VRAM at the cost of a small quality loss.
    shifts:
        Enables the "shift trick" from Demucs for slightly cleaner stems at the
        expense of additional inference time.
    jobs:
        Number of files to process concurrently. Keep this at ``1`` when using
        GPUs to avoid out-of-memory issues.
    mp3/mp3_bitrate:
        Save results as MP3 files instead of 44.1kHz wav. MP3s are lighter on
        disk but require an extra encoding pass.
    float32:
        Store wav files as ``float32`` instead of the default ``int16``.
    keep_intermediate:
        By default we clean the raw Demucs folders once the stems have been
        copied to the final destination. Toggle this flag if you want to inspect
        the unmodified Demucs layout for debugging.
    disable_cuda_cache:
        Mirrors the README recommendation to set the
        ``PYTORCH_NO_CUDA_MEMORY_CACHING`` env var. This can help keep VRAM
        usage in check when using consumer GPUs.
    """

    def __init__(
        self,
        output_root: Path | str = "outputs/separated",
        model_name: str = "htdemucs",
        device: Optional[str] = None,
        two_stems: str = "vocals",
        segment: Optional[float] = None,
        shifts: int = 1,
        jobs: int = 1,
        mp3: bool = False,
        mp3_bitrate: int = 320,
        float32: bool = False,
        keep_intermediate: bool = False,
        disable_cuda_cache: bool = True,
    ) -> None:
        self.output_root = Path(output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)

        self.model_name = model_name
        self.device = self._resolve_device(device)
        self.two_stems = two_stems
        self.segment = segment
        self.shifts = shifts
        self.jobs = jobs
        self.mp3 = mp3
        self.mp3_bitrate = mp3_bitrate
        self.float32 = float32
        self.keep_intermediate = keep_intermediate
        self.disable_cuda_cache = disable_cuda_cache

        self._work_dir = self.output_root / "_demucs_raw"
        self._work_dir.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------------------- API
    def separate_track(self, song_path: Path | str, overwrite: bool = False) -> SeparationResult:
        """Split ``song_path`` into vocal and accompaniment stems.

        Parameters
        ----------
        song_path:
            Absolute or relative path to the audio file (wav, mp3, flac, ...).
        overwrite:
            When ``False`` the method raises an error if the destination folder
            already contains stems for this track. Enable overwrite to refresh
            the stems.
        """

        input_path = Path(song_path).expanduser().resolve()
        if not input_path.exists():
            raise FileNotFoundError(f"Song not found: {input_path}")

        target_dir = self.output_root / input_path.stem
        if target_dir.exists():
            if not overwrite:
                raise FileExistsError(
                    f"Stems for '{input_path.stem}' already exist. "
                    "Pass overwrite=True to regenerate them."
                )
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        command = self._build_command(input_path)
        env = os.environ.copy()
        if self.disable_cuda_cache:
            env["PYTORCH_NO_CUDA_MEMORY_CACHING"] = "1"

        LOGGER.info("Running Demucs: %s", " ".join(command))
        subprocess.run(command, check=True, env=env)

        demucs_track_dir = self._resolve_demucs_track_dir(input_path)
        vocals_path, instrumental_path = self._collect_stems(demucs_track_dir, target_dir)

        if not self.keep_intermediate:
            shutil.rmtree(demucs_track_dir)
            model_dir = demucs_track_dir.parent
            if not any(model_dir.iterdir()):
                model_dir.rmdir()

        return SeparationResult(
            song_path=input_path,
            vocals_path=vocals_path,
            instrumental_path=instrumental_path,
            output_dir=target_dir,
            model_name=self.model_name,
            device=self.device,
        )

    # ----------------------------------------------------------------- Helpers
    def _resolve_device(self, preferred: Optional[str]) -> str:
        if preferred:
            return preferred
        if torch is not None and torch.cuda.is_available():
            return "cuda"
        return "cpu"

    def _build_command(self, song_path: Path) -> list[str]:
        command: list[str] = [
            sys.executable,
            "-m",
            "demucs",
            "--two-stems",
            self.two_stems,
            "-n",
            self.model_name,
            "-d",
            self.device,
            "--out",
            str(self._work_dir),
        ]

        if self.segment:
            command += ["--segment", str(self.segment)]
        if self.shifts and self.shifts > 1:
            command += ["--shifts", str(self.shifts)]
        if self.jobs and self.jobs > 1:
            command += ["-j", str(self.jobs)]
        if self.mp3:
            command += ["--mp3", "--mp3-bitrate", str(self.mp3_bitrate)]
        if self.float32:
            command.append("--float32")

        command.append(str(song_path))
        return command

    def _resolve_demucs_track_dir(self, input_path: Path) -> Path:
        model_dir = self._work_dir / self.model_name
        if not model_dir.exists():
            raise FileNotFoundError(
                f"Demucs did not create the expected model directory: {model_dir}"
            )

        candidate = model_dir / input_path.stem
        if candidate.exists():
            return candidate

        matches = sorted(model_dir.glob(f"{input_path.stem}*"))
        if not matches:
            raise FileNotFoundError(
                f"Unable to locate Demucs output for '{input_path.name}' under {model_dir}"
            )
        return matches[0]

    def _collect_stems(self, demucs_track_dir: Path, dest_dir: Path) -> tuple[Path, Path]:
        extension = ".mp3" if self.mp3 else ".wav"

        vocals_source = demucs_track_dir / f"vocals{extension}"
        if not vocals_source.exists():
            raise FileNotFoundError(f"Expected vocals stem missing: {vocals_source}")

        accompaniment_source = self._find_instrumental_source(demucs_track_dir, extension)

        vocals_dest = dest_dir / f"{demucs_track_dir.name}_vocals{extension}"
        instrumental_dest = dest_dir / f"{demucs_track_dir.name}_instrumental{extension}"

        shutil.move(vocals_source, vocals_dest)
        shutil.move(accompaniment_source, instrumental_dest)

        return vocals_dest, instrumental_dest

    def _find_instrumental_source(self, demucs_track_dir: Path, extension: str) -> Path:
        candidate_names = [f"no_{self.two_stems}", "accompaniment", "instrumental", "other"]
        # When ``two_stems`` is not vocals Demucs still writes a file with that
        # name, so we look for it as a fallback.
        candidate_names.append(self.two_stems)

        for name in candidate_names:
            candidate = demucs_track_dir / f"{name}{extension}"
            if candidate.exists():
                return candidate

        raise FileNotFoundError(
            f"Could not determine the instrumental stem inside {demucs_track_dir}"
        )


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Split a song into vocal and instrumental stems using Demucs."
    )
    parser.add_argument(
        "--song",
        required=True,
        type=Path,
        help="Path to the input song (e.g. assets/songs/track.mp3).",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("outputs/separated"),
        help="Directory where the processed stems should be saved.",
    )
    parser.add_argument(
        "--model",
        default="htdemucs",
        help="Name of the pretrained Demucs model to use.",
    )
    parser.add_argument(
        "--device",
        default=None,
        help="Device override (cpu/cuda). Leave empty for auto-detection.",
    )
    parser.add_argument(
        "--segment",
        type=float,
        default=None,
        help="Optional segment size in seconds to reduce memory usage.",
    )
    parser.add_argument(
        "--shifts",
        type=int,
        default=1,
        help="Number of prediction shifts to average (>=1).",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        help="Number of files to separate in parallel.",
    )
    parser.add_argument(
        "--mp3",
        action="store_true",
        help="Save stems as mp3 instead of wav.",
    )
    parser.add_argument(
        "--mp3-bitrate",
        type=int,
        default=320,
        help="Bitrate to use when --mp3 is enabled.",
    )
    parser.add_argument(
        "--float32",
        action="store_true",
        help="Save wav files as float32 instead of int16.",
    )
    parser.add_argument(
        "--keep-intermediate",
        action="store_true",
        help="Do not delete the raw Demucs output directory.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenerate stems even if they already exist in the output folder.",
    )
    return parser


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    )


def main() -> None:
    parser = _build_cli_parser()
    args = parser.parse_args()

    _configure_logging()

    separator = DemucsSeparator(
        output_root=args.output_root,
        model_name=args.model,
        device=args.device,
        segment=args.segment,
        shifts=args.shifts,
        jobs=args.jobs,
        mp3=args.mp3,
        mp3_bitrate=args.mp3_bitrate,
        float32=args.float32,
        keep_intermediate=args.keep_intermediate,
    )

    result = separator.separate_track(args.song, overwrite=args.overwrite)

    LOGGER.info(
        "Done! Vocals: %s | Instrumental: %s",
        result.vocals_path,
        result.instrumental_path,
    )


if __name__ == "__main__":  # pragma: no cover - CLI entry point.
    main()


