"""Flask web service with multi-step meeting processing pipeline.

Endpoints:
    POST /api/video-to-audio      -> upload video, extract WAV audio (reuses existing ffmpeg wrapper)
    GET  /api/download/audio/<id> -> download generated audio file
    POST /api/audio-to-transcript -> upload audio OR reference audio_id, returns transcript text
    POST /api/summarize           -> summarize transcript (existing generate_summary_text)
    POST /api/pipeline            -> one-click: video -> audio -> transcript -> summary

The existing helper functions reused:
    extract_audio.extract_audio(video_path, outdir, audio_path=None, sample_rate=16000)
    transcribe.transcribe_audio(audio_path, outdir, whisper_model, language=None)

Run locally:
    python -m meeting_summary.web

"""

from __future__ import annotations

import json
import mimetypes
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from flask import (
    Flask,
    Response,
    abort,
    jsonify,
    request,
    send_file,
    send_from_directory,
    stream_with_context,
)
from werkzeug.utils import secure_filename

from .extract_audio import extract_audio
from .summarize import generate_summary_text
from .transcribe import transcribe_audio
from .utils import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS

_ALLOWED_VIDEO_EXT = set(VIDEO_EXTENSIONS)
_ALLOWED_AUDIO_EXT = set(AUDIO_EXTENSIONS)

# ---------------------------------------------------------------------------
# Paths & app setup
# ---------------------------------------------------------------------------
_pkg_dir = Path(__file__).resolve().parent  # .../src/meeting_summary
_project_root = _pkg_dir.parent.parent  # repository root
_static_dir = _pkg_dir / 'static'
_output_dir = _project_root / 'output'
_upload_dir = _output_dir / 'uploads'
_output_dir.mkdir(parents=True, exist_ok=True)
_upload_dir.mkdir(parents=True, exist_ok=True)

app = Flask(
    __name__,
    static_folder=str(_static_dir),
    static_url_path='/static',
)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024  # 2GB upload cap


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _save_upload(field: str, allowed_exts: set[str]) -> Path:
    if field not in request.files:
        abort(400, description=f'Missing file field: {field}')
    f = request.files[field]
    if not f or f.filename is None:
        abort(400, description='Empty upload')
    original = secure_filename(f.filename)
    ext = Path(original).suffix.lower()
    if ext and allowed_exts and ext not in allowed_exts:
        abort(400, description=f'Unsupported extension: {ext}')
    # Use uuid to avoid collisions; keep extension if present.
    new_name = f'{uuid.uuid4().hex}{ext or ""}'
    dest = _upload_dir / new_name
    f.save(dest)
    return dest


def _audio_file_from_video(video_path: Path) -> Path:
    """Return expected audio file path after extraction (extract_audio overwrites name)."""
    return _output_dir / (video_path.stem + '.wav')


def _validate_audio_id(audio_id: str) -> Path:
    """Locate an uploaded or generated audio file by id.

    Historically uploaded audio files were stored under `output/uploads/`, while
    generated (video ➜ audio) files live directly under `output/`. The original
    validation only checked the root, causing 404 errors for directly uploaded
    audio when requesting transcript/SRT downloads.

    This function now searches both locations and returns the existing path.
    """
    p_root = (_output_dir / audio_id).resolve()
    p_upload = (_upload_dir / audio_id).resolve()
    # Security: ensure resolved parents are expected directories
    valid_parents = {str(_output_dir.resolve()), str(_upload_dir.resolve())}
    candidate: Path | None = None
    if p_root.exists() and str(p_root.parent) in valid_parents:
        candidate = p_root
    elif p_upload.exists() and str(p_upload.parent) in valid_parents:
        candidate = p_upload
    if candidate is None:
        abort(404, description='Audio file not found')
    if candidate.suffix.lower() not in _ALLOWED_AUDIO_EXT:
        abort(400, description='Unsupported audio extension')
    return candidate


# ---------------------------------------------------------------------------
# Pipeline jobs for progress SSE
# ---------------------------------------------------------------------------


@dataclass
class PipelineJob:
    job_id: str
    created_at: float = field(default_factory=time.time)
    messages: list[dict] = field(default_factory=list)  # [{type, text, ts}]
    result: dict | None = None
    error: str | None = None
    done: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _cv: threading.Condition = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._cv = threading.Condition(self._lock)

    def push(self, typ: str, text: str):
        with self._lock:
            evt = {'type': typ, 'text': text, 'ts': time.time()}
            self.messages.append(evt)
            self._cv.notify_all()

    def complete(self, result: dict | None = None, error: str | None = None):
        with self._lock:
            self.result = result
            self.error = error
            self.done = True
            self._cv.notify_all()


_JOBS: dict[str, PipelineJob] = {}
_JOBS_LOCK = threading.Lock()


def _new_job() -> PipelineJob:
    job_id = uuid.uuid4().hex
    job = PipelineJob(job_id)
    with _JOBS_LOCK:
        _JOBS[job_id] = job
    return job


def _get_job(job_id: str) -> PipelineJob:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
    if not job:
        abort(404, description='Job not found')
    return job


def _run_pipeline_job(
    job: PipelineJob,
    video_path: Path,
    whisper_model: str,
    ollama_model: str,
    context_length: int | None,
    extra_prompt: str | None,
):
    audio_path: Path | None = None
    try:
        job.push('info', 'Starting pipeline: video ➜ audio ➜ transcript ➜ summary')
        # 1) video -> audio
        job.push('step', 'Extracting audio...')
        audio_path = extract_audio(video_path=video_path, outdir=_output_dir)
        if not audio_path.exists():  # defensive, normally exists
            msg = 'Audio file missing after extraction'
            raise RuntimeError(msg)  # noqa: TRY301
        job.push('ok', f'Audio ready: {audio_path.name}')

        # 2) audio -> transcript
        job.push('step', f'Transcribing with Whisper model "{whisper_model}"...')
        transcript = transcribe_audio(
            audio_path=audio_path, outdir=_output_dir, whisper_model=whisper_model, language=None
        )
        job.push('ok', 'Transcription completed')

        # 3) transcript -> summary
        job.push('step', f'Generating summary with model "{ollama_model}"...')
        summary = generate_summary_text(
            transcript,
            ollama_model=ollama_model,
            context_length=context_length,
            extra_prompt=extra_prompt,
            log_progress=False,
        )
        if not summary:
            msg = 'Summary generation returned empty result'
            raise RuntimeError(msg)  # noqa: TRY301
        job.push('ok', 'Summary completed')

        job.complete({
            'audio_id': audio_path.name,
            'download_url': f'/api/download/audio/{audio_path.name}',
            'download_transcript_url': f'/api/download/transcript/{audio_path.name}'
            if (_output_dir / f'{audio_path.stem}.transcript.txt').exists()
            else None,
            'download_srt_url': f'/api/download/srt/{audio_path.name}'
            if (_output_dir / f'{audio_path.stem}.srt').exists()
            else None,
            'transcript': transcript,
            'summary': summary,
        })
    except Exception as e:
        job.push('error', f'Pipeline failed: {e}')
        job.complete(None, error=str(e))
    finally:
        try:
            # cleanup uploaded video to save space
            if video_path.exists():
                video_path.unlink(missing_ok=True)
        except Exception as e:
            # Log cleanup errors for visibility instead of silently ignoring them.
            job.push('error', f'Failed to cleanup uploaded video {e}')
            job.complete(None, error=str(e))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get('/')
def index():  # type: ignore[override]
    """Serve UI based on ?lang, cookie, or Accept-Language; default English.

    Priority:
    1) ?lang=zh|en (sets cookie)
    2) cookie 'lang'
    3) Accept-Language header
    4) default: en
    """
    if not _static_dir.exists():
        abort(500, description='Static directory missing')

    # 1) explicit query
    q_lang = request.args.get('lang')
    if q_lang in {'zh', 'en'}:
        filename = 'index_zh.html' if q_lang == 'zh' else 'index.html'
        resp = send_from_directory(str(_static_dir), filename)
        # set cookie for future visits
        resp.set_cookie('lang', q_lang, max_age=60 * 60 * 24 * 365, httponly=False, samesite='Lax')
        return resp

    # 2) cookie
    c_lang = request.cookies.get('lang')
    if c_lang in {'zh', 'en'}:
        filename = 'index_zh.html' if c_lang == 'zh' else 'index.html'
        return send_from_directory(str(_static_dir), filename)

    # 3) Accept-Language
    accept = (request.headers.get('Accept-Language') or '').lower()
    # very light-weight detection
    prefer_zh = any(tag.startswith('zh') for tag in accept.replace(' ', '').split(','))
    filename = 'index_zh.html' if prefer_zh else 'index.html'

    # 4) fallback if file missing
    path = _static_dir / filename
    if not path.exists():
        filename = 'index.html' if filename == 'index_zh.html' else 'index_zh.html'
    return send_from_directory(str(_static_dir), filename)


@app.post('/api/video-to-audio')
def video_to_audio():  # type: ignore[override]
    video_path = _save_upload('video', _ALLOWED_VIDEO_EXT)
    try:
        extract_audio(video_path=video_path, outdir=_output_dir)
    except Exception as e:
        abort(502, description=f'Audio extraction failed: {e}')
    audio_path = _audio_file_from_video(video_path)
    if not audio_path.exists():
        abort(502, description='Audio file missing after extraction')
    audio_id = audio_path.name
    return jsonify({
        'audio_id': audio_id,
        'download_url': f'/api/download/audio/{audio_id}',
    })


@app.get('/api/download/audio/<audio_id>')
def download_audio(audio_id: str):  # type: ignore[override]
    audio_path = _validate_audio_id(audio_id)
    mime, _ = mimetypes.guess_type(str(audio_path))
    return send_file(
        str(audio_path),
        as_attachment=True,
        download_name=audio_path.name,
        mimetype=mime or 'audio/wav',
    )


@app.get('/api/download/transcript/<audio_id>')
def download_transcript(audio_id: str):  # type: ignore[override]
    # Map audio id to transcript file under output/
    try:
        audio_path = _validate_audio_id(audio_id)
    except Exception:
        abort(404, description='Audio not found')
    transcript_path = _output_dir / f'{audio_path.stem}.transcript.txt'
    if not transcript_path.exists():
        abort(404, description='Transcript not found')
    return send_file(
        str(transcript_path),
        as_attachment=True,
        download_name=transcript_path.name,
        mimetype='text/plain',
    )


@app.get('/api/download/srt/<audio_id>')
def download_srt(audio_id: str):  # type: ignore[override]
    # Map audio id to srt file under output/
    try:
        audio_path = _validate_audio_id(audio_id)
    except Exception:
        abort(404, description='Audio not found')
    srt_path = _output_dir / f'{audio_path.stem}.srt'
    if not srt_path.exists():
        abort(404, description='SRT not found')
    return send_file(
        str(srt_path),
        as_attachment=True,
        download_name=srt_path.name,
        mimetype='text/plain',
    )


@app.post('/api/audio-to-transcript')
def audio_to_transcript():  # type: ignore[override]
    # Accept either uploaded audio OR existing audio_id referencing output dir
    transcript: str | None = None
    audio_path: Path | None = None
    if 'audio' in request.files and request.files['audio'].filename:
        audio_path = _save_upload('audio', _ALLOWED_AUDIO_EXT)
    else:
        audio_id = request.form.get('audio_id') or (request.json or {}).get('audio_id')
        if not audio_id:
            abort(400, description='Provide audio file or audio_id')
        audio_path = _validate_audio_id(audio_id)

    try:
        transcript = transcribe_audio(audio_path=audio_path, outdir=_output_dir, whisper_model='turbo', language=None)
    except Exception as e:
        abort(502, description=f'Transcription failed: {e}')
    # Build download URLs for transcript and srt (if file exists)
    stem = audio_path.stem
    transcript_path = _output_dir / f'{stem}.transcript.txt'
    srt_path = _output_dir / f'{stem}.srt'
    resp = {
        'transcript': transcript,
        'audio_id': audio_path.name,
        'download_transcript_url': f'/api/download/transcript/{audio_path.name}' if transcript_path.exists() else None,
        'download_srt_url': f'/api/download/srt/{audio_path.name}' if srt_path.exists() else None,
    }
    return jsonify(resp)


@app.post('/api/summarize')
def summarize():  # type: ignore[override]
    data = request.get_json(silent=True) or {}
    transcript = (data.get('transcript') or '').strip()
    if not transcript:
        abort(422, description='Transcript cannot be empty')
    ollama_model = data.get('ollama_model') or 'qwen3:30b-a3b'
    context_length_raw = data.get('context_length') or 0
    extra_prompt = data.get('extra_prompt')
    context_length = None if not context_length_raw or int(context_length_raw) == 0 else int(context_length_raw)
    try:
        summary = generate_summary_text(
            transcript,
            ollama_model=ollama_model,
            context_length=context_length,
            extra_prompt=extra_prompt,
            log_progress=False,
        )
    except Exception as e:
        abort(502, description=f'Summary generation failed: {e}')
    if not summary:
        abort(502, description='Empty summary')
    # return summary (markdown) as well as optional downloadable path info
    return jsonify({'summary': summary})


@app.post('/api/pipeline')
def pipeline():  # type: ignore[override]
    # Multipart form: video + optional context params
    if 'video' not in request.files:
        abort(400, description='Missing video file')
    video_path = _save_upload('video', _ALLOWED_VIDEO_EXT)
    # 1) video -> audio
    try:
        extract_audio(video_path=video_path, outdir=_output_dir)
    except Exception as e:
        abort(502, description=f'Audio extraction failed: {e}')
    audio_path = _audio_file_from_video(video_path)
    if not audio_path.exists():
        abort(502, description='Audio file missing after extraction')
    audio_id = audio_path.name

    # 2) audio -> transcript
    whisper_model = request.form.get('whisper_model') or 'turbo'
    language = request.form.get('language') or None
    try:
        transcript = transcribe_audio(
            audio_path=audio_path, outdir=_output_dir, whisper_model=whisper_model, language=language
        )
    except Exception as e:
        abort(502, description=f'Transcription failed: {e}')

    # 3) transcript -> summary
    ollama_model = request.form.get('ollama_model') or 'qwen3:30b-a3b'
    context_length_raw = request.form.get('context_length') or '0'
    extra_prompt = request.form.get('extra_prompt') or None
    context_length = None if context_length_raw in ('', '0', 0) else int(context_length_raw)
    try:
        summary = generate_summary_text(
            transcript,
            ollama_model=ollama_model,
            context_length=context_length,
            extra_prompt=extra_prompt,
            log_progress=False,
        )
    except Exception as e:
        abort(502, description=f'Summary generation failed: {e}')
    if not summary:
        abort(502, description='Empty summary')

    return jsonify({
        'audio_id': audio_id,
        'download_url': f'/api/download/audio/{audio_id}',
        'download_transcript_url': f'/api/download/transcript/{audio_id}'
        if (_output_dir / f'{Path(audio_id).stem}.transcript.txt').exists()
        else None,
        'download_srt_url': f'/api/download/srt/{audio_id}'
        if (_output_dir / f'{Path(audio_id).stem}.srt').exists()
        else None,
        'transcript': transcript,
        'summary': summary,
    })


@app.post('/api/pipeline/start')
def pipeline_start():  # type: ignore[override]
    """Start pipeline asynchronously and return a job id; progress via SSE."""
    if 'video' not in request.files:
        abort(400, description='Missing video file')
    video_path = _save_upload('video', _ALLOWED_VIDEO_EXT)
    whisper_model = request.form.get('whisper_model') or 'turbo'
    ollama_model = request.form.get('ollama_model') or 'qwen3:30b-a3b'
    context_length_raw = request.form.get('context_length') or '0'
    extra_prompt = request.form.get('extra_prompt') or None
    context_length = None if context_length_raw in ('', '0', 0) else int(context_length_raw)

    job = _new_job()
    t = threading.Thread(
        target=_run_pipeline_job,
        args=(job, video_path, whisper_model, ollama_model, context_length, extra_prompt),
        daemon=True,
    )
    t.start()
    return jsonify({'job_id': job.job_id})


@app.get('/api/pipeline/events/<job_id>')
def pipeline_events(job_id: str):  # type: ignore[override]
    job = _get_job(job_id)

    def event_stream():  # type: ignore[override]
        # replay past messages
        idx = 0
        while True:
            with job._lock:
                while idx < len(job.messages):
                    evt = job.messages[idx]
                    idx += 1
                    yield f'data: {json.dumps(evt, ensure_ascii=False)}\n\n'
                if job.done:
                    # When finishing, include any download urls in the done payload
                    payload = {'type': 'done', 'result': job.result, 'error': job.error, 'ts': time.time()}
                    yield f'data: {json.dumps(payload, ensure_ascii=False)}\n\n'
                    return
                # wait for new messages or completion
                job._cv.wait(timeout=1.0)

    headers = {
        'Cache-Control': 'no-cache',
        'Content-Type': 'text/event-stream; charset=utf-8',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',  # for some proxies
    }
    return Response(stream_with_context(event_stream()), headers=headers)


@app.get('/api/pipeline/result/<job_id>')
def pipeline_result(job_id: str):  # type: ignore[override]
    job = _get_job(job_id)
    with job._lock:
        if not job.done:
            return jsonify({'status': 'pending'})
        if job.error:
            return jsonify({'status': 'error', 'error': job.error}), 502
        return jsonify({'status': 'done', **(job.result or {})})


if __name__ == '__main__':  # pragma: no cover
    # app.run(host='0.0.0.0', port=8000, debug=True)
    app.run(host='0.0.0.0', port=8000)  # noqa: S104
