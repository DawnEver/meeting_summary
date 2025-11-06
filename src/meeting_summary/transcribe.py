import argparse
from pathlib import Path

import whisper

from .utils import save_text


def segments_to_srt(segments: list[dict]) -> str:
    """Convert Whisper segments to SRT formatted string."""

    def fmt_time(t: float) -> str:
        hours = int(t // 3600)
        minutes = int((t % 3600) // 60)
        seconds = int(t % 60)
        milliseconds = int((t - int(t)) * 1000)
        return f'{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}'

    lines = []
    for i, seg in enumerate(segments, start=1):
        start = fmt_time(float(seg.get('start', 0)))
        end = fmt_time(float(seg.get('end', 0)))
        text = seg.get('text', '').strip()
        lines.append(str(i))
        lines.append(f'{start} --> {end}')
        lines.append(text)
        lines.append('')
    return '\n'.join(lines)


def transcribe_audio(audio_path: Path, outdir: Path, whisper_model: str, language: str | None = None):
    """Transcribe audio file and save outputs to outdir."""
    if not audio_path.exists():
        msg = f'Audio not found: {audio_path}'
        raise SystemExit(msg)

    transcript_path = outdir / (audio_path.stem + '.transcript.txt')

    if transcript_path.exists():
        print(f'Transcript already exists at {transcript_path}, loading.')
        transcript_text = transcript_path.read_text(encoding='utf-8')

    else:
        print(f"Loading Whisper model '{whisper_model}'...")
        model = whisper.load_model(whisper_model)
        print('Transcribing...')
        res = model.transcribe(str(audio_path), language=language)

        transcript_text = res.get('text') if isinstance(res, dict) else str(res)
        save_text(transcript_path, transcript_text)
        segments = res.get('segments') if isinstance(res, dict) else None

        if segments:
            srt_path = outdir / (audio_path.stem + '.srt')
            if srt_path.exists():
                print(f'SRT already exists at {srt_path}, skipping.')
            else:
                srt = segments_to_srt(segments)
                save_text(srt_path, srt)

    print('Transcription finished. Transcript:', transcript_path)
    return transcript_text


def main():
    parser = argparse.ArgumentParser(description='Transcribe audio using Whisper')
    parser.add_argument('audio', help='Path to audio file (wav)')
    parser.add_argument('--outdir', default='output', help='Directory to save transcript')
    parser.add_argument('--whisper-model', default='turbo', help='Whisper model name')
    parser.add_argument('--language', default=None, help='Language hint for Whisper')
    parser.add_argument('--make-srt', action='store_true', help='Generate SRT from segments')
    args = parser.parse_args()

    audio_path = Path(args.audio)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    transcribe_audio(audio_path=audio_path, outdir=outdir, whisper_model=args.whisper_model, language=args.language)
