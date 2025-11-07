import types
from pathlib import Path

from meeting_summary import extract_audio, summarize
from meeting_summary.__main__ import meeting_summary


def test_full_workflow_smoke(tmp_path, monkeypatch):
    # Use test video asset
    video = Path('tests/test-media/test_video.mp4').resolve()
    assert video.exists(), 'Missing test asset test_video.mp4'

    # Create a fresh unique output dir (pytest tmp_path already unique)
    outdir = tmp_path / 'wf-output'
    outdir.mkdir(parents=True, exist_ok=True)

    # Mock ffmpeg (subprocess.run) in extract_audio
    def fake_run(cmd, check=True):  # noqa: ARG001
        wav_path = Path(cmd[-1])
        wav_path.write_bytes(b'RIFF....WAVEfmt ')
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(extract_audio.subprocess, 'run', fake_run)

    # Stub whisper model load & transcribe
    def fake_load(name):  # noqa: ARG001
        obj = types.SimpleNamespace()
        obj.transcribe = lambda *a, **k: {  # noqa: ARG005
            'text': 'workflow transcript',
            'segments': [
                {'start': 0.0, 'end': 1.0, 'text': 'hello'},
                {'start': 1.0, 'end': 2.0, 'text': 'world'},
            ],
        }
        return obj

    import whisper as whisper_mod  # noqa: PLC0415

    monkeypatch.setattr(whisper_mod, 'load_model', fake_load)

    # Stub litellm completion for summarize
    def fake_completion(*a, **k):  # noqa: ARG001
        return {'choices': [{'message': {'content': 'final summary'}}]}

    # Patch summarize._request_summary directly to avoid relying on litellm import path
    monkeypatch.setattr(summarize, '_request_summary', lambda *a, **k: 'final summary')  # noqa: ARG005

    meeting_summary(
        video_path=str(video),
        outdir=str(outdir),
        whisper_model='tiny',
        ollama_model='dummy-model',
        context_length=0,
        extra_prompt=None,
    )

    # Assert expected output artifacts
    transcript = outdir / (video.stem + '.transcript.txt')
    srt = outdir / (video.stem + '.srt')
    summary = outdir / (video.stem + '.summary.md')

    assert transcript.exists(), 'Transcript missing'
    assert srt.exists(), 'SRT missing'
    assert summary.exists(), 'Summary missing'

    assert 'workflow transcript' in transcript.read_text(encoding='utf-8')
    assert 'final summary' in summary.read_text(encoding='utf-8')
