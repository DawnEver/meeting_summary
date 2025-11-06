# Meeting Summary Pipeline (Video -> Whisper -> Ollama)

## Overview
Meeting Summary extracts speech from a recorded meeting, generates a Whisper transcript, and produces a Markdown summary with a local Ollama model. Each stage is available as a standalone CLI so you can run the complete workflow or plug specific pieces into an existing pipeline.

## Features
- End-to-end video → audio → transcript → summary command.
- Whisper transcription with optional language hints and SRT export.
- Ollama-powered summarization with user-supplied prompt additions.
- Automatic transcript chunking when model context length is limited.
- Simple output layout under `output/` for quick inspection and downstream automation.

## Requirements
- Python 3.13 or newer.
- [ffmpeg](https://ffmpeg.org/) available in your PATH for audio extraction.
- [Ollama](https://ollama.com/) running locally with the target model pulled (default: `qwen3:30b-a3b`).
- Sufficient GPU/CPU resources for the chosen Whisper model.

Install Python dependencies in editable mode:

```bash
pip install -e .[dev]
```

> Replace `pip` with `uv`, `pipx runpip`, or your preferred tool if needed.

## Quick Start
Run the full workflow on a meeting video:

```bash
python -m meeting_summary path/to/meeting.mp4 -o output -w turbo -c 8000 -p "Focus on decisions and owners"
```

Key options for the pipeline command:

| Flag | Description |
| --- | --- |
| `-o/--outdir` | Destination directory for audio, transcripts, and summaries. |
| `-w/--whisper-model` | Whisper checkpoint (`tiny`, `base`, `small`, `medium`, `large`, `turbo`, …). |
| `-l/--language` | Optional language hint passed to Whisper. |
| `-m/--ollama-model` | Local Ollama model name (prefixed automatically with `ollama/`). |
| `-c/--context-length` | Maximum transcript characters per summarization request. Use `0` to disable chunking. |
| `-p/--extra-prompt` | Additional instructions appended to every summarization prompt. |

Outputs land in `output/` (or the directory you passed with `-o`) and include:

- `<stem>.wav`: extracted mono audio.
- `<stem>.transcript.txt`: raw Whisper transcript.
- `<stem>.srt`: subtitle file when segment data is available.
- `<stem>.summary.md`: Markdown summary from the Ollama model.

## Running Individual Stages
Extract only the audio track:

```bash
python -m meeting_summary.extract_audio path/to/meeting.mp4 -o output --samplerate 16000
```

Transcribe existing audio:

```bash
python -m meeting_summary.transcribe path/to/meeting.wav -o output -w turbo -l en
```

Summarize an existing transcript (supports chunking and custom prompts):

```bash
python -m meeting_summary.summarize path/to/meeting.transcript.txt -o output -m qwen3:30b-a3b -c 6000 -p "Highlight risks"
```

When chunking is enabled (`-c/--context-length` > 0), the transcript is split into character ranges sized to fit the requested context window. Each chunk is summarized independently, and the final Markdown file combines all segments with numbered headings.

## Extra Prompting Tips
- Keep `--extra-prompt` focused; short instructions tend to guide the model better than long essays.
- Use chunking if you see context errors from Ollama or your model expects shorter inputs.
- You can post-process the Markdown summary as part of CI/CD or import it into notes systems since the format is consistent.

## Development
- Format and lint with [Ruff](https://docs.astral.sh/ruff/) if desired (`ruff check .`).
- Scripts in `scripts/` (e.g., `run_workflow.py`) illustrate how to orchestrate the pipeline programmatically.
- Contributions are welcome—open an issue or PR with proposed enhancements.
