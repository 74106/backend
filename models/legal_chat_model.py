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
            'kn': 'kn',  # Konkani
            'ml': 'ml',  # Malayalam
            'pa': 'pa',  # Punjabi
            'ka': 'ka',  # Kannada 
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
        self.base_fallback_response = 'I apologize, but I\'m currently unable to provide detailed legal advice. Please consult a qualified lawyer for your specific situation.'
    
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

# Keyword inventories reused by the offline heuristic responder. They intentionally
# cover common Indian languages so that simple substring checks still match.
TENANT_KEYWORDS = [
    'tenant', 'rent', 'eviction', 'landlord', 'lease', 'rental',
    'किरायेदार', 'किराया', 'बेदखली', 'मकान मालिक', 'लीज', 'किराये',
    'ভাড়াটিয়া', 'ভাড়া', 'উচ্ছেদ', 'বাড়িওয়ালা', 'লিজ',
    'வாடகைதாரர்', 'வாடகை', 'வெளியேற்றம்', 'வீட்டு உரிமையாளர்',
    'అద్దెదారుడు', 'అద్దె', 'బహిష్కరణ', 'ఇల్లు యజమాని',
    'भाडेकरू', 'भाडे', 'घर मालक',
    'ભાડેકરૂ', 'ભાડું', 'ઘર માલિક',
    'വാടകക്കാരൻ', 'വാടക', 'വീട് ഉടമ',
    'ਕਿਰਾਏਦਾਰ', 'ਘਰ ਮਾਲਕ',
    'ಬಾಡಿಗೆದಾರ', 'ಮನೆ ಮಾಲೀಕ',
    'ଭଡ଼ାଦାର', 'ଘର ମାଲିକ'
]

FIR_KEYWORDS = [
    'fir', 'police', 'complaint', 'crime', 'criminal', 'arrest', 'bail', 'court',
    'एफआईआर', 'पुलिस', 'शिकायत', 'अपराध', 'गिरफ्तार', 'जमानत', 'अदालत',
    'এফআইআর', 'পুলিশ', 'অভিযোগ', 'অপরাধ', 'গ্রেফতার', 'জামিন', 'আদালত',
    'எஃப்ஐஆர்', 'காவல்துறை', 'புகார்', 'குற்றம்', 'கைது', 'ஜாமீன்', 'நீதிமன்றம்',
    'ఎఫ్ఐఆర్', 'పోలీసు', 'ఫిర్యాదు', 'నేరం', 'అరెస్టు', 'జామీను',
    'एफआयआर', 'पोलिस', 'तक्रार', 'गुन्हा', 'गुन्हेगार', 'अटक', 'जामीन',
    'એફઆઈઆર', 'પોલીસ', 'ફરિયાદ', 'ગુનો', 'ગુનેગાર', 'જામીન',
    'എഫ്ഐആർ', 'പോലീസ്', 'പരാതി', 'കുറ്റം', 'അറസ്റ്റ്', 'ജാമ്യം',
    'ਏਫਆਈਆਰ', 'ਪੁਲਿਸ', 'ਸ਼ਿਕਾਇਤ', 'ਅਪਰਾਧ', 'ਗਿਰਫਤਾਰੀ', 'ਜ਼ਮਾਨਤ',
    'ಎಫ್ಐಆರ್', 'ಪೊಲೀಸ್', 'ದೂರು', 'ಅರೆಸ್ಟ್', 'ಜಾಮೀನು',
    'ଏଫଆଇଆର', 'ପୋଲିସ', 'ଅଭିଯୋଗ', 'ଅପରାଧ', 'ଗିରଫତାରି', 'ଜାମିନ'
]

FAMILY_KEYWORDS = [
    'divorce', 'marriage', 'custody', 'alimony', 'maintenance', 'family', 'spouse', 'child',
    'तलाक', 'विवाह', 'संरक्षण', 'गुजारा भत्ता', 'परिवार', 'पति', 'पत्नी', 'बच्चा',
    'তালাক', 'বিবাহ', 'অভিভাবকত্ব', 'ভরণপোষণ', 'পরিবার', 'স্বামী', 'স্ত্রী', 'সন্তান',
    'விவாகரத்து', 'திருமணம்', 'வளர்ப்பு', 'பராமரிப்பு', 'குடும்பம்', 'கணவர்', 'மனைவி', 'குழந்தை',
    'విడాకులు', 'వివాహం', 'సంరక్షణ', 'జీవనాధారం', 'కుటుంబం', 'భర్త', 'భార్య', 'పిల్లలు',
    'घटस्फोट', 'लग्न', 'संरक्षण', 'कुटुंब', 'पती', 'पत्नी',
    'છૂટાછેડા', 'લગ્ન', 'સંભાળ', 'કુટુંબ', 'પતિ', 'પત્ની',
    'വിവാഹമോചനം', 'വിവാഹം', 'സംരക്ഷണം', 'കുടുംബം', 'ഭർത്താവ്', 'ഭാര്യ', 'കുട്ടി',
    'ਤਲਾਕ', 'ਵਿਆਹ', 'ਸੰਭਾਲ', 'ਪਰਿਵਾਰ', 'ਪਤੀ', 'ਪਤਨੀ', 'ਬੱਚਾ',
    'ವಿವಾಹ ವಿಚ್ಛೇದನ', 'ವಿವಾಹ', 'ಸಂರಕ್ಷಣೆ', 'ಕುಟುಂಬ', 'ಪತಿ', 'ಪತ್ನಿ', 'ಮಗು',
    'ବିବାହ ବିଚ୍ଛେଦ', 'ବିବାହ', 'ସଂରକ୍ଷଣ', 'ପରିବାର', 'ପତି', 'ପତ୍ନୀ', 'ପିଲା'
]

CONTRACT_KEYWORDS = [
    'contract', 'agreement', 'breach', 'damages', 'employment', 'job', 'work', 'salary',
    'अनुबंध', 'समझौता', 'उल्लंघन', 'नुकसान', 'रोजगार', 'नौकरी', 'काम', 'वेतन',
    'চুক্তি', 'লঙ্ঘন', 'ক্ষতি', 'চাকরি', 'কাজ', 'বেতন',
    'ஒப்பந்தம்', 'மீறல்', 'சேதம்', 'வேலை', 'சம்பளம்',
    'ఒప్పందం', 'ఉల్లంఘన', 'నష్టం', 'ఉద్యోగం', 'జీతం',
    'करार', 'उल्लंघन', 'नुकसान', 'रोजगार', 'नोकरी', 'काम', 'पगार',
    'કરાર', 'ઉલ્લંઘન', 'નુકસાન', 'રોજગાર', 'નોકરી', 'કામ', 'પગાર',
    'കരാർ', 'ലംഘനം', 'നഷ്ടം', 'ജോലി', 'ശമ്പളം',
    'ਸਮਝੌਤਾ', 'ਉਲੰਘਣ', 'ਨੁਕਸਾਨ', 'ਰੋਜ਼ਗਾਰ', 'ਨੌਕਰੀ', 'ਕੰਮ', 'ਤਨਖਾਹ',
    'ಒಪ್ಪಂದ', 'ಉಲ್ಲಂಘನೆ', 'ನಷ್ಟ', 'ಉದ್ಯೋಗ', 'ಕೆಲಸ', 'ಸಂಬಳ',
    'ଚୁକ୍ତି', 'ଉଲ୍ଲଂଘନ', 'କ୍ଷତି', 'ଚାକିରି', 'କାମ', 'ବେତନ'
]

CONSUMER_KEYWORDS = [
    'consumer', 'refund', 'defective', 'warranty', 'product', 'service', 'purchase',
    'उपभोक्ता', 'वापसी', 'दोषपूर्ण', 'वारंटी', 'शिकायत', 'उत्पाद', 'सेवा', 'खरीद',
    'ভোক্তা', 'ফেরত', 'ত্রুটিপূর্ণ', 'ওয়ারেন্টি', 'অভিযোগ', 'পণ্য', 'সেবা', 'ক্রয়',
    'நுகர்வோர்', 'குறைபாடு', 'உத்தரவாதம்', 'தயாரிப்பு', 'சேவை', 'வாங்குதல்',
    'వినియోగదారుడు', 'వాపసు', 'లోపం', 'వారంటీ', 'ఫిర్యాదు', 'ఉత్పత్తి', 'సేవ', 'కొనుగోలు',
    'ग्राहक', 'परतावा', 'दोषपूर्ण', 'वॉरंटी', 'तक्रार', 'उत्पाद', 'सेवा', 'खरेदी',
    'ગ્રાહક', 'પરતાવો', 'દોષપૂર્ણ', 'વોરંટી', 'ઉત્પાદન', 'સેવા', 'ખરીદી',
    'ഉപഭോക്താവ്', 'തിരിച്ചുകൊടുക്കൽ', 'വാറന്റി', 'പരാതി', 'ഉൽപ്പന്നം', 'സേവനങ്ങൾ',
    'ਗ੍ਰਾਹਕ', 'ਵਾਪਸੀ', 'ਦੋਸ਼ਪੂਰਨ', 'ਵਾਰੰਟੀ', 'ਸ਼ਿਕਾਇਤ', 'ਉਤਪਾਦ', 'ਸੇਵਾ', 'ਖਰੀਦ',
    'ಗ್ರಾಹಕ', 'ಹಿಂತಿರುಗಿಸುವಿಕೆ', 'ದೋಷಪೂರಿತ', 'ದೂರು', 'ಉತ್ಪನ್ನ', 'ಸೇವೆ', 'ಖರೀದಿ',
    'ଗ୍ରାହକ', 'ଫେରସ୍ତ', 'ଦୋଷପୂର୍ଣ୍ଣ', 'ଓାରାଣ୍ଟି', 'ଉତ୍ପାଦ', 'ସେବା', 'କ୍ରୟ'
]

OFFLINE_RESPONSE_TEMPLATES = [
    (
        TENANT_KEYWORDS,
        """**Tenant Rights in India - Comprehensive Guide**

**Key Rights You Have:**
1. **Right to Peaceful Enjoyment**: Landlord cannot disrupt possession without notice
2. **Right to Essential Services**: Water, electricity and lifts must be maintained
3. **Right to Privacy**: 24‑hour notice before inspection/entry
4. **Protection from Arbitrary Eviction**: Written notice + valid legal grounds required
5. **Right to Fair Rent**: Increase must follow Rent Control/Model Tenancy Act norms

**Important Laws:**
- Transfer of Property Act, 1882
- Model Tenancy Act, 2021 (if adopted by your state)
- State‑specific Rent Control Acts

**Next steps if your rights are violated:**
1. Document calls, messages, videos and bills
2. Send a legal notice referencing the tenancy agreement
3. Approach the Rent Authority / Rent Court under the Model Tenancy Act
4. Seek injunction/interim relief if the landlord tries illegal eviction"""
    ),
    (
        FIR_KEYWORDS,
        """**Filing FIR & Criminal Procedure (BNSS, 2023)**

**Steps to file an FIR:**
1. Go to the police station with jurisdiction over the incident
2. Provide date, time, location, people involved and evidence
3. Insist on a free copy of the FIR (Section 173 BNSS)
4. Track investigation status through the Investigating Officer

**If police refuse to register FIR:**
1. Send a written complaint to the Superintendent of Police (Section 193 BNSS)
2. File an application before the Magistrate under Section 156(3) BNSS
3. Escalate to State Human Rights Commission / cybercrime portal for cyber offences

**Key statutes:**
- Bharatiya Nagarik Suraksha Sanhita (BNSS), 2023
- Bharatiya Nyaya Sanhita (BNS), 2023
- Protection of Human Rights Act, 1993"""
    ),
    (
        FAMILY_KEYWORDS,
        """**Family Law: Divorce, Custody & Maintenance**

**Divorce grounds (mutual + contested):**
- Cruelty, adultery, desertion (Sections 28‑32, Special Marriage Act)
- Conversion, mental disorder, venereal disease (relevant personal laws)
- Mutual consent: two motions, 6‑month cooling (waivable by court)

**Child custody factors:**
- Best interest & welfare of child is paramount
- Joint/visitation orders possible; child’s preference (12+ years) considered
- Guardians and Wards Act, 1890 governs interim guardianship

**Maintenance/alimony:**
- Section 125 BNSS (successor to CrPC) for interim/regular maintenance
- Hindu Marriage Act Sections 24/25, Special Marriage Act Section 37
- Enforcement through civil imprisonment/attachment if unpaid"""
    ),
    (
        CONTRACT_KEYWORDS,
        """**Contract & Employment Remedies**

**Valid contract essentials (Indian Contract Act, 1872):**
1. Offer + acceptance
2. Lawful consideration
3. Competent parties (18+, sound mind)
4. Free consent (no coercion/fraud/misrepresentation)
5. Lawful object

**Breach remedies:**
- Specific performance (Specific Relief Act, 2018)
- Damages (compensatory, liquidated, nominal)
- Injunctions to restrain competing acts
- Rescission + restitution

**Action plan:**
1. Compile signed agreements, emails, invoices, salary slips
2. Send a legal notice citing clauses breached
3. Approach commercial court / labour authority depending on contract type
4. Seek interim relief (Order XXXIX CPC) if urgent"""
    ),
    (
        CONSUMER_KEYWORDS,
        """**Consumer Protection Act, 2019 Workflow**

**Your rights:**
1. Right to safety from hazardous goods/services
2. Right to information about quality, purity and price
3. Right to choose and be heard
4. Right to seek redress before Consumer Commissions

**Where to file:**
- District Commission: value up to ₹1 crore
- State Commission: ₹1 crore – ₹10 crore
- National Commission: above ₹10 crore

**Filing steps:**
1. Draft complaint with invoices, chats, defect photos
2. Pay nominal fee (₹100–₹750); e-filing available at e-daakhil.nic.in
3. Attend mediation/hearing; seek refund, replacement, compensation or penalty under Section 39"""
    )
]

DEFAULT_OFFLINE_RESPONSE = """**General Legal Guidance (India)**

**Core rights and safety-nets:**
- Article 14–18: Equality before law & protection from discrimination
- Article 19–22: Freedom of speech, movement, profession with reasonable restrictions
- Article 32: Direct access to Supreme Court for rights enforcement

**If you face a legal issue:**
1. Write down facts (date, time, people, evidence)
2. Preserve digital proofs (emails, chats, bank SMS)
3. File a police complaint / e‑FIR for cognizable cyber offences (1930 helpline & cybercrime.gov.in)
4. Approach Legal Services Authority for free legal aid if income < prescribed slab

**Helpful institutions:**
- Supreme Court & respective High Court websites for cause-list/orders
- District Legal Services Authority for Lok Adalat / mediation
- Consumer Commissions, Family Courts, Cyber Police Stations"""


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
        base_instruction = "You are a helpful legal AI for Indian law. Answer clearly and practically. Always reference current Indian legal framework (BNS, BNSS, BSA instead of IPC, CrPC, Evidence Act). Cite specific laws and sections. If unsure, advise consulting a qualified lawyer."
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
            response = requests.post(api_url, headers=headers, json=payload, timeout=30)
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

1. **Right to peaceful enjoyment**: Your landlord cannot disturb your peaceful possession of the property.

2. **Right to notice**: For eviction, landlords must provide proper notice as per state laws.

3. **Right to essential services**: Landlords must maintain essential services like water, electricity.

4. **Right to privacy**: Landlords cannot enter your premises without notice.

5. **Protection against arbitrary rent increases**: Rent increases must follow legal procedures.

Please note: Laws vary by state. For specific situations, consult a local lawyer."""

    elif any(word in question_lower for word in ['fir', 'police', 'complaint', 'crime']):
        return """For filing an FIR (First Information Report) in India:

1. **Go to the nearest police station** where the incident occurred.

2. **Provide detailed information** about the incident, including:
   - Date, time, and location
   - Description of what happened
   - Names of people involved
   - Any evidence or witnesses

3. **Get acknowledgment**: The police must give you a copy of the FIR.

4. **Follow up**: Keep track of the investigation progress.

5. **Legal remedies**: If police refuse to file FIR, you can approach the Superintendent of Police or file a complaint with the Magistrate.

**Legal Framework**: This process is governed by the Bharatiya Nagarik Suraksha Sanhita (BNSS), 2023, which replaced the Code of Criminal Procedure (CrPC).

Remember: FIR is your right for cognizable offenses. Don't hesitate to seek legal help if needed."""

    elif any(word in question_lower for word in ['divorce', 'marriage', 'custody', 'alimony']):
        return """For family law matters in India:

**Divorce Process:**
1. **Grounds for divorce**: Adultery, cruelty, desertion, conversion, mental disorder, etc.
2. **Mutual consent**: Both parties can file for divorce by mutual consent.
3. **Court procedures**: File petition in family court with proper documentation.

**Child Custody:**
1. **Best interest of child**: Courts prioritize child's welfare.
2. **Joint custody**: Both parents can share custody.
3. **Visitation rights**: Non-custodial parent has visitation rights.

**Important**: Family law is complex and varies by personal laws (Hindu, Muslim, Christian, etc.). Consult a family lawyer for specific advice."""

    elif any(word in question_lower for word in ['contract', 'agreement', 'breach', 'damages']):
        return """For contract-related issues in India:

**Essential Elements of a Valid Contract:**
1. **Offer and acceptance**
2. **Consideration** (something of value)
3. **Competent parties**
4. **Free consent**
5. **Lawful object**

**Breach of Contract Remedies:**
1. **Specific performance**: Court can order performance of contract
2. **Damages**: Monetary compensation for losses
3. **Injunction**: Court order to stop certain actions
4. **Rescission**: Cancellation of contract

**Important**: Contract law is governed by the Indian Contract Act, 1872. For complex matters, consult a contract lawyer."""

    else:
        return """I understand you're seeking legal advice. Here's some general guidance:

**General Legal Rights in India:**
1. **Right to legal aid**: Free legal aid is available for those who cannot afford lawyers
2. **Right to fair trial**: Everyone has the right to a fair and speedy trial
3. **Right to legal representation**: You have the right to be represented by a lawyer
4. **Right to information**: You can access public information under RTI Act

**Important Disclaimer**: 
- This is general information only
- Laws vary by state and personal circumstances
- Always consult a qualified lawyer for specific legal advice
- For urgent matters, contact legal aid services immediately

**Emergency Contacts:**
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
        fallback_signature = legal_advisor.get_fallback_response(language).strip().lower()
        normalized_answer = (gemini_answer or '').strip()
        lower_answer = normalized_answer.lower()
        if (
            normalized_answer
            and not lower_answer.startswith("gemini api key not set")
            and not lower_answer.startswith("error")
            and lower_answer != fallback_signature
        ):
            # If Gemini returns answer in English but we need another language, translate it
            if language != 'en' and normalized_answer == legal_advisor.get_fallback_response('en'):
                return legal_advisor.translate_text(normalized_answer, language)
            return normalized_answer

        # Fallback to intelligent response
        return get_intelligent_legal_response(question, language)
        
    except Exception:
        # Fallback to intelligent response
        return get_intelligent_legal_response(question, language)

def get_intelligent_legal_response(question: str, language: str = 'en') -> str:
    """Provide intelligent legal responses using curated templates."""
    question_lower = (question or '').lower()

    response = None
    for keywords, template in OFFLINE_RESPONSE_TEMPLATES:
        if any(word in question_lower for word in keywords):
            response = template
            break

    if response is None:
        response = DEFAULT_OFFLINE_RESPONSE

    if language != 'en':
        try:
            return legal_advisor.translate_text(response, language)
        except Exception:
            return response
    return response

