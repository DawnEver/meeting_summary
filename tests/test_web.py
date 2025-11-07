from __future__ import annotations

import io
from pathlib import Path

import pytest

from meeting_summary import web


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):  # noqa: ARG001
    app = web.app
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def _write_wav(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'RIFF....WAVEfmt ')


def _write_transcript_and_srt(stem: str) -> None:
    (web._output_dir / f'{stem}.transcript.txt').write_text('dummy transcript', encoding='utf-8')
    (web._output_dir / f'{stem}.srt').write_text('1\n00:00:00,000 --> 00:00:01,000\nhello\n', encoding='utf-8')


def test_index_serves_page(client):
    r = client.get('/')
    assert r.status_code == 200
    # basic sanity: should serve some HTML
    assert b'<!DOCTYPE html' in r.data or b'<html' in r.data


def test_index_language_routing(client):
    # 1) explicit zh query param sets cookie and returns zh page
    r = client.get('/?lang=zh')
    assert r.status_code == 200
    assert ('Set-Cookie' in r.headers) or (r.headers.get('set-cookie') is not None)
    # 2) cookie persists zh selection
    r2 = client.get('/', headers={'Cookie': 'lang=zh'})
    assert r2.status_code == 200
    # 3) Accept-Language zh influences selection when no query/cookie
    r3 = client.get('/', headers={'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'})
    assert r3.status_code == 200
    # (Light heuristic: both zh and en pages are html; just ensure 200 sequence works.)


def test_summarize_endpoint_success(client, monkeypatch):
    # Patch summary generator to return deterministic text
    monkeypatch.setattr(web, 'generate_summary_text', lambda *a, **k: 'unit summary')  # noqa: ARG005
    r = client.post('/api/summarize', json={'transcript': 'abc', 'context_length': 0})
    assert r.status_code == 200
    assert r.get_json()['summary'] == 'unit summary'


def test_video_to_audio_success(client, monkeypatch):
    # Patch extract_audio to synthesize output wav under output/
    def fake_extract(video_path: Path, outdir: Path, **kwargs):  # noqa: ARG001
        out_path = web._audio_file_from_video(video_path)
        _write_wav(out_path)
        return out_path

    monkeypatch.setattr(web, 'extract_audio', fake_extract)

    data = {
        'video': (io.BytesIO(b'\x00' * 16), 'sample.mp4'),
    }
    r = client.post('/api/video-to-audio', data=data, content_type='multipart/form-data')
    assert r.status_code == 200
    js = r.get_json()
    assert 'audio_id' in js and js['download_url'].startswith('/api/download/audio/')

    # Download the generated audio
    r2 = client.get(js['download_url'])
    assert r2.status_code == 200
    assert r2.data.startswith(b'RIFF')


def test_audio_to_transcript_with_upload(client, monkeypatch):
    # Patch transcribe to return text and create transcript/srt files
    def fake_transcribe(audio_path: Path, outdir: Path, whisper_model: str, language=None):  # noqa: ARG001
        stem = audio_path.stem
        _write_transcript_and_srt(stem)
        return 'unit transcript'

    monkeypatch.setattr(web, 'transcribe_audio', fake_transcribe)

    data = {
        'audio': (io.BytesIO(b'\x00' * 16), 'sample.wav'),
    }
    r = client.post('/api/audio-to-transcript', data=data, content_type='multipart/form-data')
    assert r.status_code == 200
    js = r.get_json()
    assert js['transcript'] == 'unit transcript'
    assert js['download_transcript_url'] and js['download_srt_url']

    # Verify download endpoints work
    r_t = client.get(js['download_transcript_url'])
    r_s = client.get(js['download_srt_url'])
    assert r_t.status_code == 200 and r_s.status_code == 200


def test_pipeline_success(client, monkeypatch):
    # Patch extract/transcribe/summary for full pipeline
    def fake_extract(video_path: Path, outdir: Path, **kwargs):  # noqa: ARG001
        out_path = web._audio_file_from_video(video_path)
        _write_wav(out_path)
        return out_path

    def fake_transcribe(audio_path: Path, outdir: Path, whisper_model: str, language=None):  # noqa: ARG001
        stem = audio_path.stem
        _write_transcript_and_srt(stem)
        return 'pipeline transcript'

    monkeypatch.setattr(web, 'extract_audio', fake_extract)
    monkeypatch.setattr(web, 'transcribe_audio', fake_transcribe)
    monkeypatch.setattr(web, 'generate_summary_text', lambda *a, **k: 'pipeline summary')  # noqa: ARG005

    data = {
        'video': (io.BytesIO(b'\x00' * 16), 'input.mp4'),
        'whisper_model': 'tiny',
        'ollama_model': 'dummy',
        'context_length': '0',
    }
    r = client.post('/api/pipeline', data=data, content_type='multipart/form-data')
    assert r.status_code == 200
    js = r.get_json()
    assert js['transcript'] == 'pipeline transcript'
    assert js['summary'] == 'pipeline summary'
    assert js['download_transcript_url'] and js['download_srt_url']


def test_error_responses_and_sse_pipeline(client, monkeypatch):
    # 1) Missing video should yield 400 on /api/pipeline
    r = client.post('/api/pipeline')
    assert r.status_code == 400

    # 2) Summarize with empty transcript -> 422
    r2 = client.post('/api/summarize', json={'transcript': ''})
    assert r2.status_code == 422

    # 3) Async pipeline start and then poll events stream & result
    def fake_extract(video_path: Path, outdir: Path, **kwargs):  # noqa: ARG001
        out_path = web._audio_file_from_video(video_path)
        _write_wav(out_path)
        return out_path

    def fake_transcribe(audio_path: Path, outdir: Path, whisper_model: str, language=None):  # noqa: ARG001
        stem = audio_path.stem
        _write_transcript_and_srt(stem)
        return 'async transcript'

    monkeypatch.setattr(web, 'extract_audio', fake_extract)
    monkeypatch.setattr(web, 'transcribe_audio', fake_transcribe)
    monkeypatch.setattr(web, 'generate_summary_text', lambda *a, **k: 'async summary')  # noqa: ARG005
    monkeypatch.setattr(web, 'transcribe_audio', lambda *a, **k: 'ok-transcript')  # noqa: ARG005

    data = {
        'video': (io.BytesIO(b'\x00' * 16), 'async.mp4'),
        'ollama_model': 'dummy',
    }
    start_resp = client.post('/api/pipeline/start', data=data, content_type='multipart/form-data')
    assert start_resp.status_code == 200
    job_id = start_resp.get_json()['job_id']
    # Stream events (consume until done)
    events_resp = client.get(f'/api/pipeline/events/{job_id}', buffered=True)
    assert events_resp.status_code == 200
    text = events_resp.get_data(as_text=True)
    assert 'Starting pipeline' in text and 'done' in text
    # Poll result endpoint (should be done immediately in test)
    result_resp = client.get(f'/api/pipeline/result/{job_id}')
    js = result_resp.get_json()
    assert js['status'] == 'done'
    assert js['summary'] == 'async summary'
