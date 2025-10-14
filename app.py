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
        "<p><b>Bridging people to justice.</b> NyaySetu helps citizens ask legal questions, generate forms (FIR, RTI, complaints, appeals), and connect with lawyers for guidance.</p>"
        "<div class='big-nav'>"
        "<a class='big-tile' href='#lawyer' aria-label='Book a Lawyer (call or chat)'>🧑‍⚖️ Book a Lawyer</a>"
        "<a class='big-tile' href='#forms' aria-label='Make a Form (simple)'>📝 Make a Form</a>"
        "<a class='big-tile' href='#chat' aria-label='Ask a Question'>💬 Ask a Question</a>"
        "</div>"
        "<div class='grid'>"
        "  <div>"
        "    <div id='lawyer' class='card'>"
        "      <h2>Book a Lawyer</h2>"
        "      <p>Choose how you want to connect. We will add phone numbers shortly.</p>"
        "      <a class='button' id='btnCall' href='javascript:void(0)'>📞 Call a Lawyer</a>"
        "      <a class='button secondary' id='btnChat' href='javascript:void(0)'>💬 Chat to a Lawyer</a>"
        "      <p id='lawyerNote' style='margin-top:8px;color:#444'>Numbers coming soon. For now, chat opens a placeholder.</p>"
        "    </div>"
        "    <div id='forms' class='card'>"
        "      <h2>Form Generator</h2>"
        "      <p>Get simple, guided forms with examples for every field.</p>"
        "      <div class='endpoint'><b>POST</b> <code>/generate_form</code> (Bearer token required)</div>"
        "    </div>"
        "    <div id='chat' class='card'>"
        "      <h2>Ask a Legal Question</h2>"
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
        "      <h3>API Endpoints</h3>"
        "      <p>Status: healthy. See <code>/health</code>.</p>"
        "      <h4>Auth</h4>"
        "      <div class='endpoint'><b>POST</b> <code>/auth/register</code> { email, password }</div>"
        "      <div class='endpoint'><b>POST</b> <code>/auth/login</code> { email, password }</div>"
        "      <h4>Data</h4>"
        "      <div class='endpoint'><b>POST</b> <code>/chat</code></div>"
        "      <div class='endpoint'><b>POST</b> <code>/generate_form</code></div>"
        "      <div class='endpoint'><b>GET</b> <code>/data/chats</code> ?start&end&language&q</div>"
        "      <div class='endpoint'><b>GET</b> <code>/data/forms</code> ?start&end&form_type&q</div>"
        "    </div>"
        "  </div>"
        "</div>"
        "<script>"
        "document.getElementById('btnCall').addEventListener('click', function(){alert('Phone numbers will be added by admin soon.');});"
        "document.getElementById('btnChat').addEventListener('click', function(){alert('Chat with a lawyer coming soon.');});"
        "document.getElementById('pdfForm').addEventListener('submit', async function(e){e.preventDefault(); const form=new FormData(this); const res=await fetch('/tools/summarize_pdf',{method:'POST', body:form}); const txt=await res.text(); document.getElementById('pdfOut').textContent=txt;});"
        "</script>"
        "</div></body></html>"
    )
    return make_response(html, 200)

@app.route('/tools/summarize_pdf', methods=['POST'])
def summarize_pdf():
    """Very simple PDF summariser: extracts text and returns the first N lines.
    Intended as a placeholder for lawyers; replace with an LLM-based summary later.
    """
    try:
        if 'file' not in request.files:
            return make_response('No file uploaded', 400)
        file = request.files['file']
        if not file or file.filename.lower().endswith('.pdf') is False:
            return make_response('Please upload a PDF file', 400)

        # Lazy import to avoid hard dependency during cold start
        try:
            import PyPDF2  # type: ignore
        except Exception:
            return make_response('PDF support not installed on server', 500)

        reader = PyPDF2.PdfReader(file)
        extracted: list[str] = []
        max_pages = min(len(reader.pages), 10)  # safety cap
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
            return make_response('Could not extract text from PDF', 200)

        # Naive summary: first 1200 characters
        preview = full_text[:1200]
        return make_response(preview, 200)
    except Exception as e:
        logger.error(f"Error in summarize_pdf: {e}")
        return make_response('Internal server error', 500)

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

        # If local model failed, nothing else to try (Gemini handled in model)

        # If still no answer, fallback
        if not answer:
            answer = "I apologize, but I'm currently unable to provide detailed legal advice. Please consult a qualified lawyer for your specific situation."

        # Enforce policy/sanitization
        try:
            sanitized = apply_policy(answer, question, language)
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
            'source': 'cohere_api' if answer and 'cohere' in str(answer).lower() else 'local_model'
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
