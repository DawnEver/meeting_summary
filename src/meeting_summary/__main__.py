import argparse
import sys
from pathlib import Path

# import the component modules
from .extract_audio import extract_audio
from .summarize import summarize_with_ollama
from .transcribe import transcribe_audio


def meeting_summary(
    video_path: str,
    outdir: str,
    whisper_model: str = 'turbo',
    language: str | None = None,
    ollama_model: str = 'qwen3:30b-a3b',
    *,
    context_length: int | None = None,
    extra_prompt: str | None = None,
):
    """Run the full meeting-summary pipeline:
    Video -> audio (ffmpeg) -> Whisper transcription -> Ollama summarization
    Args:
        video_path: Path to input video file
        outdir: Directory to save outputs and intermediate files
        whisper_model: Whisper model name (tiny, base, small, medium, large, turbo)
        language: Language hint for Whisper (e.g. 'en', 'zh')
        ollama_model: Local Ollama model name
    """
    video_path = Path(video_path)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    if not video_path.exists():
        print(f'Video not found: {video_path}', file=sys.stderr)
        raise SystemExit(2)

    stem = video_path.stem
    # Step 1: extract audio
    audio_path = extract_audio(video_path=video_path, outdir=outdir)

    # Step 2: transcribe
    transcript_text = transcribe_audio(
        audio_path=audio_path, outdir=outdir, whisper_model=whisper_model, language=language
    )
    # Step 3: summarize with Ollama
    summarize_with_ollama(
        transcript_text=transcript_text,
        outdir=outdir,
        stem=stem,
        ollama_model=ollama_model,
        context_length=context_length,
        extra_prompt=extra_prompt,
    )
    print('Workflow finished. Outputs are in:', outdir)


def main():
    parser = argparse.ArgumentParser(description='Run full meeting-summary pipeline')
    parser.add_argument('video', help='Path to input video file')
    parser.add_argument('-o', '--outdir', default='output', help='Directory to save outputs and intermediate files')
    parser.add_argument(
        '-w',
        '--whisper-model',
        default='turbo',
        help='Whisper model name (tiny, base, small, medium, large, turbo)',
    )
    parser.add_argument('-l', '--language', default=None, help="Language hint for Whisper (e.g. 'en', 'zh')")
    parser.add_argument('-m', '--ollama-model', default='qwen3:30b-a3b', help='Local Ollama model name')
    parser.add_argument(
        '-c',
        '--context-length',
        type=int,
        default=64000,
        help='Max characters per request; 0 disables chunking',
    )
    parser.add_argument('-p', '--extra-prompt', default=None, help='Additional instructions appended to the prompt')
    args = parser.parse_args()
    meeting_summary(
        video_path=args.video,
        outdir=args.outdir,
        whisper_model=args.whisper_model,
        language=args.language,
        ollama_model=args.ollama_model,
        context_length=args.context_length,
        extra_prompt=args.extra_prompt,
    )


if __name__ == '__main__':
    main()
