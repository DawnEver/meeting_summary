import argparse
from pathlib import Path

import whisper

from .utils import AUDIO_EXTENSIONS, convert_to_wav, require_ext, save_text


def segments_to_srt(segments: list[dict], *, simple_time: bool = False) -> str:
    """Convert Whisper segments to SRT formatted string.

    Parameters
    ----------
    segments : list[dict]
        Whisper output segments.
    simple_time : bool, default False
        If True, emit timestamps as HH:MM:SS (drop milliseconds) for easier human reading.
        Note: Standard SRT specification requires milliseconds (HH:MM:SS,mmm). Some players
        may reject simplified timestamps.

    """

    def fmt_time(t: float) -> str:
        hours = int(t // 3600)
        minutes = int((t % 3600) // 60)
        seconds = int(t % 60)
        if simple_time:
            return f'{hours:02d}:{minutes:02d}:{seconds:02d}'
        milliseconds = int((t - int(t)) * 1000)
        return f'{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}'

    lines = []
    for i, seg in enumerate(segments, start=1):
        start = fmt_time(float(seg.get('start', 0)))
        end = fmt_time(float(seg.get('end', 0)))
        text = seg.get('text', '').strip()
        lines.append(str(i))
        # When simple_time, still keep arrow separator; SRT spec expects ms but we allow simplified.
        lines.append(f'{start} --> {end}')
        lines.append(text)
        lines.append('')
    return '\n'.join(lines)


def transcribe_audio(
    audio_path: Path,
    outdir: Path,
    whisper_model: str,
    language: str | None = None,
    *,
    make_srt: bool = True,
    simple_srt_time: bool = False,
    auto_convert_wav: bool = False,
    sample_rate: int = 16000,
) -> str:
    """Transcribe an audio file and persist transcript (and optional SRT).

    Returns the raw transcript text. If a previous transcript exists it is reused.
    """
    if not audio_path.exists():
        msg = f'Audio not found: {audio_path}'
        raise SystemExit(msg)

    # Validate audio extension early
    require_ext(audio_path, AUDIO_EXTENSIONS, 'audio')

    # Optionally convert to wav (mono) for consistent Whisper ingestion
    if auto_convert_wav:
        audio_path = convert_to_wav(audio_path, outdir=outdir, sample_rate=sample_rate)

    transcript_path = outdir / (audio_path.stem + '.transcript.txt')
    outdir.mkdir(parents=True, exist_ok=True)

    if transcript_path.exists():
        print(f'[transcribe_audio] Reusing existing transcript: {transcript_path}')
        transcript_text = transcript_path.read_text(encoding='utf-8')
    else:
        print(f"[transcribe_audio] Loading Whisper model '{whisper_model}' ...")
        model = whisper.load_model(whisper_model)
        print('[transcribe_audio] Transcribing ...')
        res = model.transcribe(str(audio_path), language=language)
        transcript_text = res.get('text') if isinstance(res, dict) else str(res)
        save_text(transcript_path, transcript_text)

        if make_srt and isinstance(res, dict):
            segments = res.get('segments')
            if segments:
                srt_path = outdir / (audio_path.stem + '.srt')
                if srt_path.exists():
                    print(f'[transcribe_audio] SRT already exists: {srt_path}')
                else:
                    srt = segments_to_srt(segments, simple_time=simple_srt_time)
                    save_text(srt_path, srt)

    print('[transcribe_audio] Finished ->', transcript_path)
    return transcript_text


def main() -> None:
    parser = argparse.ArgumentParser(
        description=('Transcribe audio using Whisper. Supported audio formats: ' + ', '.join(sorted(AUDIO_EXTENSIONS)))
    )
    parser.add_argument('audio', help='Path to audio file (any supported format)')
    parser.add_argument('--outdir', default='output', help='Directory to save transcript/SRT')
    parser.add_argument('--whisper-model', default='turbo', help='Whisper model name')
    parser.add_argument('--language', default=None, help='Language hint for Whisper (e.g. en, zh)')
    parser.add_argument('--no-srt', action='store_true', help='Disable SRT generation')
    parser.add_argument(
        '--simple-srt-time', action='store_true', help='Use HH:MM:SS (no milliseconds) in SRT timestamps'
    )
    parser.add_argument(
        '--auto-convert-wav',
        action='store_true',
        help='Convert input audio to mono WAV (16kHz) before transcribing for consistency',
    )
    parser.add_argument('--sample-rate', type=int, default=16000, help='Target sample rate when converting to WAV')
    args = parser.parse_args()

    audio_path = Path(args.audio)
    outdir = Path(args.outdir)
    transcribe_audio(
        audio_path=audio_path,
        outdir=outdir,
        whisper_model=args.whisper_model,
        language=args.language,
        make_srt=not args.no_srt,
        simple_srt_time=args.simple_srt_time,
        auto_convert_wav=args.auto_convert_wav,
        sample_rate=args.sample_rate,
    )


if __name__ == '__main__':
    main()
