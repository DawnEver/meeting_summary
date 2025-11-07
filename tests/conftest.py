# Ensure the package in src/ is importable without installation
import sys
import types
from pathlib import Path

# Add src path to sys.path
ROOT = Path(__file__).resolve().parents[1]
src_path = ROOT / 'src'
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Stub external heavy/optional dependencies so imports succeed in unit tests
# 1) Stub 'whisper' used by meeting_summary.transcribe
if 'whisper' not in sys.modules:
    whisper_mod = types.ModuleType('whisper')

    def _fake_load_model(name):  # noqa: ARG001
        # Return object with a transcribe method
        obj = types.SimpleNamespace()
        obj.transcribe = lambda *a, **k: {  # noqa: ARG005
            'text': 'dummy transcript',
            'segments': [{'start': 0.0, 'end': 1.0, 'text': 'hello'}],
        }
        return obj

    whisper_mod.load_model = _fake_load_model
    sys.modules['whisper'] = whisper_mod

# 2) Stub 'litellm' used by meeting_summary.summarize
if 'litellm' not in sys.modules:
    litellm_mod = types.ModuleType('litellm')

    def _fake_completion(*args, **kwargs):  # noqa: ARG001
        # Minimal shape compatible with summarize._request_summary
        return {
            'choices': [
                {'message': {'content': 'stub summary'}},
            ]
        }

    litellm_mod.completion = _fake_completion
    sys.modules['litellm'] = litellm_mod
