"""Policy helpers for NyaySetu legal chat.

Provides functions to detect identity questions, detect legal intent heuristically,
and apply a policy that enforces legal-only responses and a fixed identity reply.
"""
from __future__ import annotations

from typing import Optional


def is_identity_question(text: Optional[str]) -> bool:
    t = (text or '').strip().lower()
    triggers = [
        "who are you",
        "what are you",
        "who is this",
        "identify yourself",
        "what is your name",
        "are you a bot",
    ]
    return any(trigger in t for trigger in triggers)


def is_legal_question(text: Optional[str]) -> bool:
    t = (text or '').strip().lower()
    legal_keywords = [
        'law', 'legal', 'rights', 'police', 'court', 'complaint', 'fir', 'appeal', 'rti', 'eviction',
        'divorce', 'custody', 'contract', 'agreement', 'charge', 'arrest', 'evidence', 'bail', 'sue', 'lawsuit'
    ]
    # Short identity-like questions are not legal questions
    if len(t.split()) <= 5 and is_identity_question(t):
        return False
    return any(k in t for k in legal_keywords)


def apply_policy(original_answer: Optional[str], user_question: str, language: str = 'en') -> str:
    """Enforce policy:
    - Mandatory Legal Disclaimer.
    - If user asks about identity, return fixed identity sentence.
    - If user's question is not legal, refuse.
    - Sanitize model output to avoid alternative identity claims.
    - Ensure answer contains legal keywords, else refuse.
    - Maintain a Formal and Neutral Tone.
    - Request Clarification for Ambiguous Queries.
    """
    # Identity question -> fixed identity
    if is_identity_question(user_question):
        if language.startswith('hi'):
            return 'मैं कानूनी जानकारी में विशेषज्ञता वाला एक एआई सहायक हूं।'
        return 'I am an AI assistant specializing in legal information.'

    # Non-legal user question -> refusal
    if not is_legal_question(user_question):
        if language.startswith('hi'):
            return 'मैं केवल कानूनी जानकारी प्रदान कर सकता/सकती हूँ। कृपया एक कानूनी प्रश्न पूछें।'
        return 'I can only provide legal knowledge. Please ask a legal question.'

    ans = (original_answer or '').strip()
    lower = ans.lower()

    # Replace or suppress identity mentions
    identity_patterns = [
        'i am chatgpt', 'i am gpt', 'i am a language model', 'i am an ai', 'i am ai', 'i am a chatbot',
        'this is chatgpt', 'chatgpt', 'openai' , 'this is gemini', 'this is gemma', 'i am an llm'
    ]
    if any(pat in lower for pat in identity_patterns):
        if language.startswith('hi'):
            return 'मैं कानूनी जानकारी में विशेषज्ञता वाला एक एआई सहायक हूं।'
        return 'I am an AI assistant specializing in legal information.'

    # Ensure answer contains legal-related content
    if not any(k in ans.lower() for k in ['law', 'legal', 'court', 'police', 'rights', 'complaint', 'fir', 'appeal', 'contract']):
        if language.startswith('hi'):
            return 'मैं केवल कानूनी जानकारी प्रदान कर सकता/सकती हूँ। कृपया एक कानूनी प्रश्न पूछें।'
        return 'My function is to provide information on legal topics. Please frame your question accordingly.'

    return ans

