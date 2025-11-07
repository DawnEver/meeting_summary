from pathlib import Path

import pytest

from meeting_summary import transcribe


def test_segments_to_srt_formats():
    segments = [
        {'start': 0.0, 'end': 1.234, 'text': 'Hello'},
        {'start': 61.0, 'end': 62.5, 'text': 'World'},
    ]
    srt = transcribe.segments_to_srt(segments, simple_time=False)
    assert '00:00:00,000 --> 00:00:01,234' in srt
    assert '00:01:01,000 --> 00:01:02,500' in srt
    assert 'Hello' in srt and 'World' in srt

    srt_simple = transcribe.segments_to_srt(segments, simple_time=True)
    assert '00:00:00 --> 00:00:01' in srt_simple
    assert '00:01:01 --> 00:01:02' in srt_simple


def test_transcribe_reuse(tmp_path: Path, monkeypatch):
    # Prepare a dummy existing transcript file to trigger reuse path
    audio_file = tmp_path / 'audio.wav'
    audio_file.write_bytes(b'RIFF....WAVEfmt ')
    transcript_path = tmp_path / 'audio.transcript.txt'
    transcript_path.write_text('existing transcript', encoding='utf-8')

    # Monkeypatch require_ext to accept .wav and skip actual whisper import
    monkeypatch.setattr(transcribe, 'AUDIO_EXTENSIONS', {'.wav'})

    text = transcribe.transcribe_audio(
        audio_path=audio_file,
        outdir=tmp_path,
        whisper_model='does-not-matter',
        language=None,
        make_srt=False,
    )
    assert text == 'existing transcript'


def test_transcribe_missing_file(tmp_path: Path):
    with pytest.raises(SystemExit):
        transcribe.transcribe_audio(
            audio_path=tmp_path / 'missing.mp3',
            outdir=tmp_path,
            whisper_model='dummy',
        )
