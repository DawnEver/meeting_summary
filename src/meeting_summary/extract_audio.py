import argparse
import shlex
import subprocess
from pathlib import Path

from .utils import VIDEO_EXTENSIONS, require_ext


def extract_audio(video_path: Path, outdir: Path, *, sample_rate: int = 16000) -> Path:
    """Extract audio from a video into a mono WAV file.

    Supported video extensions: .utils.VIDEO_EXTENSIONS

    Returns existing output if previously generated.
    Raises SystemExit if input missing or extension unsupported or ffmpeg fails.
    """
    video = Path(video_path)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    if not video.exists():
        msg = f'Video not found: {video}'
        raise SystemExit(msg)
    # Validate extension
    require_ext(video, VIDEO_EXTENSIONS, 'video')

    audio_path = outdir / (video.stem + '.wav')
    if audio_path.exists():
        print(f'[extract_audio] Reusing existing audio: {audio_path}')
        return audio_path

    cmd = [
        'ffmpeg',
        '-y',
        '-i',
        str(video_path),
        '-ar',
        str(sample_rate),
        '-ac',
        '1',
        '-vn',
        str(audio_path),
    ]
    print('[extract_audio] Running ffmpeg:', ' '.join(shlex.quote(c) for c in cmd))
    subprocess.run(cmd, check=True)
    print(f'[extract_audio] Extracted audio -> {audio_path}')
    return audio_path


def main() -> None:  # pragma: no cover
    parser = argparse.ArgumentParser(
        description=f'Extract audio from video (ffmpeg). Supported: {", ".join(sorted(VIDEO_EXTENSIONS))}'
    )
    parser.add_argument('video', help='Path to video file')
    parser.add_argument('--outdir', default='output', help='Directory to save audio')
    parser.add_argument('--samplerate', type=int, default=16000, help='Audio sample rate (Hz)')
    args = parser.parse_args()
    extract_audio(video_path=Path(args.video), outdir=Path(args.outdir), sample_rate=args.samplerate)


if __name__ == '__main__':
    main()
