"""
Модуль для отделения вокала от инструментала в аудиофайлах.
Использует Demucs для разделения источников звука.
"""

from pathlib import Path
from typing import Optional, Tuple
import demucs.separate


class VocalSeparator:
    """Класс для отделения вокала от инструментала в аудиофайлах."""
    
    def __init__(
        self,
        model: str = "htdemucs",
        output_dir: Optional[str] = None,
        device: Optional[str] = None,
        segment: Optional[int] = None,
        shifts: int = 1,
        overlap: float = 0.25,
        mp3: bool = False,
        mp3_bitrate: int = 320,
        float32: bool = False
    ):
        """
        Инициализация сепаратора вокала.
        
        Args:
            model: Модель Demucs для использования (по умолчанию 'htdemucs')
            output_dir: Директория для сохранения результатов (по умолчанию 'separated')
            device: Устройство для обработки ('cuda', 'cpu' или None для автоопределения)
            segment: Длина сегмента в секундах (для управления памятью GPU).
                    Если None, автоматически выбирается на основе модели:
                    - htdemucs, htdemucs_ft, htdemucs_6s: 7 секунд (максимум 7.8)
                    - другие модели: 10 секунд
            shifts: Количество сдвигов для улучшения качества (увеличивает время обработки)
            overlap: Перекрытие между окнами (0.0-1.0)
            mp3: Сохранять результат в MP3 формате
            mp3_bitrate: Битрейт для MP3 (если mp3=True)
            float32: Сохранять как float32 WAV файлы
        """
        self.model = model
        self.output_dir = output_dir or "separated"
        self.device = device
        
        # Автоматический выбор segment на основе модели
        if segment is None:
            if model.startswith("htdemucs"):
                # Hybrid Transformer модели имеют ограничение 7.8 секунд
                self.segment = 7
            else:
                # Другие модели могут использовать большие сегменты
                self.segment = 10
        else:
            self.segment = segment
        self.shifts = shifts
        self.overlap = overlap
        self.mp3 = mp3
        self.mp3_bitrate = mp3_bitrate
        self.float32 = float32
    
    def separate(
        self,
        audio_path: str,
        two_stems: Optional[str] = None,
        output_subdir: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Отделяет вокал от инструментала в аудиофайле.
        
        Args:
            audio_path: Путь к входному аудиофайлу
            two_stems: Если указано 'vocals', отделяет только вокал от остального
            output_subdir: Поддиректория для сохранения результатов (по умолчанию имя файла)
        
        Returns:
            Tuple[str, str]: Пути к файлам вокала и инструментала
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Аудиофайл не найден: {audio_path}")
        
        # Подготовка аргументов для Demucs
        args = [
            "-n", self.model,
            "--out", str(self.output_dir),
        ]
        
        # Настройка устройства
        if self.device:
            args.extend(["-d", self.device])
        
        # Настройка сегментации (для управления памятью GPU)
        if self.segment:
            args.extend(["--segment", str(self.segment)])
        
        # Настройка сдвигов
        if self.shifts > 1:
            args.extend(["--shifts", str(self.shifts)])
        
        # Настройка перекрытия
        if self.overlap != 0.25:
            args.extend(["--overlap", str(self.overlap)])
        
        # Настройка формата вывода
        if self.mp3:
            args.append("--mp3")
            args.extend(["--mp3-bitrate", str(self.mp3_bitrate)])
        
        if self.float32:
            args.append("--float32")
        
        # Режим двух стемов (только вокал или только инструментал)
        if two_stems:
            args.extend(["--two-stems", two_stems])
        
        # Путь к аудиофайлу
        args.append(str(audio_path))
        
        # Выполнение разделения
        print(f"Начинаю разделение: {audio_path.name}")
        print(f"Модель: {self.model}")
        print(f"Устройство: {self.device or 'автоопределение'}")
        
        try:
            demucs.separate.main(args)
        except Exception as e:
            raise RuntimeError(f"Ошибка при разделении аудио: {e}")
        
        # Определение путей к результатам
        output_subdir = output_subdir or audio_path.stem
        model_output_dir = Path(self.output_dir) / self.model / output_subdir
        
        # Определение путей к файлам
        if two_stems == "vocals":
            # В режиме two-stems создаются только vocals.wav и no_vocals.wav
            vocals_path = model_output_dir / "vocals.wav"
            if self.mp3:
                vocals_path = model_output_dir / "vocals.mp3"
            instrumental_path = model_output_dir / "no_vocals.wav"
            if self.mp3:
                instrumental_path = model_output_dir / "no_vocals.mp3"
        else:
            # В обычном режиме создаются все стемы (vocals, drums, bass, other)
            vocals_path = model_output_dir / ("vocals.wav" if not self.mp3 else "vocals.mp3")
            
            # Инструментал = drums + bass + other
            # Проверяем, существует ли уже no_vocals (если модель его создала)
            instrumental_path = model_output_dir / ("no_vocals.wav" if not self.mp3 else "no_vocals.mp3")
            
            # Если файл no_vocals не существует, создаем его из других стемов
            if not instrumental_path.exists():
                drums_path = model_output_dir / ("drums.wav" if not self.mp3 else "drums.mp3")
                bass_path = model_output_dir / ("bass.wav" if not self.mp3 else "bass.mp3")
                other_path = model_output_dir / ("other.wav" if not self.mp3 else "other.mp3")
                
                if all(p.exists() for p in [drums_path, bass_path, other_path]):
                    # Создадим инструментал, смешав стемы
                    print("Смешиваю стемы для создания инструментала...")
                    self._mix_stems(
                        [drums_path, bass_path, other_path],
                        instrumental_path
                    )
                else:
                    # Если не все стемы найдены, попробуем найти хотя бы некоторые
                    available_stems = [p for p in [drums_path, bass_path, other_path] if p.exists()]
                    if available_stems:
                        print(f"Найдены только некоторые стемы: {[p.name for p in available_stems]}")
                        self._mix_stems(available_stems, instrumental_path)
                    else:
                        raise FileNotFoundError(
                            f"Не найдены стемы для создания инструментала в {model_output_dir}. "
                            f"Используйте two_stems='vocals' для автоматического создания."
                        )
        
        if not vocals_path.exists():
            raise FileNotFoundError(f"Файл вокала не найден: {vocals_path}")
        
        if not instrumental_path.exists():
            raise FileNotFoundError(f"Файл инструментала не найден: {instrumental_path}")
        
        print(f"✓ Разделение завершено!")
        print(f"  Вокал: {vocals_path}")
        print(f"  Инструментал: {instrumental_path}")
        
        return str(vocals_path), str(instrumental_path)
    
    def _mix_stems(self, stem_paths: list, output_path: Path):
        """
        Смешивает несколько стемов в один файл.
        
        Args:
            stem_paths: Список путей к стемам для смешивания
            output_path: Путь для сохранения результата
        """
        try:
            import torch
            import torchaudio
            
            # Загружаем все стемы
            waveforms = []
            sample_rate = None
            
            for stem_path in stem_paths:
                waveform, sr = torchaudio.load(stem_path)
                if sample_rate is None:
                    sample_rate = sr
                elif sr != sample_rate:
                    # Ресемплируем если нужно
                    resampler = torchaudio.transforms.Resample(sr, sample_rate)
                    waveform = resampler(waveform)
                
                waveforms.append(waveform)
            
            # Смешиваем стемы
            mixed = sum(waveforms)
            
            # Нормализуем чтобы избежать клиппинга
            max_val = mixed.abs().max()
            if max_val > 1.0:
                mixed = mixed / max_val
            
            # Сохраняем результат
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if output_path.suffix == '.mp3':
                torchaudio.save(
                    str(output_path),
                    mixed,
                    sample_rate,
                    format='mp3',
                    encoding='mp3',
                    bitrate=f'{self.mp3_bitrate}k'
                )
            else:
                torchaudio.save(str(output_path), mixed, sample_rate)
                
        except ImportError:
            print("Предупреждение: torchaudio не установлен, используйте --two-stems=vocals для автоматического создания инструментала")
            raise
        except Exception as e:
            raise RuntimeError(f"Ошибка при смешивании стемов: {e}")


def separate_vocals(
    audio_path: str,
    output_dir: str = "separated",
    model: str = "htdemucs",
    device: Optional[str] = None,
    segment: Optional[int] = None
) -> Tuple[str, str]:
    """
    Удобная функция для быстрого отделения вокала от инструментала.
    
    Args:
        audio_path: Путь к входному аудиофайлу
        output_dir: Директория для сохранения результатов
        model: Модель Demucs для использования
        device: Устройство ('cuda', 'cpu' или None)
        segment: Длина сегмента в секундах (None для автоматического выбора)
    
    Returns:
        Tuple[str, str]: Пути к файлам вокала и инструментала
    """
    separator = VocalSeparator(
        model=model,
        output_dir=output_dir,
        device=device,
        segment=segment
    )
    return separator.separate(audio_path, two_stems="vocals")


if __name__ == "__main__":
    """Пример использования модуля."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Отделение вокала от инструментала")
    parser.add_argument("audio_path", help="Путь к аудиофайлу")
    parser.add_argument("-o", "--output", default="separated", help="Директория для результатов")
    parser.add_argument("-n", "--model", default="htdemucs", help="Модель Demucs")
    parser.add_argument("-d", "--device", help="Устройство (cuda/cpu)")
    parser.add_argument("--segment", type=int, default=None, help="Длина сегмента в секундах (None для автоопределения)")
    parser.add_argument("--mp3", action="store_true", help="Сохранять как MP3")
    parser.add_argument("--mp3-bitrate", type=int, default=320, help="Битрейт MP3")
    
    args = parser.parse_args()
    
    separator = VocalSeparator(
        model=args.model,
        output_dir=args.output,
        device=args.device,
        segment=args.segment,
        mp3=args.mp3,
        mp3_bitrate=args.mp3_bitrate
    )
    
    vocals_path, instrumental_path = separator.separate(args.audio_path, two_stems="vocals")
    print(f"\nРезультаты сохранены:")
    print(f"  Вокал: {vocals_path}")
    print(f"  Инструментал: {instrumental_path}")

