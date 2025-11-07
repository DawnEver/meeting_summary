import argparse
import sys
from collections.abc import Iterable
from pathlib import Path

from litellm import completion

from .utils import save_text


def build_ollama_prompt(transcript_text: str, extra_prompt: str | None = None) -> list[dict]:
    user_content = 'Input transcript:\n' + transcript_text
    if extra_prompt:
        user_content += '\n\nAdditional instructions:\n' + extra_prompt.strip()
    return [
        {
            'role': 'system',
            'content': 'You are an assistant that reads a meeting transcript and produces concise meeting summary. Respond with valid Markdown format.',
        },
        {'role': 'user', 'content': user_content},
    ]


def _request_summary(
    chunk_text: str,
    ollama_model: str,
    extra_prompt: str | None = None,
):
    messages = build_ollama_prompt(chunk_text, extra_prompt)
    try:
        response = completion(model='ollama/' + ollama_model, messages=messages, stream=False)
    except ValueError as exc:
        print(f'Model summary request failed: {exc}')
        return None

    parsed = response['choices'][0]['message']['content']
    if isinstance(parsed, str):
        return parsed.strip()
    return None


def _split_transcript(transcript_text: str, context_length: int) -> Iterable[str]:
    step = max(context_length, 1)
    for start in range(0, len(transcript_text), step):
        yield transcript_text[start : start + step]


def generate_summary_text(
    transcript_text: str,
    *,
    ollama_model: str,
    context_length: int | None = None,
    extra_prompt: str | None = None,
    log_progress: bool = True,
) -> str | None:
    """Return a Markdown summary string for the provided transcript."""
    if context_length and context_length > 0 and len(transcript_text) > context_length:
        chunks = list(_split_transcript(transcript_text, context_length))
    else:
        chunks = [transcript_text]

    summaries: list[str] = []
    total = len(chunks)
    for index, chunk in enumerate(chunks, start=1):
        if total > 1 and log_progress:
            print(f'Summarizing chunk {index}/{total} (length={len(chunk)})...')
        chunk_summary = _request_summary(chunk, ollama_model=ollama_model, extra_prompt=extra_prompt)
        if chunk_summary is None:
            if log_progress:
                print(f'Skipped chunk {index} due to empty response')
            continue
        summaries.append(chunk_summary)

    if not summaries:
        if log_progress:
            print('No summary generated: all requests failed.')
        return None

    if len(summaries) == 1:
        return summaries[0]

    return '\n\n'.join(f'### Segment {idx}\n\n{summary}' for idx, summary in enumerate(summaries, start=1))


def summarize_with_ollama(
    transcript_text: str,
    outdir: Path,
    stem: str,
    ollama_model: str,
    context_length: int | None = None,
    extra_prompt: str | None = None,
):
    """Summarize transcript text using Ollama and save outputs to outdir."""
    final_summary = generate_summary_text(
        transcript_text,
        ollama_model=ollama_model,
        context_length=context_length,
        extra_prompt=extra_prompt,
        log_progress=True,
    )
    if final_summary is None:
        return

    save_text(outdir / (stem + '.summary.md'), final_summary)


def main():
    parser = argparse.ArgumentParser(description='Generate bilingual summary using Ollama')
    parser.add_argument('transcript', help='Path to transcript text file')
    parser.add_argument('-o', '--outdir', default='output', help='Directory to save outputs')
    parser.add_argument('-m', '--ollama-model', default='qwen3:30b-a3b', help='Local Ollama model name')
    parser.add_argument(
        '-c', '--context-length', type=int, default=0, help='Max characters per request; 0 disables chunking'
    )
    parser.add_argument('-p', '--extra-prompt', default=None, help='Additional instructions appended to the prompt')
    args = parser.parse_args()
    transcript_path = Path(args.transcript)
    if not transcript_path.exists():
        print(f'Transcript file not found: {transcript_path}', file=sys.stderr)
        sys.exit(2)
    summarize_with_ollama(
        transcript_text=transcript_path.read_text(encoding='utf-8'),
        outdir=Path(args.outdir),
        stem=transcript_path.stem,
        ollama_model=args.ollama_model,
        context_length=args.context_length,
        extra_prompt=args.extra_prompt,
    )


if __name__ == '__main__':
    main()
