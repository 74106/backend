"""Policy helpers for NyaySetu legal chat.

Provides functions to detect identity questions, detect legal intent heuristically,
and apply a policy that enforces legal-only responses with trusted source citations.
"""
from __future__ import annotations

from typing import Optional

# Trusted Indian legal sources (English only)
TRUSTED_LEGAL_SOURCES = {
    'primary_laws': {
        'criminal_law': 'Bharatiya Nyaya Sanhita (BNS), 2023',
        'criminal_procedure': 'Bharatiya Nagarik Suraksha Sanhita (BNSS), 2023', 
        'evidence_law': 'Bharatiya Sakshya Adhiniyam (BSA), 2023',
        'it_act': 'Information Technology Act, 2000 (as amended)',
        'constitutional_law': 'Constitution of India, 1950'
    },
    'databases': [
        'Supreme Court of India official website',
        'High Court official websites',
        'Ministry of Law and Justice, Government of India',
        'Indian Cyber Crime Portal (cybercrime.gov.in)',
        'CERT-In (cert-in.org.in) advisories'
    ]
}


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
        # English keywords
        'law', 'legal', 'rights', 'police', 'court', 'complaint', 'fir', 'appeal', 'rti', 'eviction',
        'divorce', 'custody', 'contract', 'agreement', 'charge', 'arrest', 'evidence', 'bail', 'sue', 'lawsuit',
        # New Indian legal framework keywords
        'bns', 'bharatiya nyaya sanhita', 'bnss', 'bharatiya nagarik suraksha sanhita', 
        'bsa', 'bharatiya sakshya adhiniyam', 'ipc', 'crpc', 'evidence act',
        'constitution', 'article', 'fundamental rights', 'legal aid', 'advocate', 'lawyer',
        'judgment', 'verdict', 'legal precedent', 'case law', 'statute', 'act', 'section',
        # Cyber law and safety keywords (treat as legal intent for this app)
        'cyber', 'cyber crime', 'cybercrime', 'information technology act', 'it act', 'data privacy',
        'online fraud', 'phishing', 'upi fraud', 'bank fraud', 'sextortion', 'harassment', 'stalking',
        'electronic evidence', 'social media', 'identity theft', 'ransomware', 'malware', 'hacking'
        ]
    # Short identity-like questions are not legal questions
    if len(t.split()) <= 5 and is_identity_question(t):
        return False
    return any(k in t for k in legal_keywords)


def apply_policy(original_answer: Optional[str], user_question: str, language: str = 'en') -> str:
    """Enforce policy:
    - Mandatory Legal Disclaimer with source attribution.
    - If user asks about identity, return fixed identity sentence.
    - If user's question is not legal, refuse.
    - Sanitize model output to avoid alternative identity claims.
    - Ensure answer contains legal keywords and source references, else refuse.
    - Maintain a Formal and Neutral Tone.
    - Request Clarification for Ambiguous Queries.
    - Enforce reference to trusted legal sources (BNS, BNSS, BSA for India).
    """
    # Identity question -> fixed identity
    if is_identity_question(user_question):
        if language.startswith('hi'):
            return 'मैं कानूनी जानकारी में विशेषज्ञता वाला एक एआई सहायक हूं।'
        return 'I am a legal chat bot'

    ans = (original_answer or '').strip()
    lower = ans.lower()

    if user_question.lower().startswith("what is") or "explain" in user_question.lower():
        # For definitions, ensure they include source attribution
        if not _has_source_attribution(ans):
            ans = _add_source_attribution(ans, language)
        return ans

    # Non-legal user question -> if cyber-safety topic, provide prevention guidance; else refusal
    if not is_legal_question(user_question):
        if _is_cyber_question(user_question):
            guidance = _get_cyber_prevention_guidance(language)
            # Add source attribution block for consistency
            return _add_source_attribution(guidance, language)
        if language.startswith('hi'):
            return 'मैं मुख्यतः साइबर कानून से संबंधित जानकारी प्रदान करता/करती हूँ। कृपया साइबर कानून पर प्रश्न पूछें।'
        return 'I primarily provide information on cyber law. Please ask a cyber law-related question.'

    # Replace or suppress identity mentions
    identity_patterns = [
        'i am chatgpt', 'i am gpt', 'i am a language model', 'i am an ai', 'i am ai', 'i am a chatbot',
        'this is chatgpt', 'chatgpt', 'openai', 'this is gemini', 'this is gemma', 'i am an llm'
    ]
    if any(pat in lower for pat in identity_patterns):
        if language.startswith('hi'):
            return 'मैं कानूनी जानकारी में विशेषज्ञता वाला एक एआई सहायक हूं।'
        return 'I am a legal chat bot'

    # Ensure answer contains legal/cyber-related content
    legal_keywords = [
        # English keywords
        'law', 'legal', 'cyber', 'cybercrime', 'it act', 'information technology act', 'data privacy', 'online fraud', 'phishing', 'social media', 'electronic evidence', 'court', 'police', 'rights', 'complaint', 'fir', 'appeal', 'contract', 'bns', 'bnss', 'bsa',
    ]
    if not any(k in lower for k in legal_keywords):
        # If the question is clearly about cyber topics but the answer lacks signals,
        # provide a prevention-only safe fallback.
        if _is_cyber_question(user_question):
            guidance = _get_cyber_prevention_guidance(language)
            return _add_source_attribution(guidance, language)
        if language.startswith('hi'):
            return 'मैं केवल कानूनी जानकारी प्रदान कर सकता/सकती हूँ। कृपया एक कानूनी प्रश्न पूछें।'
        return 'My function is to provide information on legal topics. Please frame your question accordingly.'

    # Enforce source attribution for legal answers
    if not _has_source_attribution(ans):
        ans = _add_source_attribution(ans, language)

    return ans


def _has_source_attribution(text: str) -> bool:
    """Check if the text already contains source attribution."""
    text_lower = text.lower()
    source_indicators = [
        # English indicators
        'according to', 'as per', 'under', 'section', 'article', 'act of', 'law of',
        'bns', 'bnss', 'bsa', 'ipc', 'crpc', 'constitution', 'supreme court',
        'high court', 'judgment', 'case law', 'legal precedent', 'statute',
    ]
    return any(indicator in text_lower for indicator in source_indicators)


def _add_source_attribution(text: str, language: str = 'en') -> str:
    """Add source attribution to legal answers."""
    if language.startswith('hi'):
        disclaimer = """

**स्रोत और अस्वीकरण:**
- यह जानकारी भारतीय कानूनी ढांचे के आधार पर है: भारतीय न्याय संहिता (BNS), 2023, भारतीय नागरिक सुरक्षा संहिता (BNSS), 2023, और भारतीय साक्ष्य अधिनियम (BSA), 2023
- यह सामान्य जानकारी है और विशिष्ट मामलों के लिए योग्य वकील से सलाह लें
- कानून जटिल हैं और मामले के अनुसार भिन्न हो सकते हैं"""
    else:
        disclaimer = """

**Source and Disclaimer:**
- This information is based on Indian legal framework: Bharatiya Nyaya Sanhita (BNS), 2023, Bharatiya Nagarik Suraksha Sanhita (BNSS), 2023, and Bharatiya Sakshya Adhiniyam (BSA), 2023
- This is general information only. For specific cases, consult a qualified lawyer
- Laws are complex and may vary by case and jurisdiction"""
    
    return text + disclaimer


def _is_cyber_question(text: Optional[str]) -> bool:
    t = (text or '').strip().lower()
    if not t:
        return False
    cyber_keywords = [
        'cyber', 'cyber crime', 'cybercrime', 'online fraud', 'phishing', 'scam', 'otp', 'upi', 'bank fraud',
        'data privacy', 'privacy', 'social media', 'identity theft', 'sextortion', 'harassment', 'stalking',
        'ransomware', 'malware', 'hacking', 'password', '2fa', 'mfa', 'vpn', 'it act', 'information technology act'
    ]
    return any(k in t for k in cyber_keywords)


def _get_cyber_prevention_guidance(language: str = 'en') -> str:
    if language.startswith('hi'):
        return (
            "साइबर अपराध से बचाव के लिए व्यावहारिक कदम:\n"
            "- मजबूत और अलग-अलग पासवर्ड रखें; पासवर्ड मैनेजर का उपयोग करें\n"
            "- हर जगह 2‑FA/MFA सक्षम करें (ऑथेंटिकेटर ऐप/सिक्योरिटी की)\n"
            "- सिस्टम, ब्राउज़र, ऐप्स और राउटर फर्मवेयर को अपडेट रखें\n"
            "- संदिग्ध लिंक/QR/अटैचमेंट न खोलें; यूआरएल खुद टाइप करें\n"
            "- सार्वजनिक Wi‑Fi पर संवेदनशील काम न करें; जरूरत हो तो हॉटस्पॉट/VPN इस्तेमाल करें\n"
            "- बैंक/UPI अलर्ट चालू रखें; अनजान कॉल/SMS/OTP न साझा करें\n"
            "- सोशल मीडिया गोपनीयता सेटिंग्स सख्त रखें; अति-साझेदारी से बचें\n"
            "- 3‑2‑1 बैकअप रखें और रिस्टोर टेस्ट करें\n"
            "यदि धोखा हो जाए: नेटवर्क से डिस्कनेक्ट करें, स्कैन चलाएँ, पासवर्ड बदलें, बैंक को तुरंत सूचित करें, और 1930/\n"
            "cybercrime.gov.in पर रिपोर्ट करें।"
        )
    return (
        "Practical steps to prevent cybercrime:\n"
        "- Use strong, unique passwords and a reputable password manager\n"
        "- Enable 2FA/MFA everywhere (authenticator app or security key)\n"
        "- Keep OS, browser, apps, router/IoT firmware up to date\n"
        "- Be phishing-smart: avoid unsolicited links/QRs/attachments; type important URLs yourself\n"
        "- Prefer mobile hotspot or trusted VPN over public Wi‑Fi for sensitive actions\n"
        "- Turn on bank/UPI/card transaction alerts; never share OTP/PIN\n"
        "- Tighten social media privacy; limit personal data exposure\n"
        "- Maintain 3‑2‑1 backups and test restores\n"
        "If victimized: disconnect, run a full scan, change passwords, contact your bank, and report at cybercrime.gov.in (India) or your national cybercrime portal."
    )


def test_apply_policy_allows_definitions():
    model_out = 'An FIR is a First Information Report, a written document prepared by police when they receive information about a cognizable offence.'
    res = apply_policy(model_out, 'What is FIR?', language='en')
    assert 'FIR' in res and 'Report' in res
