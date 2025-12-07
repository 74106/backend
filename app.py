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
    list_lawyer_profiles,
    insert_lawyer_booking,
    create_subscription_purchase,
    get_subscription_purchase,
    get_user_subscriptions,
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
# Configure CORS to allow all origins (for development and production)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# Initialize database - wrap in try/except to prevent import failures
try:
    init_db()
except Exception as db_err:
    logger.warning(f"Database initialization warning (non-fatal): {db_err}")
    # Continue anyway - database will be initialized on first use or can be fixed manually

LAWYER_PORTAL_KEY = os.environ.get('LAWYER_PORTAL_KEY')
LAWYER_UPI_HANDLE = os.environ.get('LAWYER_UPI_ID', 'cyberverge@upi')

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
    
    # Consider it legal if we find enough indicators
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

        # Use the existing legal advice function for summarization
        summary = get_legal_advice(prompt, 'en')
        return summary if summary else generate_basic_summary(text)
        
    except Exception as e:
        logger.error(f"Legal summarization failed: {e}")
        return generate_basic_summary(text)

def generate_basic_summary(text: str) -> str:
    """Generate a basic summary as fallback."""
    # Split into sentences and take first few meaningful ones
    sentences = text.split('.')
    meaningful_sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
    
    # Take first 3-5 sentences as summary
    summary_sentences = meaningful_sentences[:5]
    summary = '. '.join(summary_sentences)
    
    if summary and not summary.endswith('.'):
        summary += '.'
    
    return summary or text[:500] + "..." if len(text) > 500 else text

def generate_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)

def get_current_timestamp() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _portal_request_authorized() -> bool:
    """Validate incoming requests from the lawyer portal (if key configured)."""
    if not LAWYER_PORTAL_KEY:
        return True
    candidate = (
        request.headers.get('X-Portal-Key')
        or request.args.get('api_key')
        or (request.get_json(silent=True) or {}).get('api_key')
    )
    if not candidate:
        return False
    try:
        return secrets.compare_digest(str(candidate), LAWYER_PORTAL_KEY)
    except Exception:
        return str(candidate) == LAWYER_PORTAL_KEY


def get_consultation_tiers() -> list[dict]:
    """Central definition of consultation tiers so frontend and APIs stay in sync."""
    return [
        {
            'id': 'basic',
            'name': '79 / Quick Help',
            'price': 79,
            'currency': 'INR',
            'duration': '1 hour',
            'hours': 1,
            'features': [
                '1 hour consultation (voice/video/chat)',
                'Immediate cyber-law triage',
                'Checklist of documents to gather'
            ]
        },
        {
            'id': 'standard',
            'name': '199 / Deep Dive',
            'price': 199,
            'currency': 'INR',
            'duration': '3 hours',
            'hours': 3,
            'features': [
                'Up to 3 hours split across the day',
                'Detailed analysis of FIR/complaints',
                'Follow-up call & drafts review'
            ]
        },
        {
            'id': 'extended',
            'name': '299 / Case Build',
            'price': 299,
            'currency': 'INR',
            'duration': '5 hours',
            'hours': 5,
            'features': [
                '5 lawyer hours for complex matters',
                'Drafting of notices / RTI / complaints',
                'Priority slot + escalation support'
            ]
        },
        {
            'id': 'premium',
            'name': '999 / Premium Lawyer',
            'price': 999,
            'currency': 'INR',
            'duration': 'Premium cyber-law partner',
            'hours': 8,
            'featured': True,
            'features': [
                'Top-tier cyber lawyer & dedicated VC room',
                'Full drafting, appeals & representation plan',
                '24/7 hotline + case manager'
            ]
        },
    ]


def _mask_phone(value: str | None) -> str | None:
    if not value:
        return None
    digits = ''.join(ch for ch in value if ch.isdigit())
    if len(digits) < 4:
        return None
    return f"+91-XXX-XXX-{digits[-4:]}" if len(digits) >= 4 else digits


def _short_text(text: str | None, limit: int = 220) -> str:
    if not text:
        return ''
    clean = re.sub(r'\s+', ' ', text).strip()
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 3)].rstrip() + '...'


def _public_lawyer_payload(profile: dict) -> dict:
    """Prepare lawyer profile for client consumption."""
    availability = profile.get('availability') or []
    communication = profile.get('communication') or profile.get('communication_modes') or []
    consultation_modes = profile.get('consultation_modes') or []
    return {
        'id': profile.get('id'),
        'name': profile.get('full_name'),
        'specialization': profile.get('specialization'),
        'experience_years': profile.get('experience_years'),
        'languages': profile.get('languages'),
        'location': profile.get('location') or 'Pan-India',
        'status': profile.get('status') or ('Available' if profile.get('is_available') else 'Busy'),
        'is_available': bool(profile.get('is_available')),
        'cases_handled': profile.get('cases_handled') or 0,
        'rating': round(float(profile.get('rating') or 4.8), 1),
        'masked_phone': _mask_phone(profile.get('phone')),
        'email': profile.get('email'),
        'bio_excerpt': _short_text(profile.get('bio')),
        'availability': availability,
        'communication_modes': communication,
        'consultation_modes': consultation_modes or communication,
        'hourly_rate': profile.get('hourly_rate'),
        'photo_url': profile.get('photo_url'),
        'video_link': profile.get('video_link'),
        'updated_at': profile.get('updated_at'),
    }

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
    # Remove very common short tokens
    return {w for w in words if len(w) > 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return float(inter) / float(union) if union else 0.0


def _summarize_text(content: str, max_length: int = 360) -> str:
    """Generate a short, reassuring summary snippet."""
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
        # Fallback: DuckDuckGo search constrained to official domains
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


@app.route('/cases/previous', methods=['GET'])
def previous_cases():
    """Return recent landmark decisions from Supreme, High, and District courts."""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401

        try:
            per_court = int(request.args.get('limit') or 3)
        except Exception:
            per_court = 3
        per_court = max(1, min(per_court, 5))

        showcase = {
            'supreme_court': _search_cases_by_court(
                "Supreme Court of India cyber law victim relief judgement",
                limit=per_court,
                court_hints=['supreme court'],
                fallback_court_label='Supreme Court of India',
            ),
            'high_courts': _search_cases_by_court(
                "High Court cyber fraud compensation order",
                limit=per_court,
                court_hints=['high court'],
                fallback_court_label='High Court',
            ),
            'district_courts': _search_cases_by_court(
                "District court cyber crime conviction India",
                limit=per_court,
                court_hints=['district court', 'sessions court'],
                fallback_court_label='District / Sessions Court',
            ),
        }

        return jsonify({
            'cases': showcase,
            'generated_at': get_current_timestamp(),
        }), 200
    except Exception as e:
        logger.error(f"Error in previous_cases endpoint: {e}")
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


@app.route('/case_law', methods=['GET'])
def case_law():
    """Search Indian court cases (Supreme/High Courts) via Indian Kanoon API.

    Query params:
      - q: user query (string)
      - limit: max number of cases to return (default 5, max 10)

    Requires environment variable INDIAN_KANOON_API_KEY if using Indian Kanoon.
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        q = (request.args.get('q') or '').strip()
        if not q:
            return jsonify({'error': 'Query (q) is required'}), 400

        try:
            limit = int(request.args.get('limit') or 5)
        except Exception:
            limit = 5
        limit = max(1, min(limit, 10))

        # Simple in-memory cache to reduce repeated external calls
        cache_key = f"{q}::{limit}"
        cached = _CASELAW_CACHE.get(cache_key)
        now = time.time()
        if cached and (now - cached.get('ts', 0) < 600):  # 10 min TTL
            return jsonify({'cases': cached.get('data', [])}), 200

        api_key = os.environ.get('INDIAN_KANOON_API_KEY')
        results: list[dict] = []

        if api_key and requests is not None:
            # Indian Kanoon search API (if configured)
            try:
                url = 'https://api.indiankanoon.org/search/'
                params = {'formInput': q, 'pagenum': 0}
                headers = {'Authorization': f'Token {api_key}'}
                resp = requests.get(url, params=params, headers=headers, timeout=8)
                if resp.status_code == 200:
                    data = resp.json()
                    for item in (data.get('results') or [])[:limit]:
                        try:
                            results.append({
                                'citation': item.get('citation') or item.get('equivalent_citations') or '',
                                'court': item.get('court') or '',
                                'date': item.get('judgement_date') or item.get('date') or '',
                                'title': item.get('title') or item.get('case_title') or '',
                                'url': item.get('url') or item.get('doc_url') or '',
                                'snippet': item.get('snippet') or item.get('headnote') or ''
                            })
                        except Exception:
                            continue
                else:
                    logger.info(f"Kanoon HTTP {resp.status_code}; falling back to free search")
            except Exception as prov_err:
                logger.info(f"Kanoon search failed ({prov_err}); falling back to free search")

        # Free fallback via DuckDuckGo official domains if nothing yet
        if not results:
            results = _duckduckgo_search_official(q, limit=limit)

        _CASELAW_CACHE[cache_key] = {'ts': now, 'data': results}
        # Bound cache size
        if len(_CASELAW_CACHE) > 64:
            try:
                # remove an arbitrary oldest
                oldest_key = sorted(_CASELAW_CACHE.items(), key=lambda kv: kv[1].get('ts', 0))[0][0]
                _CASELAW_CACHE.pop(oldest_key, None)
            except Exception:
                pass

        return jsonify({'cases': results}), 200
    except Exception as e:
        logger.error(f"Error in case_law endpoint: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/', methods=['GET'])
def root():
    html = (
        "<html><head><title>NyaySetu</title>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'/>"
        "<style>"
        "body{font-family:Segoe UI,Tahoma,Arial,sans-serif;padding:24px;line-height:1.6;background:#fff;color:#222;}"
        "code{background:#f5f5f5;padding:2px 6px;border-radius:4px;}"
        ".box{max-width:980px;margin:auto}"
        ".grid{display:grid;grid-template-columns:1fr;gap:16px}"
        "@media(min-width:900px){.grid{grid-template-columns:2fr 1fr}}"
        ".card{background:#fafafa;border:1px solid #eee;padding:16px;border-radius:12px}"
        ".button{display:inline-block;padding:12px 16px;border-radius:10px;border:1px solid #ddd;background:#0b5;"
        "color:#fff;text-decoration:none;margin-right:8px;font-weight:600}"
        ".button.secondary{background:#2276e3}"
        ".button.ghost{background:#fff;color:#222;border-color:#bbb}"
        ".endpoint{background:#fff;border:1px dashed #ddd;padding:10px;border-radius:8px;margin:6px 0}"
        ".sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);border:0}"
        ".big-nav{display:flex;gap:12px;flex-wrap:wrap;margin:12px 0}"
        ".big-tile{flex:1 1 180px;min-width:180px;border:2px solid #222;border-radius:16px;padding:16px;text-align:center;font-size:18px;"
        "background:#ffe969}"
        "</style></head><body><div class='box'>"
        "<h1>NyaySetu</h1>"
        "<p><b>Cyber Law Focus.</b> NyaySetu specializes in cyber law: online fraud, cybercrime complaints, data privacy, social media harassment, and electronic evidence. Ask questions, generate relevant forms, and connect with cyber-law lawyers.</p>"
        "<div class='big-nav'>"
        "<a class='big-tile' href='#lawyer' aria-label='Book a Lawyer (call or chat)'>🧑‍⚖ Book a Lawyer</a>"
        "<a class='big-tile' href='#forms' aria-label='Make a Form (simple)'>📝 Make a Form</a>"
        "<a class='big-tile' href='#chat' aria-label='Ask a Question'>💬 Ask a Question</a>"
        "</div>"
        "<div class='grid'>"
        "  <div>"
        "    <div id='lawyer' class='card'>"
        "      <h2>Book a Cyber-Lawyer</h2>"
        "      <p>See live availability of cyber-law specialists. Phone numbers will be added soon.</p>"
        "      <a class='button' id='btnCall' href='javascript:void(0)'>📞 Call a Lawyer</a>"
        "      <a class='button secondary' id='btnChat' href='javascript:void(0)'>💬 Chat to a Lawyer</a>"
        "      <p id='lawyerNote' style='margin-top:8px;color:#444'>Numbers coming soon. For now, chat opens a placeholder.</p>"
        "    </div>"
        "    <div id='forms' class='card'>"
        "      <h2>Cyber Law Form Generator</h2>"
        "      <p>Get guided templates for cyber-complaints, online fraud, and data protection.</p>"
        "      <div class='endpoint'><b>POST</b> <code>/generate_form</code> (Bearer token required)</div>"
        "    </div>"
        "    <div id='chat' class='card'>"
        "      <h2>Ask a Cyber Law Question</h2>"
        "      <div class='endpoint'><b>POST</b> <code>/chat</code> (Bearer token required)</div>"
        "    </div>"
        "    <div id='pdf' class='card'>"
        "      <h2>PDF Summariser (for lawyers)</h2>"
        "      <form id='pdfForm' enctype='multipart/form-data' method='post' action='/tools/summarize_pdf'>"
        "        <label for='pdfFile'><b>Select PDF:</b></label><br/>"
        "        <input name='file' id='pdfFile' type='file' accept='application/pdf' required />"
        "        <button class='button ghost' type='submit'>Summarise PDF</button>"
        "      </form>"
        "      <pre id='pdfOut' style='white-space:pre-wrap;background:#fff;border:1px solid #eee;padding:12px;border-radius:8px;margin-top:10px'></pre>"
        "    </div>"
        "  </div>"
        "  <div>"
        "    <div class='card'>"
        "      <h3>API Endpoints (Cyber Law)</h3>"
        "      <p>Status: healthy. See <code>/health</code>.</p>"
        "      <h4>Auth</h4>"
        "      <div class='endpoint'><b>POST</b> <code>/auth/register</code> { email, password }</div>"
        "      <div class='endpoint'><b>POST</b> <code>/auth/login</code> { email, password }</div>"
        "      <h4>Data</h4>"
        "      <div class='endpoint'><b>POST</b> <code>/chat</code></div>"
        "      <div class='endpoint'><b>POST</b> <code>/generate_form</code></div>"
        "      <div class='endpoint'><b>GET</b> <code>/data/chats</code> ?start&end&language&q</div>"
        "      <div class='endpoint'><b>GET</b> <code>/data/forms</code> ?start&end&form_type&q</div>"
        "      <div class='endpoint'><b>GET</b> <code>/lawyers/availability</code> (Bearer token required)</div>"
        "    </div>"
        "  </div>"
        "</div>"
        "<script>"
        "document.getElementById('btnCall').addEventListener('click', function(){alert('Phone numbers will be added by admin soon.');});"
        "document.getElementById('btnChat').addEventListener('click', function(){alert('Chat with a lawyer coming soon.');});"
        "async function loadAvailability(){try{const res=await fetch('/lawyers/availability',{headers:{'Authorization':localStorage.getItem('nyaysetu_token')?('Bearer '+localStorage.getItem('nyaysetu_token')):''}});if(!res.ok){return;}const data=await res.json();const el=document.getElementById('lawyerNote');if(el){const lines=(data.lawyers||[]).map(l=>${l.name} — ${l.specialty} — ${l.available?'Available':'Busy'});el.textContent = lines.join('\n') || el.textContent;}}catch(e){}}; loadAvailability();"
        "document.getElementById('pdfForm').addEventListener('submit', async function(e){e.preventDefault(); const form=new FormData(this); const res=await fetch('/tools/summarize_pdf',{method:'POST', body:form}); const txt=await res.text(); document.getElementById('pdfOut').textContent=txt;});"
        "</script>"
        "</div></body></html>"
    )
    return make_response(html, 200)

@app.route('/lawyers/availability', methods=['GET'])
def lawyers_availability():
    try:
        profiles = list_lawyer_profiles()
        public_profiles = [_public_lawyer_payload(p) for p in profiles]
        summary = {
            'total': len(public_profiles),
            'available': sum(1 for p in public_profiles if p['is_available']),
        }
        tiers = get_consultation_tiers()
        return jsonify({
            'lawyers': public_profiles,
            'timestamp': get_current_timestamp(),
            'summary': summary,
            'tiers': tiers,
            'payment': {
                'upi_handle': LAWYER_UPI_HANDLE,
                'requires_pre_payment': True,
                'note': 'Purchase a subscription tier first using /subscriptions/purchase, then use the subscription_id to book a lawyer.'
            }
        })
    except Exception as e:
        logger.error(f"Error in lawyers_availability: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/lawyers/profiles', methods=['GET'])
def lawyers_profiles():
    try:
        email_filter = (request.args.get('email') or '').strip().lower()
        only_available = request.args.get('available') == '1'
        try:
            limit = int(request.args.get('limit')) if request.args.get('limit') else None
        except Exception:
            limit = None
        profiles = list_lawyer_profiles(only_available=only_available, limit=limit)
        if email_filter:
            profiles = [p for p in profiles if (p.get('email') or '').lower() == email_filter]
        public = [_public_lawyer_payload(p) for p in profiles]
        return jsonify({
            'lawyers': public,
            'count': len(public),
            'tiers': get_consultation_tiers(),
            'payment': {'upi_handle': LAWYER_UPI_HANDLE, 'requires_pre_payment': True},
            'timestamp': get_current_timestamp()
        }), 200
    except Exception as e:
        logger.error(f"Error in lawyers_profiles: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/subscription-tiers', methods=['GET'])
def get_subscription_tiers():
    """Get available subscription tiers for lawyer consultation."""
    try:
        return jsonify({
            'tiers': get_consultation_tiers(),
            'timestamp': get_current_timestamp(),
            'payment': {
                'requires_pre_payment': True,
                'upi_handle': LAWYER_UPI_HANDLE,
                'note': 'Purchase a subscription tier first, then use the subscription_id to book a lawyer.'
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error in get_subscription_tiers: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/subscriptions/purchase', methods=['POST'])
def purchase_subscription():
    """Purchase a subscription tier. User pays first, then gets a subscription_id to book lawyers."""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        data = request.get_json() or {}
        tier_id = (data.get('tier_id') or '').strip().lower()
        payment_reference = (data.get('payment_reference') or '').strip()
        
        if not tier_id:
            return jsonify({'error': 'tier_id is required'}), 400
        
        if not payment_reference:
            return jsonify({'error': 'payment_reference is required. Please provide your UPI transaction reference.'}), 400
        
        # Validate tier
        tiers = {t['id']: t for t in get_consultation_tiers()}
        tier = tiers.get(tier_id)
        if not tier:
            return jsonify({'error': 'Invalid subscription tier'}), 400
        
        # Create subscription purchase
        subscription = create_subscription_purchase({
            'user_id': user['user_id'],
            'tier_id': tier_id,
            'tier_name': tier['name'],
            'price': tier['price'],
            'payment_reference': payment_reference,
            'status': 'active'
        })
        
        return jsonify({
            'message': 'Subscription purchased successfully',
            'subscription': subscription,
            'tier': tier,
            'next_steps': [
                'Use the subscription_id to book a lawyer consultation',
                'Your subscription is active and ready to use'
            ]
        }), 201
        
    except Exception as e:
        logger.error(f"Error in purchase_subscription: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/subscriptions/my', methods=['GET'])
def get_my_subscriptions():
    """Get current user's active subscriptions."""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        subscriptions = get_user_subscriptions(user['user_id'])
        return jsonify({
            'subscriptions': subscriptions,
            'count': len(subscriptions)
        }), 200
        
    except Exception as e:
        logger.error(f"Error in get_my_subscriptions: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/book-lawyer', methods=['POST'])
def book_lawyer():
    """Book a lawyer consultation with selected subscription tier."""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
            
        data = request.get_json() or {}
        response, status = _handle_lawyer_booking(user, data)
        return jsonify(response), status
        
    except Exception as e:
        logger.error(f"Error in book_lawyer: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/lawyers/book', methods=['POST'])
def lawyers_book():
    """Compatibility endpoint for frontend: accepts { tier, price, tier_name } and books consultation."""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401

        data = request.get_json() or {}
        response, status = _handle_lawyer_booking(user, data)
        return jsonify(response), status
    except Exception as e:
        logger.error(f"Error in lawyers_book: {e}")
        return jsonify({'error': 'Internal server error'}), 500




@app.route('/tools/summarize_pdf', methods=['POST'])
def summarize_pdf():
    """AI-powered PDF summariser focused on legal documents.
    Extracts text, detects legal content, and provides intelligent summarization.
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401

        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        file = request.files['file']
        if not file or file.filename.lower().endswith('.pdf') is False:
            return jsonify({'error': 'Please upload a PDF file'}), 400

        # Lazy import to avoid hard dependency during cold start
        try:
            import PyPDF2  # type: ignore
        except Exception:
            return jsonify({'error': 'PDF support not installed on server'}), 500

        reader = PyPDF2.PdfReader(file)
        extracted: list[str] = []
        max_pages = min(len(reader.pages), 20)  # Increased limit for legal documents
        for i in range(max_pages):
            try:
                page = reader.pages[i]
                text = page.extract_text() or ''
                if text:
                    extracted.append(text.strip())
            except Exception:
                continue

        full_text = "\n".join(extracted).strip()
        if not full_text:
            return jsonify({'error': 'Could not extract text from PDF'}), 400

        # Detect if this is a legal document
        is_legal_doc = detect_legal_document(full_text)
        
        # Generate AI-powered summary
        try:
            summary = generate_legal_summary(full_text, is_legal_doc)
        except Exception as e:
            logger.warning(f"AI summarization failed: {e}")
            # Fallback to basic summary
            summary = generate_basic_summary(full_text)

        return jsonify({
            'summary': summary,
            'is_legal_document': is_legal_doc,
            'original_length': len(full_text),
            'summary_length': len(summary),
            'pages_processed': len(extracted)
        }), 200
    except Exception as e:
        logger.error(f"Error in summarize_pdf: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/tools/convert_to_pdf', methods=['POST'])
def convert_to_pdf():
    """Convert summarized text to PDF format."""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401

        data = request.get_json() or {}
        text = data.get('text', '').strip()
        title = data.get('title', 'Legal Document Summary')
        
        if not text:
            return jsonify({'error': 'Text content is required'}), 400

        # Lazy import to avoid hard dependency during cold start
        try:
            from reportlab.lib.pagesizes import letter, A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.lib import colors
            from io import BytesIO
        except Exception:
            return jsonify({'error': 'PDF generation support not installed on server'}), 500

        # Create PDF in memory
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, 
                              topMargin=72, bottomMargin=18)
        
        # Get styles
        styles = getSampleStyleSheet()
        
        # Create custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
            alignment=1,  # Center alignment
            textColor=colors.darkblue
        )
        
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=12,
            leading=14
        )
        
        # Build PDF content
        story = []
        
        # Add title
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 20))
        
        # Add content
        paragraphs = text.split('\n\n')
        for para in paragraphs:
            if para.strip():
                story.append(Paragraph(para.strip(), body_style))
                story.append(Spacer(1, 6))
        
        # Build PDF
        doc.build(story)
        
        # Get PDF data
        buffer.seek(0)
        pdf_data = buffer.getvalue()
        buffer.close()
        
        # Return PDF as response
        response = make_response(pdf_data)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename="{title.replace(" ", "_")}_Summary.pdf"'
        
        return response
        
    except Exception as e:
        logger.error(f"Error in convert_to_pdf: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/generate_form_pdf', methods=['POST'])
def generate_form_pdf():
    """Generate a legal form, then return it as a downloadable PDF."""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401

        data = request.get_json() or {}
        form_type = data.get('form_type') or ''
        responses = data.get('responses') or {}
        if not form_type:
            return jsonify({'error': 'Form type is required'}), 400

        try:
            from utils.form_generator import generate_form as generate_form_text
            form_text = generate_form_text(form_type, responses)
        except Exception as gen_err:
            logger.error(f"Form generation failed (PDF): {gen_err}")
            return jsonify({'error': 'Failed to generate form'}), 500

        # Lazy import to avoid hard dependency during cold start
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            from io import BytesIO
        except Exception:
            return jsonify({'error': 'PDF generation support not installed on server'}), 500

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72,
                                 topMargin=72, bottomMargin=18)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'FormTitle', parent=styles['Heading1'], fontSize=16, spaceAfter=20,
            alignment=1, textColor=colors.darkblue
        )
        body_style = ParagraphStyle(
            'FormBody', parent=styles['Normal'], fontSize=11, spaceAfter=10, leading=14
        )

        story = []
        story.append(Paragraph(f"{form_type} Form", title_style))
        story.append(Spacer(1, 12))

        # Split body into paragraphs for basic layout
        for para in (form_text or '').split('\n\n'):
            p = para.strip()
            if not p:
                continue
            story.append(Paragraph(p.replace('\n', '<br/>'), body_style))
            story.append(Spacer(1, 6))

        doc.build(story)
        buffer.seek(0)
        pdf_data = buffer.getvalue()
        buffer.close()

        response = make_response(pdf_data)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename="{form_type.replace(' ', '_')}_NyaySetu.pdf"'
        return response
    except Exception as e:
        logger.error(f"Error in generate_form_pdf: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/speech_chat', methods=['POST'])
def speech_chat():
    """Accepts multipart/form-data with 'audio' file and optional 'language'.

    Transcribes audio, detects language if not supplied, runs chat flow,
    and returns localized answer.
    """
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401

        if 'audio' not in request.files:
            return jsonify({'error': 'No audio uploaded'}), 400
        file = request.files['audio']
        audio_bytes = file.read()
        if not audio_bytes:
            return jsonify({'error': 'Empty audio file'}), 400

        # Optional language hint
        lang_hint = request.form.get('language') or None

        try:
            from utils.speech import transcribe_audio_bytes  # lazy import
            transcript = transcribe_audio_bytes(audio_bytes, language=lang_hint)
        except Exception as e:
            logger.error(f"STT import/exec failed: {e}")
            transcript = None

        if not transcript:
            return jsonify({'error': 'Speech-to-text not available on this deployment'}, 501)

        # Reuse /chat logic: detect language, translate, answer, translate back
        detected_lang = lang_hint or detect_language(transcript)
        _, transcript_en = translate_pair(transcript, detected_lang)

        answer = None
        try:
            answer = get_legal_advice(transcript_en, 'en')
        except Exception as local_err:
            logger.warning(f"Local legal model failed (speech): {local_err}")

        if not answer:
            answer = "I apologize, but I'm currently unable to provide detailed legal advice. Please consult a qualified lawyer for your specific situation."

        try:
            sanitized_en = apply_policy(answer, transcript_en, 'en')
        except Exception as pol_err:
            logger.error(f"Policy enforcement failed (speech): {pol_err}")
            sanitized_en = 'I can only provide legal knowledge. Please ask a legal question.'

        final_text = translate(sanitized_en, 'en', detected_lang or 'en')

        timestamp = get_current_timestamp()
        try:
            insert_chat(question=transcript, answer=final_text, language=detected_lang, timestamp=timestamp)
        except Exception as db_err:
            logger.error(f"Failed to persist speech chat: {db_err}")

        return jsonify({
            'answer': final_text,
            'question': transcript,
            'language': detected_lang,
            'timestamp': timestamp,
            'source': 'local_model'
        })
    except Exception as e:
        logger.error(f"Error in speech_chat endpoint: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/health', methods=['GET', 'OPTIONS'])
def health_check():
    """Health check endpoint for monitoring and frontend connectivity checks."""
    response = jsonify({
        'status': 'healthy', 
        'service': 'NyaySetu Legal Aid API',
        'timestamp': time.time()
    })
    # Ensure CORS headers are set
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Methods', 'GET, OPTIONS')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    return response


def _handle_lawyer_booking(user: dict, payload: dict) -> tuple[dict, int]:
    subscription_id_raw = payload.get('subscription_id')
    if not subscription_id_raw:
        return {'error': 'subscription_id is required. Please purchase a subscription tier first using /subscriptions/purchase'}, 400
    
    try:
        subscription_id = int(subscription_id_raw)
    except Exception:
        return {'error': 'Invalid subscription_id format'}, 400
    
    # Verify subscription belongs to user and is active
    subscription = get_subscription_purchase(subscription_id)
    if not subscription:
        return {'error': 'Subscription not found'}, 404
    
    if subscription['user_id'] != user['user_id']:
        return {'error': 'Unauthorized: This subscription does not belong to you'}, 403
    
    if subscription['status'] != 'active':
        return {'error': f'Subscription is not active. Current status: {subscription["status"]}'}, 400
    
    tier_id = subscription['tier_id']
    tiers = {t['id']: t for t in get_consultation_tiers()}
    tier = tiers.get(tier_id)
    if not tier:
        return {'error': 'Invalid subscription tier'}, 400

    customer_name = (payload.get('customer_name') or '').strip()
    customer_phone = (payload.get('customer_phone') or '').strip()
    issue_description = (payload.get('issue_description') or '').strip()
    preferred_lawyer_raw = payload.get('preferred_lawyer_id') or payload.get('lawyer_id')
    preferred_lawyer_id = None
    if preferred_lawyer_raw:
        try:
            preferred_lawyer_id = int(preferred_lawyer_raw)
        except Exception:
            preferred_lawyer_id = None

    booking_id = f"BOOK_{int(time.time())}"
    record = insert_lawyer_booking({
        'booking_id': booking_id,
        'tier_id': tier_id,
        'tier_name': tier['name'],
        'price': tier['price'],
        'user_id': user['user_id'],
        'preferred_lawyer_id': preferred_lawyer_id,
        'customer_name': customer_name or user.get('email'),
        'customer_phone': customer_phone,
        'customer_email': user.get('email'),
        'issue_description': issue_description,
        'payment_reference': subscription['payment_reference'],
        'status': 'awaiting_match' if not preferred_lawyer_id else 'pending_confirmation',
        'notes': payload.get('notes'),
        'subscription_id': subscription_id,
    })

    shortlist = list_lawyer_profiles(only_available=True, limit=3)
    response = {
        'message': 'Lawyer consultation booked successfully',
        'booking': record,
        'tier': tier,
        'subscription_id': subscription_id,
        'preferred_lawyer_id': preferred_lawyer_id,
        'available_lawyers': [_public_lawyer_payload(p) for p in shortlist],
        'next_steps': [
            'Your booking has been confirmed using your active subscription.',
            'You will receive a call / WhatsApp message to confirm the preferred communication mode.',
            'The selected lawyer will join you via chat/voice/video as per the chosen plan.'
        ]
    }
    return response, 200

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json() or {}
        question = (data.get('question') or '').strip()
        # Auto-detect input language; translate to English for internal processing
        language = data.get('language') or detect_language(question)
        detected_lang, question_en = translate_pair(question, language)
        if not question:
            return jsonify({'error': 'Question is required'}), 400

        user = get_current_user()
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401

        # Fetch relevant court cases from Indian court databases (not local SQLite)
        previous_cases = []
        try:
            # Search for relevant cases from Indian courts using the case_law search
            api_key = os.environ.get('INDIAN_KANOON_API_KEY')
            if api_key and requests is not None:
                try:
                    # Build search query from user question
                    search_query = question_en[:200]  # Limit query length
                    url = 'https://api.indiankanoon.org/search/'
                    params = {'formInput': search_query, 'pagenum': 0}
                    headers = {'Authorization': f'Token {api_key}'}
                    resp = requests.get(url, params=params, headers=headers, timeout=8)
                    if resp.status_code == 200:
                        data = resp.json()
                        for item in (data.get('results') or [])[:5]:  # Get top 5 cases
                            try:
                                previous_cases.append({
                                    'title': item.get('title') or item.get('case_title') or 'Untitled case',
                                    'court': item.get('court') or '',
                                    'date': item.get('judgement_date') or item.get('date') or '',
                                    'citation': item.get('citation') or item.get('equivalent_citations') or '',
                                    'url': item.get('url') or item.get('doc_url') or '',
                                    'summary': _summarize_text(item.get('snippet') or item.get('headnote') or ''),
                                    'question': question_en,  # Keep original question for context
                                    'answer': ''  # Will be filled by AI
                        })
                except Exception:
                    continue
                except Exception as kanoon_err:
                    logger.info(f"Indian Kanoon search failed: {kanoon_err}")
                    # Fallback to DuckDuckGo search for official court domains
                    try:
                        results = _duckduckgo_search_official(question_en, limit=5)
                        for item in results:
                            previous_cases.append({
                                'title': item.get('title', ''),
                                'court': item.get('court', ''),
                                'date': item.get('date', ''),
                                'citation': item.get('citation', ''),
                                'url': item.get('url', ''),
                                'summary': item.get('snippet', ''),
                                'question': question_en,
                                'answer': ''
                            })
                    except Exception as ddg_err:
                        logger.warning(f"DuckDuckGo fallback also failed: {ddg_err}")
            else:
                # Fallback to DuckDuckGo if API key not available
                try:
                    results = _duckduckgo_search_official(question_en, limit=5)
                    for item in results:
                        previous_cases.append({
                            'title': item.get('title', ''),
                            'court': item.get('court', ''),
                            'date': item.get('date', ''),
                            'citation': item.get('citation', ''),
                            'url': item.get('url', ''),
                            'summary': item.get('snippet', ''),
                            'question': question_en,
                            'answer': ''
                        })
                except Exception as ddg_err:
                    logger.warning(f"DuckDuckGo search failed: {ddg_err}")
        except Exception as cases_err:
            logger.warning(f"Failed to fetch court cases: {cases_err}")

        answer = None
        # Try OpenAI legal model with previous cases context
        try:
            answer = get_legal_advice(question_en, 'en', previous_cases)
            logger.info("Got answer from OpenAI legal model")
        except Exception as local_err:
            logger.warning(f"OpenAI legal model failed: {local_err}")

        # If still no answer, fallback
        if not answer:
            answer = "I apologize, but I'm currently unable to provide detailed legal advice. Please consult a qualified lawyer for your specific situation."

        # Enforce policy/sanitization on English answer first
        try:
            sanitized_en = apply_policy(answer, question_en, 'en')
        except Exception as pol_err:
            logger.error(f"Policy enforcement failed: {pol_err}")
            sanitized_en = 'I can only provide legal knowledge. Please ask a legal question.'

        # Translate back to user's language if needed
        sanitized = translate(sanitized_en, 'en', detected_lang or 'en')

        timestamp = get_current_timestamp()
        try:
            insert_chat(question=question, answer=sanitized, language=detected_lang, timestamp=timestamp)
        except Exception as db_err:
            logger.error(f"Failed to persist chat: {db_err}")

        return jsonify({
            'answer': sanitized,
            'question': question,
            'language': detected_lang,
            'timestamp': timestamp,
            'source': 'openai_api' if answer and 'openai' in str(answer).lower() else 'local_model'
        })
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/auth/register', methods=['POST'])
def register():
    """Register a new user without email verification."""
    try:
        data = request.get_json() or {}
        email = (data.get('email') or '').strip().lower()
        password = data.get('password') or ''
        
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        if len(password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        
        # Check if user already exists
        existing_user = get_user_by_email(email)
        if existing_user:
            return jsonify({'error': 'User with this email already exists'}), 409
        
        # Hash password and create user (auto-verified)
        password_hash = hash_password(password)
        timestamp = get_current_timestamp()

        try:
            # Store as verified by setting verification_token to NULL and is_verified=1 directly
            # The create_user helper sets is_verified=0 by default, so we mimic creation then set verified
            user_id = create_user(email, password_hash, None, timestamp)
        except Exception as db_err:
            logger.error(f"Failed to create user: {db_err}")
            return jsonify({'error': 'Failed to create user account'}), 500

        # Manually mark verified in DB since create_user sets default 0
        try:
            import sqlite3
            from utils.db import get_db_connection
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET is_verified = 1, verification_token = NULL, verified_at = ? WHERE id = ?",
                (timestamp, user_id),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to auto-verify user: {e}")

        return jsonify({
            'message': 'Registration successful',
            'user_id': user_id
        }), 201
        
    except Exception as e:
        logger.error(f"Error in register endpoint: {e}")
        return jsonify({'error': 'Internal server error'}), 500

# Removed /auth/verify endpoint (email verification disabled)

@app.route('/auth/login', methods=['POST'])
def login():
    """Login user with email and password."""
    try:
        data = request.get_json() or {}
        email = (data.get('email') or '').strip().lower()
        password = data.get('password') or ''
        
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        user = get_user_by_email(email)
        if not user:
            return jsonify({'error': 'Invalid email or password'}), 401
        
        # Email verification disabled; skip is_verified check
        
        if not verify_password(password, user['password_hash']):
            return jsonify({'error': 'Invalid email or password'}), 401
        
        # Create JWT token
        token_payload = {
            'user_id': user['id'],
            'email': user['email'],
            'verified': user['is_verified']
        }
        token = create_jwt(token_payload, expires_minutes=60*24)  # 24 hours
        
        return jsonify({
            'message': 'Login successful',
            'token': token,
            'user': {
                'id': user['id'],
                'email': user['email'],
                'verified': user['is_verified']
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error in login endpoint: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/auth/logout', methods=['POST'])
def logout():
    """Logout user (client-side token invalidation)."""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Not authenticated'}), 401
        
        # In a stateless JWT system, logout is handled client-side
        # by removing the token. We can optionally maintain a blacklist
        # for additional security, but for simplicity, we'll just return success
        return jsonify({'message': 'Logout successful'}), 200
        
    except Exception as e:
        logger.error(f"Error in logout endpoint: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/auth/me', methods=['GET'])
def get_current_user_info():
    """Get current user information."""
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Not authenticated'}), 401
        
        return jsonify({
            'user': {
                'id': user['user_id'],
                'email': user['email'],
                'verified': user['verified']
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error in get_current_user_info endpoint: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/generate_form', methods=['POST'])
def generate_form():
    """Generate a legal form based on user input."""
    try:
        data = request.get_json() or {}
        form_type = data.get('form_type') or ''
        responses = data.get('responses') or {}
        
        if not form_type:
            return jsonify({'error': 'Form type is required'}), 400
        
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401
        
        try:
            from utils.form_generator import generate_form as generate_form_text
            form_text = generate_form_text(form_type, responses)
        except Exception as gen_err:
            logger.error(f"Form generation failed: {gen_err}")
            return jsonify({'error': 'Failed to generate form'}), 500
        
        timestamp = get_current_timestamp()
        try:
            form_id = insert_form(form_type, form_text, responses, timestamp)
        except Exception as db_err:
            logger.error(f"Failed to persist form: {db_err}")
            return jsonify({'error': 'Form generated but failed to save'}), 500
        
        return jsonify({
            'form_id': form_id,
            'form_type': form_type,
            'form_text': form_text,
            'responses': responses,
            'timestamp': timestamp
        }), 200
        
    except Exception as e:
        logger.error(f"Error in generate_form endpoint: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/data/chats', methods=['GET'])
def get_chats():
    """Get chat data with optional filters."""
    try:
        start = request.args.get('start')
        end = request.args.get('end')
        language = request.args.get('language')
        q = request.args.get('q')
        
        chats = fetch_chats_filtered(start=start, end=end, language=language, q=q)
        return jsonify({'chats': chats}), 200
        
    except Exception as e:
        logger.error(f"Error in get_chats endpoint: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/data/forms', methods=['GET'])
def get_forms():
    """Get form data with optional filters."""
    try:
        start = request.args.get('start')
        end = request.args.get('end')
        form_type = request.args.get('form_type')
        q = request.args.get('q')
        
        forms = fetch_forms_filtered(start=start, end=end, form_type=form_type, q=q)
        return jsonify({'forms': forms}), 200
        
    except Exception as e:
        logger.error(f"Error in get_forms endpoint: {e}")
        return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV', '') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)
