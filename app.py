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
        "<p><b>Cyber Law Focus.</b> NyaySetu specializes in cyber law: online fraud, cybercrime complaints, data privacy, social media harassment, and electronic evidence. Ask questions, generate relevant forms, and connect with cyber-law lawyers.</p>"
        "<div class='big-nav'>"
        "<a class='big-tile' href='#lawyer' aria-label='Book a Lawyer (call or chat)'>🧑‍⚖️ Book a Lawyer</a>"
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
        "async function loadAvailability(){try{const res=await fetch('/lawyers/availability',{headers:{'Authorization':localStorage.getItem('nyaysetu_token')?('Bearer '+localStorage.getItem('nyaysetu_token')):''}});if(!res.ok){return;}const data=await res.json();const el=document.getElementById('lawyerNote');if(el){const lines=(data.lawyers||[]).map(l=>`${l.name} — ${l.specialty} — ${l.available?'Available':'Busy'}`);el.textContent = lines.join('\n') || el.textContent;}}catch(e){}}; loadAvailability();"
        "document.getElementById('pdfForm').addEventListener('submit', async function(e){e.preventDefault(); const form=new FormData(this); const res=await fetch('/tools/summarize_pdf',{method:'POST', body:form}); const txt=await res.text(); document.getElementById('pdfOut').textContent=txt;});"
        "</script>"
        "</div></body></html>"
    )
    return make_response(html, 200)

@app.route('/lawyers/availability', methods=['GET'])
def lawyers_availability():
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Unauthorized'}), 401

        # Placeholder static dataset; replace with DB records in future
        lawyers = [
            { 'id': 1, 'name': 'Adv. Meera Sharma', 'specialty': 'Cyber Crime, IT Act', 'available': True },
            { 'id': 2, 'name': 'Adv. Raj Patel', 'specialty': 'Data Privacy, Online Fraud', 'available': False },
            { 'id': 3, 'name': 'Adv. Ananya Rao', 'specialty': 'Social Media Harassment', 'available': True }
        ]

        return jsonify({ 'lawyers': lawyers, 'timestamp': get_current_timestamp() })
    except Exception as e:
        logger.error(f"Error in lawyers_availability: {e}")
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

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'service': 'NyaySetu Legal Aid API'})

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

        answer = None
        # Try local legal model first
        try:
            answer = get_legal_advice(question_en, 'en')
            logger.info("Got answer from local legal model")
        except Exception as local_err:
            logger.warning(f"Local legal model failed: {local_err}")

        # If local model failed, nothing else to try (Gemini handled in model)

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
