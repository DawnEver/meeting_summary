"""Shared utility helpers for meeting_summary package.

Centralizes file save helpers plus media format detection and optional audio
conversion so CLI modules and the web API stay consistent.
"""

from __future__ import annotations

import shlex
import subprocess
from collections.abc import Iterable
from pathlib import Path

# Mainstream container/codec extensions we accept. All lowercase, include leading dot.
VIDEO_EXTENSIONS: set[str] = {
    '.mp4',
    '.mov',
    '.mkv',
    '.avi',
    '.webm',
    '.m4v',
    '.flv',
    '.3gp',
    '.ts',
    '.vob',
    '.wmv',
    '.mpeg',
    '.mpg',
    '.m2ts',
    '.ogv',
}
"""Supported video container extensions for video ➜ audio extraction."""

AUDIO_EXTENSIONS: set[str] = {
    '.wav',
    '.mp3',
    '.aac',
    '.ogg',
    '.flac',
    '.m4a',
    '.wma',
    '.webm',  # sometimes audio-only webm
    '.opus',  # explicit opus files
}
"""Supported audio file extensions for audio ➜ transcript stage."""


def save_text(path: Path, text: str) -> None:
    """Persist UTF-8 text, creating parent directories if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    print(f'Saved: {path}')


def _suffix(path: Path | str) -> str:
    return Path(path).suffix.lower()


def is_video_file(path: Path | str) -> bool:
    """Return True if path has a known video extension."""
    return _suffix(path) in VIDEO_EXTENSIONS


def is_audio_file(path: Path | str) -> bool:
    """Return True if path has a known audio extension."""
    return _suffix(path) in AUDIO_EXTENSIONS


def require_ext(path: Path | str, allowed: Iterable[str], kind: str) -> None:
    """Raise SystemExit if path extension not in allowed set."""
    ext = _suffix(path)
    if ext not in {e.lower() for e in allowed}:
        msg = f'Unsupported {kind} extension: {ext}'
        raise SystemExit(msg)


def convert_to_wav(
    audio_path: Path,
    outdir: Path,
    *,
    sample_rate: int = 16000,
    overwrite: bool = False,
) -> Path:
    """Convert an input audio file to mono WAV (returns path).

    If the input is already a WAV file it is returned unchanged. Uses ffmpeg.
    Raises SystemExit on failure.
    """
    if audio_path.suffix.lower() == '.wav':
        return audio_path
    outdir.mkdir(parents=True, exist_ok=True)
    wav_path = outdir / (audio_path.stem + '.wav')
    if wav_path.exists() and not overwrite:
        print(f'[convert_to_wav] Reusing existing WAV: {wav_path}')
        return wav_path
    cmd = [
        'ffmpeg',
        '-y',
        '-i',
        str(audio_path),
        '-ar',
        str(sample_rate),
        '-ac',
        '1',
        str(wav_path),
    ]
    print('[convert_to_wav] Running ffmpeg:', ' '.join(shlex.quote(c) for c in cmd))
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        msg = f'ffmpeg conversion failed: {e}'
        raise SystemExit(msg) from e
    print(f'[convert_to_wav] Created -> {wav_path}')
    return wav_path
