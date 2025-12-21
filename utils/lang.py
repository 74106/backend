from __future__ import annotations

"""Language utilities: detection and translation wrappers.

We use deep-translator for translation. Language detection is heuristic with optional
fasttext if installed. Keep all imports lazy to avoid hard dependencies.
"""

from typing import Tuple


def detect_language(text: str) -> str:
	"""Best-effort language detection. Returns IETF code like 'en', 'hi', 'fr', 'es', etc.
	
	Supports any language that langdetect can detect. Uses Google Translator's language codes.
	If detection fails, uses Unicode heuristics for common Indian scripts, then defaults to 'en'.
	"""
	text = (text or "").strip()
	if not text:
		return 'en'
	
	# Try langdetect first - it supports many languages
	try:
		from langdetect import detect  # type: ignore
		code = detect(text)
		# Return the detected code directly - Google Translator supports many languages
		# Only validate it's a reasonable length (2-5 chars for language codes)
		if code and len(code) >= 2 and len(code) <= 5:
			return code
	except Exception:
		pass

	# Unicode block heuristics for common Indian scripts (fallback)
	first = ord(text[0])
	# Devanagari range
	if 0x0900 <= first <= 0x097F:
		return 'hi'
	# Bengali
	if 0x0980 <= first <= 0x09FF:
		return 'bn'
	# Gurmukhi (Punjabi)
	if 0x0A00 <= first <= 0x0A7F:
		return 'pa'
	# Gujarati
	if 0x0A80 <= first <= 0x0AFF:
		return 'gu'
	# Oriya (Odia)
	if 0x0B00 <= first <= 0x0B7F:
		return 'or'
	# Tamil
	if 0x0B80 <= first <= 0x0BFF:
		return 'ta'
	# Telugu
	if 0x0C00 <= first <= 0x0C7F:
		return 'te'
	# Kannada
	if 0x0C80 <= first <= 0x0CFF:
		return 'kn'
	# Malayalam
	if 0x0D00 <= first <= 0x0D7F:
		return 'ml'
	
	# Final fallback to English if nothing matches
	return 'en'


def translate(text: str, source_lang: str, target_lang: str) -> str:
	"""Translate text using deep-translator if available; otherwise pass-through.

	Avoid translating when source == target.
	"""
	text = text or ''
	if not text:
		return ''
	if (source_lang or 'en') == (target_lang or 'en'):
		return text
	try:
		from deep_translator import GoogleTranslator  # type: ignore
		return GoogleTranslator(source=source_lang or 'auto', target=target_lang or 'en').translate(text)
	except Exception:
		return text


def translate_pair(question_text: str, user_lang: str) -> Tuple[str, str]:
	"""Translate incoming text to English for internal processing, return tuple
	(original_detected_lang, english_text).
	"""
	detected = user_lang or detect_language(question_text)
	to_english = translate(question_text, detected, 'en')
	return detected, to_english


