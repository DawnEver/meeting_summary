from __future__ import annotations

import io
import uuid
from pathlib import Path

import pytest

from meeting_summary import web


@pytest.fixture
def client():
    app = web.app
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def _write(path: Path, data: bytes = b'x') -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _write_wav(path: Path) -> None:
    _write(path, b'RIFF....WAVEfmt ')


def test_web_additional_branches(client, monkeypatch):
    # 1) download audio: 404 for nonexistent id
    rid = uuid.uuid4().hex + '.wav'
    r = client.get(f'/api/download/audio/{rid}')
    assert r.status_code == 404

    # 2) download audio: 400 for unsupported extension under uploads/
    bad = web._upload_dir / (uuid.uuid4().hex + '.txt')
    _write(bad, b'test')
    r = client.get(f'/api/download/audio/{bad.name}')
    assert r.status_code == 400

    # 3) transcript/srt download 404 when files missing
    wav = web._output_dir / (uuid.uuid4().hex + '.wav')
    _write_wav(wav)
    r_t = client.get(f'/api/download/transcript/{wav.name}')
    r_s = client.get(f'/api/download/srt/{wav.name}')
    assert r_t.status_code == 404 and r_s.status_code == 404

    # 4) video-to-audio: empty upload -> 400
    data = {'video': (io.BytesIO(b'abc'), '')}
    r = client.post('/api/video-to-audio', data=data, content_type='multipart/form-data')
    assert r.status_code == 400

    # 5) audio-to-transcript by audio_id path (no upload)
    monkeypatch.setattr(web, 'transcribe_audio', lambda *a, **k: 'ok-transcript')  # noqa: ARG005
    r = client.post('/api/audio-to-transcript', json={'audio_id': wav.name})
    assert r.status_code == 200
    js = r.get_json()
    assert js['transcript'] == 'ok-transcript'
    # No transcript/srt files were created here, so urls may be None
    assert js['download_transcript_url'] is None and js['download_srt_url'] is None

    # 6) SSE: job not found for events & result
    r = client.get('/api/pipeline/events/does-not-exist')
    assert r.status_code == 404
    r = client.get('/api/pipeline/result/does-not-exist')
    assert r.status_code == 404

    # 7) SSE: pending result when job exists but not done
    job = web._new_job()
    r = client.get(f'/api/pipeline/result/{job.job_id}')
    assert r.status_code == 200
    assert r.get_json()['status'] == 'pending'
