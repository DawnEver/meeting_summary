import types
from pathlib import Path

import pytest

from meeting_summary import extract_audio


def test_extract_audio_with_mock(monkeypatch, tmp_path: Path):
    # Use the provided test video asset path
    video = Path('tests/test-media/test_video.mp4').resolve()
    assert video.exists(), 'Missing test asset tests/test-media/test_video.mp4'

    # Mock subprocess.run to avoid actually invoking ffmpeg
    def fake_run(cmd, check=True):  # noqa: ARG001
        out_path = Path(cmd[-1])  # last arg is the output wav path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b'RIFF....WAVEfmt ')
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(extract_audio.subprocess, 'run', fake_run)

    outdir = tmp_path
    wav = extract_audio.extract_audio(video, outdir)
    assert wav.exists()
    assert wav.suffix == '.wav'


def test_extract_audio_unsupported_extension(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):  # noqa: ARG001
    # Create a dummy file with unsupported extension to trigger validation
    bad = tmp_path / 'file.txt'
    bad.write_text('x', encoding='utf-8')
    with pytest.raises(SystemExit):
        extract_audio.extract_audio(bad, tmp_path)
