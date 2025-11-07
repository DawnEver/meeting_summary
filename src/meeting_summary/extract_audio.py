import argparse
import shlex
import subprocess
from pathlib import Path


def extract_audio(video_path: Path, outdir: Path, *, sample_rate: int = 16000) -> Path:
    """Extract audio from a video into a mono WAV file.

    Returns the path to the generated audio file; if it already exists it is reused.
    Raises SystemExit if the input video is missing or ffmpeg fails (subprocess will raise).
    """
    video = Path(video_path)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    if not video.exists():
        msg = f'Video not found: {video}'
        raise SystemExit(msg)

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


def main() -> None:  # CLI entry point
    parser = argparse.ArgumentParser(description='Extract audio from video (ffmpeg)')
    parser.add_argument('video', help='Path to video file')
    parser.add_argument('--outdir', default='output', help='Directory to save audio')
    parser.add_argument('--samplerate', type=int, default=16000, help='Audio sample rate (Hz)')
    args = parser.parse_args()
    extract_audio(video_path=Path(args.video), outdir=Path(args.outdir), sample_rate=args.samplerate)


if __name__ == '__main__':
    main()
