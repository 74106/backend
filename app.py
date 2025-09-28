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
)
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

def call_openai_api(prompt, language="en"):
    """
    Calls the OpenAI API with the given prompt.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not set in environment")
        return None

    if requests is None:
        logger.error("The 'requests' library is required for OpenAI API calls")
        return None

    try:
        # OpenAI API endpoint
        api_url = "https://api.openai.com/v1/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful legal AI assistant specializing in Indian law. Provide clear, practical legal advice based on Indian legal framework. Focus on relevant Indian laws, practical steps, legal remedies, and when to consult a lawyer. Always include disclaimers about consulting qualified legal professionals for specific cases."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            "max_tokens": 1000,
            "temperature": 0.7,
            "top_p": 0.9
        }
        
        resp = requests.post(api_url, headers=headers, json=payload, timeout=30)
        
        if resp.status_code == 200:
            data = resp.json()
            if 'choices' in data and len(data['choices']) > 0:
                answer = data['choices'][0]['message']['content']
                return answer.strip()
            else:
                return "I understand you're asking about a legal matter. Please consult a qualified legal professional for specific advice."
        else:
            logger.error(f"OpenAI API returned status {resp.status_code}: {resp.text}")
            return None
            
    except Exception as e:
        logger.error(f"OpenAI API call failed: {e}")
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
        ""
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

        # If local model failed, try OpenAI API
        if not answer:
            answer = call_openai_api(question, language)
            if answer:
                logger.info("Got answer from OpenAI API")

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
