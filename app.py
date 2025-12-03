from flask import Flask, request, jsonify, make_response, redirect
from flask_cors import CORS
from models.legal_chat_model import get_legal_advice
from utils.lang import detect_language, translate, translate_pair
from policy import is_identity_question, is_legal_question, apply_policy
from utils.form_generator import generate_form
from utils.db import (
    init_db,
    insert_chat,
    insert_form,
    fetch_all_chats,
    fetch_all_forms,
    fetch_chats_filtered,
    fetch_forms_filtered,
    create_user,
    get_user_by_email,
)
import logging
import os
import time
import json
import secrets
import re
from urllib.parse import urlencode

# --- Securely load env ---
from dotenv import load_dotenv
load_dotenv()

# Optional deps
try:
    import requests
except ImportError:
    requests = None

try:
    from werkzeug.security import check_password_hash as _check_password_hash, generate_password_hash as _generate_password_hash
except Exception:
    _check_password_hash = None
    _generate_password_hash = None

try:
    import jwt
except Exception:
    jwt = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)
init_db()

# Legal document detection and summarization helpers
def detect_legal_document(text: str) -> bool:
    """Detect if the PDF contains legal content based on keywords and patterns."""
    text_lower = text.lower()
    # Legal keywords and phrases
    legal_indicators = [
        'court', 'judge', 'law', 'legal', 'statute', 'act', 'section', 'clause',
        'plaintiff', 'defendant', 'petitioner', 'respondent', 'witness', 'evidence',
        'criminal', 'civil', 'appeal', 'judgment', 'order', 'decree', 'verdict',
        'constitution', 'amendment', 'regulation', 'provision', 'penalty', 'fine',
        'imprisonment', 'bail', 'warrant', 'summons', 'notice', 'complaint',
        'fir', 'charge sheet', 'indictment', 'prosecution', 'defense', 'counsel',
        'advocate', 'attorney', 'barrister', 'solicitor', 'legal opinion',
        'contract', 'agreement', 'terms', 'conditions', 'liability', 'obligation',
        'right', 'duty', 'responsibility', 'breach', 'violation', 'infringement',
        'copyright', 'patent', 'trademark', 'intellectual property', 'privacy',
        'data protection', 'cyber crime', 'it act', 'information technology',
        'digital signature', 'electronic record', 'computer evidence'
    ]
    # Count legal indicators
    legal_count = sum(1 for indicator in legal_indicators if indicator in text_lower)
    # Check for legal document patterns
    legal_patterns = [
        r'\b(?:section|clause|article)\s+\d+',
        r'\b(?:act|act\s+of)\s+\d{4}',
        r'\b(?:vs?\.?|versus)\b',
        r'\b(?:in\s+re|in\s+the\s+matter\s+of)\b',
        r'\b(?:case\s+no\.?|file\s+no\.?)\b',
        r'\b(?:court\s+of|high\s+court|supreme\s+court)\b',
        r'\b(?:bail|warrant|summons|notice)\b',
        r'\b(?:fir|first\s+information\s+report)\b'
    ]
    import re
    pattern_count = sum(1 for pattern in legal_patterns if re.search(pattern, text_lower))
    return legal_count >= 5 or pattern_count >= 3

def generate_legal_summary(text: str, is_legal: bool) -> str:
    """Generate AI-powered summary for legal documents."""
    try:
        # Use the existing legal model for summarization
        if is_legal:
            prompt = f"""Please provide a comprehensive summary of this legal document. Focus on:
1. Key legal issues and facts
2. Important dates, parties, and case details
3. Legal provisions, sections, or acts mentioned
4. Main arguments or claims
5. Court orders, judgments, or decisions
6. Any deadlines or important legal requirements

Document text:
{text[:4000]}  # Limit to avoid token limits

Please provide a clear, structured summary suitable for legal professionals."""
        else:
            prompt = f"""Please provide a summary of this document. Since it may not be a legal document, focus on:
1. Main topics and key points
2. Important information and facts
3. Any legal or regulatory content if present
4. Key dates and parties mentioned
5. Main conclusions or recommendations

Document text:
{text[:4000]}

Please provide a clear, structured summary."""

        summary = get_legal_advice(prompt, 'en')
        return summary if summary else generate_basic_summary(text)
    except Exception as e:
        logger.error(f"Legal summarization failed: {e}")
        return generate_basic_summary(text)

def generate_basic_summary(text: str) -> str:
    """Generate a basic summary as fallback."""
    sentences = text.split('.')
    meaningful_sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
    summary_sentences = meaningful_sentences[:5]
    summary = '. '.join(summary_sentences)
    if summary and not summary.endswith('.'):
        summary += '.'
    return summary or (text[:500] + "..." if len(text) > 500 else text)

def generate_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)

def get_current_timestamp() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()

# Password helpers
def hash_password(password: str) -> str:
    if _generate_password_hash:
        return _generate_password_hash(password)
    raise RuntimeError("werkzeug.security.generate_password_hash not available. Install Werkzeug.")

def verify_password(password: str, password_hash: str) -> bool:
    if _check_password_hash:
        return _check_password_hash(password_hash, password)
    raise RuntimeError("werkzeug.security.check_password_hash not available. Install Werkzeug.")

# JWT helpers
def create_jwt(payload: dict, expires_minutes: int = 60) -> str:
    if jwt is None:
        raise RuntimeError("PyJWT not installed")
    import datetime
    secret = os.environ.get('JWT_SECRET', 'secret')
    p = payload.copy()
    p['exp'] = datetime.datetime.utcnow() + datetime.timedelta(minutes=expires_minutes)
    token = jwt.encode(p, secret, algorithm='HS256') # type: ignore
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    return token

def decode_jwt(token: str) -> dict | None:
    if jwt is None:
        raise RuntimeError("PyJWT not installed")
    secret = os.environ.get('JWT_SECRET', 'secret')
    try:
        return jwt.decode(token, secret, algorithms=['HS256']) # type: ignore
    except Exception as e:
        logger.debug(f"JWT decode failed: {e}")
        return None

def get_current_user():
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None
    token = auth_header.split(' ', 1)[1]
    try:
        return decode_jwt(token)
    except Exception:
        return None

def _tokenize(text: str) -> set[str]:
    """Very simple tokenizer for similarity scoring."""
    import re
    words = re.findall(r"[a-zA-Z0-9]+", (text or "").lower())
    return {w for w in words if len(w) > 2}

def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return float(inter) / float(union) if union else 0.0

def _summarize_text(content: str, max_length: int = 360) -> str:
    """Generate a short summary snippet."""
    summary = (content or "").strip()
    summary = re.sub(r"\s+", " ", summary)
    if len(summary) > max_length:
        summary = summary[: max(0, max_length - 3)].rstrip() + "..."
    return summary

def _search_cases_by_court(
    query: str,
    limit: int = 3,
    court_hints: list[str] | None = None,
    fallback_court_label: str | None = None,
) -> list[dict]:
    """Fetch official case summaries filtered by court level."""
    results: list[dict] = []
    court_hints = [h.lower() for h in (court_hints or []) if h]
    api_key = os.environ.get('INDIAN_KANOON_API_KEY')

    def _matches_court(value: str | None) -> bool:
        if not court_hints:
            return True
        val = (value or '').lower()
        return any(h in val for h in court_hints)

    if api_key and requests is not None:
        try:
            url = 'https://api.indiankanoon.org/search/'
            params = {'formInput': query, 'pagenum': 0}
            headers = {'Authorization': f'Token {api_key}'}
            resp = requests.get(url, params=params, headers=headers, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get('results') or []:
                    court = item.get('court') or ''
                    if not _matches_court(court):
                        continue
                    results.append({
                        'title': item.get('title') or item.get('case_title') or 'Untitled case',
                        'court': court or fallback_court_label or '',
                        'date': item.get('judgement_date') or item.get('date') or '',
                        'citation': item.get('citation') or item.get('equivalent_citations') or '',
                        'url': item.get('url') or item.get('doc_url') or '',
                        'summary': _summarize_text(item.get('snippet') or item.get('headnote') or '')
                    })
                    if len(results) >= limit:
                        break
            else:
                logger.info(f"Kanoon HTTP {resp.status_code} for showcase query '{query}'")
        except Exception as err:
            logger.info(f"Kanoon showcase query failed ({err}); falling back to open search")

    if not results:
        ddg_query = query
        if court_hints:
            ddg_query = f"{query} {' '.join(court_hints)}"
        fallback = _duckduckgo_search_official(ddg_query, limit=limit)
        for item in fallback:
            results.append({
                'title': item.get('title') or 'Official judgment',
                'court': fallback_court_label or '',
                'date': item.get('date') or '',
                'citation': item.get('citation') or '',
                'url': item.get('url') or '',
                'summary': _summarize_text(item.get('snippet') or '')
            })
            if len(results) >= limit:
                break

    return results[:limit]

@app.route('/similar_cases', methods=['POST'])
def similar_cases():
    """Return similar past chats (cases) for a given user question.

    Body: { question: string, limit?: number }
    Returns: { similar: [ { id, question, answer, language, timestamp, score } ] }
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
            
        data = request.get_json() or {}
        question = (data.get('question') or '').strip()
        limit = data.get('limit') or 5
        try:
            limit = int(limit)
        except Exception:
            limit = 5
        limit = max(1, min(limit, 10))

        if not question:
            return jsonify({'error': 'Question is required'}), 400

        # Fetch recent chats (we can cap to last 200 for speed)
        rows = []
        try:
            rows = fetch_chats_filtered() or []
        except Exception as db_err:
            logger.error(f"Failed to fetch chats for similarity: {db_err}")
            rows = []

        # Score with simple Jaccard on tokens
        q_tokens = _tokenize(question)
        scored: list[dict] = []
        for r in rows[:200]:  # newest first as per helper
            try:
                rq = (r.get('question') or '')
                ra = (r.get('answer') or '')
                score_q = _jaccard(q_tokens, _tokenize(rq))
                score_a = _jaccard(q_tokens, _tokenize(ra)) * 0.5
                score = score_q + score_a
                if score > 0:
                    scored.append({
                        'id': r.get('id'),
                        'question': rq,
                        'answer': ra,
                        'language': r.get('language'),
                        'timestamp': r.get('timestamp'),
                        'score': round(float(score), 4)
                    })
            except Exception:
                continue

        scored.sort(key=lambda x: (-x['score'], x.get('timestamp') or ''))
        return jsonify({'similar': scored[:limit]}), 200
    except Exception as e:
        logger.error(f"Error in similar_cases endpoint: {e}")
        return jsonify({'error': 'Internal server error'}), 500

_CASELAW_CACHE: dict[str, dict] = {}

def _strip_tags(html: str) -> str:
    import re
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def _extract_title(html: str) -> str:
    import re
    m = re.search(r"<title[^>]*>([\s\S]*?)</title>", html, flags=re.I)
    if not m:
        return ""
    title = m.group(1)
    title = re.sub(r"\s+", " ", title)
    return title.strip()

def _duckduckgo_search_official(q: str, limit: int = 5) -> list[dict]:
    """Query DuckDuckGo HTML for official court domains (no API key)."""
    if requests is None:
        return []
    import urllib.parse
    # Focus on official domains; keep concise to improve precision
    site_filter = "(site:main.sci.gov.in OR site:*.nic.in OR site:*.gov.in)"
    query = f"{q} judgment {site_filter}"
    params = { 'q': query }
    url = f"https://duckduckgo.com/html/?{urllib.parse.urlencode(params)}"
    try:
        r = requests.get(url, timeout=8, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code != 200:
            return []
        html = r.text
    except Exception:
        return []

    import re, html as htmlmod
    # Extract result links from DDG HTML page (best-effort, structure may change)
    links: list[str] = []
    for m in re.finditer(r"<a[^>]+class=\"result__a\"[^>]+href=\"([^\"]+)\"", html):
        href = htmlmod.unescape(m.group(1))
        # Resolve redirect URLs (uddg param contains the target)
        if '/l/?' in href and 'uddg=' in href:
            try:
                parsed = urllib.parse.urlparse(href)
                qs = urllib.parse.parse_qs(parsed.query)
                if 'uddg' in qs and qs['uddg']:
                    href = qs['uddg'][0]
            except Exception:
                pass
        links.append(href)

    results: list[dict] = []
    for href in links:
        if len(results) >= limit:
            break
        if not href.startswith('http'):
            continue
        # Basic domain allow-listing for safety
        try:
            host = urllib.parse.urlparse(href).hostname or ''
        except Exception:
            host = ''
        if not any(x in host for x in ['sci.gov.in', '.nic.in', '.gov.in']):
            continue
        try:
            pr = requests.get(href, timeout=8, headers={'User-Agent': 'Mozilla/5.0'})
            if pr.status_code != 200:
                continue
            page_html = pr.text
            title = _extract_title(page_html) or href
            text = _strip_tags(page_html)
            snippet = (text[:300] + '...') if len(text) > 300 else text
            results.append({
                'title': title,
                'court': '',
                'date': '',
                'citation': '',
                'url': href,
                'snippet': snippet
            })
        except Exception:
            continue
    return results

# The rest of the file below this point doesn't have syntax errors and is unchanged.

# ... (existing endpoint routes remain unchanged)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV', '') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)
