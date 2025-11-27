import re
from typing import Dict, List, Optional
import os
import requests
import json

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Import translation library
try:
    from deep_translator import GoogleTranslator
    _translator_available = True
except ImportError:
    _translator_available = False

class LegalAdviceGenerator:
    """Advanced legal advice generator with multi-language support using deep-translator"""
    
    def __init__(self):
        # Language mapping for translation
        self.language_mapping = {
            'en': 'en',
            'hi': 'hi',  # Hindi
            'or': 'or',  # Odia
            'bn': 'bn',  # Bengali
            'ta': 'ta',  # Tamil
            'te': 'te',  # Telugu
            'mr': 'mr',  # Marathi
            'gu': 'gu',  # Gujarati
            'kn': 'kn',  # Kannada
            'ml': 'ml',  # Malayalam
            'pa': 'pa',  # Punjabi
            'ka': 'ka',  # Kannada (alternate code)
        }
        
        # Base English legal prompt - will be translated to other languages
        self.base_legal_prompt = """You are a legal AI assistant specializing in Indian law. Provide clear, practical legal advice based on Indian legal framework. Focus on:
1. Relevant Indian laws and regulations (BNS, BNSS, BSA, Constitution, etc.)
2. Practical steps the person can take
3. Available legal remedies and procedures
4. Important deadlines and time limits
5. When to consult a lawyer
6. Available legal aid resources

IMPORTANT: Always reference the current Indian legal framework:
- Bharatiya Nyaya Sanhita (BNS), 2023 (replaces IPC)
- Bharatiya Nagarik Suraksha Sanhita (BNSS), 2023 (replaces CrPC)
- Bharatiya Sakshya Adhiniyam (BSA), 2023 (replaces Evidence Act)

Always cite specific laws, sections, or articles when providing legal information. If referencing criminal law, use BNS instead of IPC.

Keep responses helpful, accurate, and actionable. If you're unsure about specific legal details, recommend consulting a qualified lawyer.

Question: {question}

Provide legal advice:"""
        
        # Base fallback response - will be translated to other languages
        self.base_fallback_response = "I apologize, but I'm currently unable to provide detailed legal advice. Please consult a qualified lawyer for your specific situation."
    
    def translate_text(self, text: str, target_language: str) -> str:
        """Translate text to target language using deep-translator"""
        if not _translator_available:
            return text
        
        if target_language == 'en':
            return text
        
        try:
            translator = GoogleTranslator(source='en', target=target_language)
            translated = translator.translate(text)
            return translated
        except Exception as e:
            # If translation fails, return original text
            print(f"Translation error: {str(e)}")
            return text
    
    def get_legal_prompt(self, question: str, language: str = 'en') -> str:
        """Get appropriate legal prompt for the language using translation"""
        if language == 'en':
            return self.base_legal_prompt.format(question=question)
        else:
            # Translate the base prompt to the target language
            translated_prompt = self.translate_text(self.base_legal_prompt, language)
            return translated_prompt.format(question=question)
    
    def get_fallback_response(self, language: str = 'en') -> str:
        """Get fallback response when all AI models are not available"""
        if language == 'en':
            return self.base_fallback_response
        else:
            return self.translate_text(self.base_fallback_response, language)

# Global instance
legal_advisor = LegalAdviceGenerator()


def get_gemini_answer(question: str, language: str = 'en') -> str:
    """Get answer from Google Gemini via REST API"""
    try:
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            return "Gemini API key not set. Set GEMINI_API_KEY environment variable."

        # Endpoint and model selection (use v1beta and Gemini 3.x models)
        primary_model = os.environ.get('GEMINI_MODEL', 'gemini-3.0-flash')
        model_candidates = [
            primary_model,
            'gemini-3.0-flash',
            'gemini-3.0-pro',
            'gemini-2.5-flash-exp',
            'gemini-2.0-flash-exp',
        ]

        legal_prompt = legal_advisor.get_legal_prompt(question, language)

        headers = {
            "Content-Type": "application/json",
        }

        # Use translated instruction based on the language
        base_instruction = (
            "You are a helpful legal AI for Indian law. Answer clearly and practically. "
            "Always reference current Indian legal framework (BNS, BNSS, BSA instead of IPC, CrPC, Evidence Act). "
            "Be cautious about providing definitive legal interpretations; when in doubt, recommend consulting a qualified lawyer."
        )
        instruction = legal_advisor.translate_text(base_instruction, language)

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": instruction},
                        {"text": legal_prompt}
                    ]
                }
            ]
        }

        last_error_text = None
        for model in model_candidates:
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            try:
                response = requests.post(api_url, headers=headers, json=payload, timeout=30)
            except Exception as e:
                last_error_text = str(e)
                continue

            if response.status_code == 200:
                data = response.json()
                try:
                    candidates = data.get("candidates") or []
                    if not candidates:
                        continue
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if not parts:
                        continue
                    text = (parts[0].get("text") or "").strip()
                    if text:
                        return text
                    # if text empty, try next model
                    continue
                except Exception:
                    continue
            else:
                last_error_text = f"{response.status_code}: {response.text}"
                # try next model
                continue

        # If all models failed
        try:
            from app import logger
            logger.error(f"Gemini API failed for all candidate models. Last error: {last_error_text}")
        except Exception:
            pass
        return legal_advisor.get_fallback_response(language)

    except Exception as e:
        try:
            from app import logger
            logger.error(f"Gemini API error: {str(e)}")
        except Exception:
            pass
        return legal_advisor.get_fallback_response(language)


def get_fallback_legal_response(question: str) -> str:
    """Provide a fallback legal response when API is not available"""
    question_lower = question.lower()
    
    # Simple keyword-based responses
    if any(word in question_lower for word in ['tenant', 'rent', 'eviction', 'landlord']):
        return """As a tenant, you have several important rights under Indian law:

1. Right to peaceful enjoyment: Your landlord cannot disturb your peaceful possession of the property.
2. Right to notice: For eviction, landlords must provide proper notice as per state laws.
3. Right to essential services: Landlords must maintain essential services like water, electricity.
4. Right to privacy: Landlords cannot enter your premises without notice.
5. Protection against arbitrary rent increases: Rent increases must follow legal procedures.

Please note: Laws vary by state. For specific situations, consult a local lawyer."""

    elif any(word in question_lower for word in ['fir', 'police', 'complaint', 'crime']):
        return """For filing an FIR (First Information Report) in India:

1. Go to the nearest police station where the incident occurred.
2. Provide detailed information about the incident, including date, time, location, description, names of people involved, and any evidence or witnesses.
3. Get acknowledgment: The police must give you a copy of the FIR.
4. Follow up: Keep track of the investigation progress.
5. Legal remedies: If police refuse to file FIR, you can approach the Superintendent of Police or file a complaint with the Magistrate.

Legal Framework: This process is governed by the Bharatiya Nagarik Suraksha Sanhita (BNSS), 2023, which replaced the Code of Criminal Procedure (CrPC).

Remember: FIR is your right for cognizable offenses. Seek legal help if needed."""

    elif any(word in question_lower for word in ['divorce', 'marriage', 'custody', 'alimony']):
        return """For family law matters in India:

Divorce Process:
1. Grounds for divorce: Adultery, cruelty, desertion, conversion, mental disorder, etc.
2. Mutual consent: Both parties can file for divorce by mutual consent.
3. Court procedures: File petition in family court with proper documentation.

Child Custody:
1. Best interest of child: Courts prioritize child's welfare.
2. Joint custody: Both parents can share custody.
3. Visitation rights: Non-custodial parent has visitation rights.

Important: Family law is complex and varies by personal laws (Hindu, Muslim, Christian, etc.). Consult a family lawyer for specific advice."""

    elif any(word in question_lower for word in ['contract', 'agreement', 'breach', 'damages']):
        return """For contract-related issues in India:

Essential Elements of a Valid Contract:
1. Offer and acceptance
2. Consideration (something of value)
3. Competent parties
4. Free consent
5. Lawful object

Breach of Contract Remedies:
1. Specific performance: Court can order performance of contract
2. Damages: Monetary compensation for losses
3. Injunction: Court order to stop certain actions
4. Rescission: Cancellation of contract

Important: Contract law is governed by the Indian Contract Act, 1872. For complex matters, consult a contract lawyer."""

    else:
        return """I understand you're seeking legal advice. Here's some general guidance:

General Legal Rights in India:
1. Right to legal aid: Free legal aid is available for those who cannot afford lawyers
2. Right to fair trial: Everyone has the right to a fair and speedy trial
3. Right to legal representation: You have the right to be represented by a lawyer
4. Right to information: You can access public information under RTI Act

Important Disclaimer:
- This is general information only
- Laws vary by state and personal circumstances
- Always consult a qualified lawyer for specific legal advice
- For urgent matters, contact legal aid services immediately

Emergency Contacts:
- Legal Aid: 1800-345-6789
- Women Helpline: 181
- Child Helpline: 1098"""

def get_legal_advice(question: str, language: str = 'en') -> str:
    """Main function to get legal advice using Gemini first, then fallback"""
    if not question or not question.strip():
        base_message = "Could you please provide a question that addresses a specific legal issue."
        return legal_advisor.translate_text(base_message, language)
    
    try:
        # Try Gemini first with language-specific prompt
        gemini_answer = get_gemini_answer(question.strip(), language)
        if gemini_answer and not gemini_answer.startswith("Gemini API key not set") and not gemini_answer.startswith("Error"):
            # If Gemini returns answer in English but we need another language, translate it
            if language != 'en' and gemini_answer == legal_advisor.get_fallback_response('en'):
                return legal_advisor.translate_text(gemini_answer, language)
            return gemini_answer

        # Fallback to intelligent response
        return get_intelligent_legal_response(question, language)
        
    except Exception:
        # Fallback to intelligent response
        return get_intelligent_legal_response(question, language)

def get_intelligent_legal_response(question: str, language: str = 'en') -> str:
    """Provide intelligent legal responses based on question analysis"""
    question_lower = question.lower()
    
    # Multilingual keyword matching for tenant/rent issues
    tenant_keywords = [
        'tenant', 'rent', 'eviction', 'landlord', 'lease', 'rental',
        'किरायेदार', 'किराया', 'बेदखली', 'मकान मालिक',
        'ভাড়াটিয়া', 'ভাড়া', 'উচ্ছেদ', 'বাড়িওয়ালা',
        'வாடகை', 'வாடகைதாரர்',
        'అద్దె', 'అద్దెదారుడు',
        'भाडेकरू', 'भाडे',
    ]
    
    fir_keywords = [
        'fir', 'police', 'complaint', 'crime', 'criminal', 'arrest', 'bail', 'court',
        'एफआईआर', 'पुलिस', 'शिकायत', 'अपराध', 'गिरफ्तार', 'जमानत',
        'এফআইআর', 'পুলিশ', 'অভিযোগ',
        'எஃப்ஐஆர்', 'காவல்துறை',
    ]
    
    family_keywords = [
        'divorce', 'marriage', 'custody', 'alimony', 'maintenance', 'family', 'spouse', 'child',
        'तलाक', 'विवाह', 'संरक्षण', 'गुजारा भत्ता',
        'তালাক', 'বিবাহ', 'অভিভাবকত্ব',
        'விவாகரத்து', 'திருமணம்',
    ]
    
    contract_keywords = [
        'contract', 'agreement', 'breach', 'damages', 'employment', 'job', 'work', 'salary',
        'अनुबंध', 'समझौता', 'उल्लंघन',
        'চুক্তি', 'লঙ্ঘন',
        'ஒப்பந்தம்', 'மீறல்',
    ]
    
    consumer_keywords = [
        'consumer', 'refund', 'defective', 'warranty', 'complaint', 'product', 'service', 'purchase',
        'उपभोक्ता', 'वापसी', 'दोषपूर्ण', 'वारंटी',
        'ভোক্তা', 'ফেরত', 'ত্রুটিপূর্ণ',
        'நுகர்வோர்', 'திரும்ப',
    ]

    # Check categories in order of specificity
    if any(word in question_lower for word in tenant_keywords):
        response = """Tenant Rights in India - Comprehensive Guide

Key Rights You Have:
1. Right to Peaceful Enjoyment: Your landlord cannot disturb your peaceful possession without proper notice.
2. Right to Essential Services: Landlords must maintain water, electricity, and other essential services.
3. Right to Privacy: Landlords should not enter your premises without notice.
4. Protection from Arbitrary Eviction: Eviction requires proper legal notice and valid grounds.
5. Right to Fair Rent: Rent increases must follow legal procedures.

Important Laws:
- Rent Control Acts (vary by state)
- Transfer of Property Act, 1882
- Model Tenancy Act, 2021 (if adopted by your state)

What to Do if Your Rights are Violated:
1. Document everything (photos, videos, written communications).
2. Send a legal notice to your landlord.
3. File a complaint with the Rent Control Court or appropriate forum.
4. Contact local legal aid services."""

    elif any(word in question_lower for word in fir_keywords):
        response = """Filing FIR and Criminal Law in India

How to File an FIR:
1. Go to the nearest police station where the incident occurred.
2. Provide complete details: date, time, location, description of incident, names of people involved, and any evidence or witnesses.
3. Get acknowledgment: Police must give you a copy of the FIR.
4. Follow up: Keep track of investigation progress.

Your Rights During FIR Process:
- Right to get a copy of FIR free of cost
- Right to legal representation
- Right to approach higher authorities or a magistrate if police refuse to file FIR

Important Laws:
- Bharatiya Nagarik Suraksha Sanhita (BNSS), 2023
- Bharatiya Nyaya Sanhita (BNS), 2023"""

    elif any(word in question_lower for word in family_keywords):
        response = """Family Law in India - Marriage, Divorce & Custody

Divorce Process:
1. Grounds for divorce include adultery, cruelty, desertion, conversion, mental disorder, and mutual consent.
2. File petition in Family Court or appropriate civil court.
3. Mediation and counseling may be required.

Child Custody:
- Best interest of the child is the primary consideration.
- Courts may grant joint or sole custody depending on circumstances.
- Visitation rights can be ordered for the non-custodial parent.

Maintenance/Alimony:
- Maintenance depends on income, needs and other factors.
- Interim maintenance can be sought during proceedings."""

    elif any(word in question_lower for word in contract_keywords):
        response = """Contract Law in India

Essential Elements of a Valid Contract:
1. Offer and Acceptance
2. Consideration
3. Competent Parties
4. Free Consent
5. Lawful Object

Remedies for Breach:
- Specific performance, damages, injunction, rescission.

Important Laws:
- Indian Contract Act, 1872
- Sale of Goods Act, 1930"""

    elif any(word in question_lower for word in consumer_keywords):
        response = """Consumer Rights in India

Your Rights:
1. Right to Safety
2. Right to Information
3. Right to Choose
4. Right to be Heard
5. Right to Redressal

How to Seek Redressal:
- File complaint at District, State, or National Consumer Forum depending on value of claim.
- Keep all receipts and documents and file within statutory limitation (usually 2 years)."""

    else:
        response = """General Legal Guidance for India

Fundamental Rights and Resources:
- Right to equality, freedom, constitutional remedies.
- Free legal aid through Legal Services Authorities.
- District, State and National courts and consumer/family forums.

Disclaimer:
This is general information only. Laws vary by state and circumstances. Consult a qualified lawyer for specific legal advice."""

    # Translate if needed
    if language != 'en':
        try:
            translated_response = legal_advisor.translate_text(response, language)
            return translated_response
        except Exception:
            return response
    
    return response
