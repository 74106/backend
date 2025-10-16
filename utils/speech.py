from __future__ import annotations

"""Speech utilities: transcription via faster-whisper if available.

We keep imports lazy so the app runs even without STT packages.
"""

from typing import Optional


def transcribe_audio_bytes(audio_bytes: bytes, language: Optional[str] = None) -> Optional[str]:
	"""Transcribe audio using faster-whisper if installed.

	Supports common formats when ffmpeg is available in PATH.
	Returns a best-effort transcript string or None on failure.
	"""
	if not audio_bytes:
		return None
	try:
		from faster_whisper import WhisperModel  # type: ignore
		import io
		model_name = 'small'
		compute_type = 'int8'
		model = WhisperModel(model_name, device='cpu', compute_type=compute_type)
		buf = io.BytesIO(audio_bytes)
		segments, info = model.transcribe(buf, language=language, beam_size=1)
		texts = []
		for seg in segments:
			texts.append(seg.text)
		return " ".join(t.strip() for t in texts if t and t.strip()) or None
	except Exception:
		# STT not available or failed
		return None


