from flask import Flask, request, jsonify, make_response, redirect
from flask_cors import CORS
from models.legal_chat_model import get_legal_advice
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
    get_user_by_verification_token,
    set_user_verified,
    set_verification_token,
)
from utils.auth import send_verification_email
import logging
import os
import time
import json
import secrets
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

def call_gemini_api(prompt, language="en"):
    """
    Calls the Google Gemini API with the given prompt.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not set in environment")
        return None

    if requests is None:
        logger.error("The 'requests' library is required for Gemini API calls")
        return None

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    try:
        resp = requests.post(f"{url}?key={api_key}", headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        # Parse Gemini format
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            return str(data)
    except Exception as e:
        logger.error(f"Gemini API call failed: {e}")
        return None

@app.route('/', methods=['GET'])
def root():
    html = (
        "<html><head><title>NyaySetu API</title>"
        "<style>body{font-family:Segoe UI,Tahoma,Arial,sans-serif;padding:24px;line-height:1.6;}"
        "code{background:#f5f5f5;padding:2px 6px;border-radius:4px;}"
        ".box{max-width:840px;margin:auto} .endpoint{background:#fafafa;border:1px solid #eee;padding:12px;border-radius:8px;margin:8px 0}"
        "</style></head><body><div class='box'>"
        "<h2>NyaySetu Legal Aid API</h2>"
        "<p>Status: healthy. See <code>/health</code>.</p>"
        "<h3>Auth</h3>"
        "<div class='endpoint'><b>POST</b> <code>/auth/register</code> { email, password }</div>"
        "<div class='endpoint'><b>GET</b> <code>/auth/verify?token=...</code></div>"
        "<div class='endpoint'><b>POST</b> <code>/auth/login</code> { email, password }</div>"
        "<h3>Data</h3>"
        "<div class='endpoint'><b>POST</b> <code>/chat</code> (Bearer token required)</div>"
        "<div class='endpoint'><b>POST</b> <code>/generate_form</code> (Bearer token required)</div>"
        "<div class='endpoint'><b>GET</b> <code>/data/chats</code> ?start&end&language&q</div>"
        "<div class='endpoint'><b>GET</b> <code>/data/forms</code> ?start&end&form_type&q</div>"
        "</div></body></html>"
    )
    return make_response(html, 200)

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'service': 'NyaySetu Legal Aid API'})

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json() or {}
        question = (data.get('question') or '').strip()
        language = data.get('language') or 'en'
        if not question:
            return jsonify({'error': 'Question is required'}), 400

        user = get_current_user()
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401

        answer = None
        # Try local legal model first
        try:
            answer = get_legal_advice(question, language)
            logger.info("Got answer from local legal model")
        except Exception as local_err:
            logger.warning(f"Local legal model failed: {local_err}")

        # If local model failed, try Gemini
        if not answer:
            answer = call_gemini_api(question, language)
            if answer:
                logger.info("Got answer from Gemini API")

        # If still no answer, fallback
        if not answer:
            answer = "I apologize, but I'm currently unable to provide detailed legal advice. Please consult a qualified lawyer for your specific situation."

        # Enforce policy/sanitization
        try:
            sanitized = apply_policy(answer, question)
        except Exception as pol_err:
            logger.error(f"Policy enforcement failed: {pol_err}")
            sanitized = 'I can only provide legal knowledge. Please ask a legal question.'

        timestamp = get_current_timestamp()
        try:
            insert_chat(question=question, answer=sanitized, language=language, timestamp=timestamp)
        except Exception as db_err:
            logger.error(f"Failed to persist chat: {db_err}")

        return jsonify({
            'answer': sanitized,
            'question': question,
            'language': language,
            'timestamp': timestamp,
            'source': 'gemini_api' if 'gemini' in str(answer).lower() else 'local_model'
        })
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return jsonify({'error': 'Internal server error'}), 500

# ... rest of your endpoints remain unchanged ...
# (For brevity, other endpoints are unchanged from your previous app.py)

# [All other route handlers remain the same as in your current file]

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV', '') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)
