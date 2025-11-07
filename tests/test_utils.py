from pathlib import Path

import pytest

from meeting_summary import utils


def test_utils_basic(tmp_path: Path):
    # is_video_file / is_audio_file detection (case-insensitive)
    assert utils.is_video_file('movie.MP4') is True
    assert utils.is_video_file('clip.avi') is True
    assert utils.is_video_file('audio.mp3') is False

    assert utils.is_audio_file('sound.WAV') is True
    assert utils.is_audio_file('track.flac') is True
    assert utils.is_audio_file('video.mkv') is False

    # require_ext success and failure
    utils.require_ext('file.mp3', utils.AUDIO_EXTENSIONS, 'audio')  # should not raise
    with pytest.raises(SystemExit):
        utils.require_ext('file.txt', utils.AUDIO_EXTENSIONS, 'audio')

    # save_text writes content
    out_file = tmp_path / 'sample.txt'
    utils.save_text(out_file, 'hello world')
    assert out_file.read_text(encoding='utf-8') == 'hello world'

    # convert_to_wav short-circuits for existing wav without calling ffmpeg
    wav_file = tmp_path / 'input.wav'
    wav_file.write_bytes(b'RIFF....WAVEfmt ')  # minimal placeholder bytes
    converted = utils.convert_to_wav(wav_file, tmp_path)
    assert converted == wav_file
