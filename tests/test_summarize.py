from meeting_summary import summarize


def test_generate_summary_chunking(monkeypatch):
    # Stub _request_summary to return deterministic value quickly.
    def fake_request(chunk_text: str, ollama_model: str, extra_prompt: str | None = None):  # noqa: ARG001
        # Return a short marker to keep output small.
        return f'SUMMARY:{len(chunk_text)}'

    monkeypatch.setattr(summarize, '_request_summary', fake_request)

    transcript = 'A' * 15  # 15 chars
    # Force chunking into size 5 to create 3 chunks
    result = summarize.generate_summary_text(
        transcript,
        ollama_model='dummy-model',
        context_length=5,
        extra_prompt=None,
        log_progress=False,
    )
    assert result is not None
    # Expect headings for each segment
    assert '### Segment 1' in result and '### Segment 2' in result and '### Segment 3' in result
    # Check that summaries correspond to chunk lengths (all 5 except last which may be 5)
    assert result.count('SUMMARY:5') >= 2


def test_generate_summary_all_none(monkeypatch):
    # Stub to simulate all failed requests
    def fake_request_fail(chunk_text: str, ollama_model: str, extra_prompt: str | None = None):  # noqa: ARG001
        return None

    monkeypatch.setattr(summarize, '_request_summary', fake_request_fail)
    transcript = 'Hello world'
    result = summarize.generate_summary_text(
        transcript,
        ollama_model='dummy-model',
        context_length=5,
        extra_prompt=None,
        log_progress=False,
    )
    assert result is None
