import argparse
import shlex
import subprocess
from pathlib import Path


def extract_audio(video_path: Path, outdir: Path, audio_path: Path, sample_rate: int = 16000):
    """Extract audio using ffmpeg to WAV (mono).

    Skips if ffmpeg fails (raises subprocess.CalledProcessError).
    """
    video = Path(video_path)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    if not video.exists():
        msg = f'Video not found: {video}'
        raise SystemExit(msg)

    audio_path = outdir / (video.stem + '.wav')
    if audio_path.exists():
        print(f'Audio already exists at {audio_path}, skipping extraction.')
        return

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
    print('Running ffmpeg:', ' '.join(shlex.quote(c) for c in cmd))
    subprocess.run(cmd, check=True)
    print(f'Extracted audio to: {audio_path}')


def main():
    parser = argparse.ArgumentParser(description='Extract audio from video (ffmpeg)')
    parser.add_argument('video', help='Path to video file')
    parser.add_argument('--outdir', default='output', help='Directory to save audio')
    parser.add_argument('--samplerate', type=int, default=16000, help='Audio sample rate')
    args = parser.parse_args()
    extract_audio(video_path=Path(args.video), outdir=Path(args.outdir), audio_path=None, sample_rate=args.samplerate)
