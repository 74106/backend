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
    from deeptranslator import GoogleTranslator
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


def get_gemini_answer(question: str, language: str = 'en') -> str:
    """Get answer from Google Gemini via REST API"""
    try:
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            return "Gemini API key not set. Set GEMINI_API_KEY environment variable."

        # Endpoint and model selection (use v1beta and Gemini 2.0 models)
        primary_model = os.environ.get('GEMINI_MODEL', 'gemini-2.0-flash-exp')
        model_candidates = [
            primary_model,
            'gemini-2.0-flash-exp',
            'gemini-2.5-flash-exp',
        ]

        legal_prompt = legal_advisor.get_legal_prompt(question, language)

        headers = {
            "Content-Type": "application/json",
        }

        # Use translated instruction based on the language
        base_instruction = "You are a helpful legal AI for Indian law. Answer clearly and practically. Always reference current Indian legal framework (BNS, BNSS, BSA instead of IPC, CrPC, Evidence Act)."
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
        # English
        'tenant', 'rent', 'eviction', 'landlord', 'lease', 'rental',
        # Hindi
        'किरायेदार', 'किराया', 'बेदखली', 'मकान मालिक', 'लीज', 'किराये',
        # Bengali
        'ভাড়াটিয়া', 'ভাড়া', 'উচ্ছেদ', 'বাড়িওয়ালা', 'লিজ', 'ভাড়া',
        # Tamil
        'வாடகைதாரர்', 'வாடகை', 'வெளியேற்றம்', 'வீட்டு உரிமையாளர்', 'லீஸ்', 'வாடகை',
        # Telugu
        'అద్దెదారుడు', 'అద్దె', 'బహిష్కరణ', 'ఇల్లు యజమాని', 'లీజ్', 'అద్దె',
        # Marathi
        'भाडेकरू', 'भाडे', 'बेदखली', 'घर मालक', 'लीज', 'भाडे',
        # Gujarati
        'ભાડેકરૂ', 'ભાડું', 'બહિષ્કરણ', 'ઘર માલિક', 'લીઝ', 'ભાડું',
        # Malayalam
        'വാടകക്കാരൻ', 'വാടക', 'പുറത്താക്കൽ', 'വീട് ഉടമ', 'ലീസ്', 'വാടക',
        # Punjabi
        'ਕਿਰਾਏਦਾਰ', 'ਕਿਰਾਇਆ', 'ਬੇਦਖਲੀ', 'ਘਰ ਮਾਲਕ', 'ਲੀਜ਼', 'ਕਿਰਾਇਆ',
        # Kannada
        'ಬಾಡಿಗೆದಾರ', 'ಬಾಡಿಗೆ', 'ಹೊರಹಾಕುವಿಕೆ', 'ಮನೆ ಮಾಲೀಕ', 'ಲೀಜ್', 'ಬಾಡಿಗೆ',
        # Odia
        'ଭଡ଼ାଦାର', 'ଭଡ଼ା', 'ବହିଷ୍କରଣ', 'ଘର ମାଲିକ', 'ଲିଜ୍', 'ଭଡ଼ା'
    ]
    
    if any(word in question_lower for word in tenant_keywords):
        response = """**Tenant Rights in India - Comprehensive Guide**

**Key Rights You Have:**
1. **Right to Peaceful Enjoyment**: Your landlord cannot disturb your peaceful possession without proper notice
2. **Right to Essential Services**: Landlords must maintain water, electricity, and other essential services
3. **Right to Privacy**: Landlords cannot enter your premises without 24-hour notice
4. **Protection from Arbitrary Eviction**: Eviction requires proper legal notice and valid grounds
5. **Right to Fair Rent**: Rent increases must follow legal procedures and be reasonable

**Important Laws:**
- **Rent Control Acts** (varies by state)
- **Transfer of Property Act, 1882**
- **Model Tenancy Act, 2021** (if adopted by your state)

**What to Do if Your Rights are Violated:**
1. Document everything (photos, videos, written communications)
2. Send a legal notice to your landlord
3. File a complaint with the Rent Control Court
4. Contact local legal aid services

**Emergency Contacts:**
- Legal Aid: 1800-345-6789
- State Legal Services Authority

**⚠️ Important**: Laws vary by state. For specific cases, consult a local property lawyer."""

    # Multilingual keyword matching for FIR/police issues
    fir_keywords = [
        # English
        'fir', 'police', 'complaint', 'crime', 'criminal', 'arrest', 'bail', 'court',
        # Hindi
        'एफआईआर', 'पुलिस', 'शिकायत', 'अपराध', 'अपराधी', 'गिरफ्तार', 'जमानत', 'अदालत', 'कानूनी',
        # Bengali
        'এফআইআর', 'পুলিশ', 'অভিযোগ', 'অপরাধ', 'অপরাধী', 'গ্রেফতার', 'জামিন', 'আদালত', 'আইনি',
        # Tamil
        'எஃப்ஐஆர்', 'காவல்துறை', 'புகார்', 'குற்றம்', 'குற்றவாளி', 'கைது', 'ஜாமீன்', 'நீதிமன்றம்', 'சட்டம்',
        # Telugu
        'ఎఫ్ఐఆర్', 'పోలీసు', 'ఫిర్యాదు', 'నేరం', 'నేరస్థుడు', 'అరెస్టు', 'జామీను', 'కోర్టు', 'చట్టం',
        # Marathi
        'एफआयआर', 'पोलिस', 'तक्रार', 'गुन्हा', 'गुन्हेगार', 'अटक', 'जामीन', 'न्यायालय', 'कायदेशीर',
        # Gujarati
        'એફઆઈઆર', 'પોલીસ', 'ફરિયાદ', 'ગુનો', 'ગુનેગાર', 'અટકાવ', 'જામીન', 'કોર્ટ', 'કાયદાકીય',
        # Malayalam
        'എഫ്ഐആർ', 'പോലീസ്', 'പരാതി', 'കുറ്റം', 'കുറ്റവാളി', 'അറസ്റ്റ്', 'ജാമ്യം', 'കോടതി', 'നിയമം',
        # Punjabi
        'ਏਫਆਈਆਰ', 'ਪੁਲਿਸ', 'ਸ਼ਿਕਾਇਤ', 'ਅਪਰਾਧ', 'ਅਪਰਾਧੀ', 'ਗਿਰਫਤਾਰੀ', 'ਜ਼ਮਾਨਤ', 'ਕੋਰਟ', 'ਕਾਨੂੰਨੀ',
        # Kannada
        'ಎಫ್ಐಆರ್', 'ಪೊಲೀಸ್', 'ದೂರು', 'ಪಾಪ', 'ಪಾಪಿ', 'ಅರೆಸ್ಟ್', 'ಜಾಮೀನು', 'ನ್ಯಾಯಾಲಯ', 'ಕಾನೂನುಬದ್ಧ',
        # Odia
        'ଏଫଆଇଆର', 'ପୋଲିସ', 'ଅଭିଯୋଗ', 'ଅପରାଧ', 'ଅପରାଧୀ', 'ଗିରଫତାରି', 'ଜାମିନ', 'କୋର୍ଟ', 'କାନୁନିକ'
    ]
    
    if any(word in question_lower for word in fir_keywords):
        response = """**Filing FIR and Criminal Law in India**

**How to File an FIR:**
1. **Go to the nearest police station** where the incident occurred
2. **Provide complete details**: Date, time, location, description of incident
3. **Get acknowledgment**: Police must give you a copy of the FIR
4. **Follow up**: Keep track of investigation progress

**Your Rights During FIR Process:**
- Right to get a copy of FIR free of cost
- Right to know the status of investigation
- Right to legal representation
- Right to file complaint if police refuse to register FIR

**If Police Refuse to File FIR:**
1. Approach the Superintendent of Police (SP)
2. File a complaint with the Magistrate under Section 156(3) BNSS
3. Send a written complaint to the State Human Rights Commission

**Important Laws:**
- **Bharatiya Nagarik Suraksha Sanhita (BNSS), 2023** (replaces CrPC)
- **Bharatiya Nyaya Sanhita (BNS), 2023** (replaces IPC)
- **Protection of Human Rights Act**

**Emergency Contacts:**
- Police: 100
- Women Helpline: 181
- Child Helpline: 1098

**⚠️ Important**: For serious crimes, contact a criminal lawyer immediately."""

    # Multilingual keyword matching for family law issues
    family_keywords = [
        # English
        'divorce', 'marriage', 'custody', 'alimony', 'maintenance', 'family', 'spouse', 'child',
        # Hindi
        'तलाक', 'विवाह', 'संरक्षण', 'गुजारा भत्ता', 'रखरखाव', 'परिवार', 'पति', 'पत्नी', 'बच्चा',
        # Bengali
        'তালাক', 'বিবাহ', 'অভিভাবকত্ব', 'ভরণপোষণ', 'রক্ষণাবেক্ষণ', 'পরিবার', 'স্বামী', 'স্ত্রী', 'শিশু',
        # Tamil
        'விவாகரத்து', 'திருமணம்', 'வளர்ப்பு', 'பராமரிப்பு', 'குடும்பம்', 'கணவர்', 'மனைவி', 'குழந்தை',
        # Telugu
        'విడాకులు', 'వివాహం', 'సంరక్షణ', 'జీవనాధారం', 'రక్షణ', 'కుటుంబం', 'భర్త', 'భార్య', 'పిల్ల',
        # Marathi
        'घटस्फोट', 'लग्न', 'संरक्षण', 'गुजारा भत्ता', 'रखरखाव', 'कुटुंब', 'पती', 'पत्नी', 'मूल',
        # Gujarati
        'છૂટાછેડા', 'લગ્ન', 'સંભાળ', 'ગુજારા ભથ્થું', 'રક્ષણ', 'કુટુંબ', 'પતિ', 'પત્ની', 'બાળક',
        # Malayalam
        'വിവാഹമോചനം', 'വിവാഹം', 'സംരക്ഷണം', 'ജീവിതാധാരം', 'പരിപാലനം', 'കുടുംബം', 'ഭർത്താവ്', 'ഭാര്യ', 'കുട്ടി',
        # Punjabi
        'ਤਲਾਕ', 'ਵਿਆਹ', 'ਸੰਭਾਲ', 'ਗੁਜ਼ਾਰਾ ਭੱਤਾ', 'ਰੱਖ-ਰਖਾਵ', 'ਪਰਿਵਾਰ', 'ਪਤੀ', 'ਪਤਨੀ', 'ਬੱਚਾ',
        # Kannada
        'ವಿವಾಹ ವಿಚ್ಛೇದನ', 'ವಿವಾಹ', 'ಸಂರಕ್ಷಣೆ', 'ಜೀವನಾಧಾರ', 'ರಕ್ಷಣೆ', 'ಕುಟುಂಬ', 'ಪತಿ', 'ಪತ್ನಿ', 'ಮಗು',
        # Odia
        'ବିବାହ ବିଚ୍ଛେଦ', 'ବିବାହ', 'ସଂରକ୍ଷଣ', 'ଜୀବିକା', 'ରକ୍ଷଣ', 'ପରିବାର', 'ପତି', 'ପତ୍ନୀ', 'ପିଲା'
    ]
    
    if any(word in question_lower for word in family_keywords):
        response = """**Family Law in India - Marriage, Divorce & Custody**

**Divorce Process:**
1. **Grounds for Divorce**:
   - Adultery, cruelty, desertion
   - Conversion to another religion
   - Mental disorder, communicable disease
   - Mutual consent (simplest process)

2. **Court Procedures**:
   - File petition in Family Court
   - Mediation and counseling (mandatory)
   - Final hearing and decree

**Child Custody:**
- **Best Interest of Child** is the primary consideration
- Both parents can get joint custody
- Visitation rights for non-custodial parent
- Child's preference considered (if above 12 years)

**Maintenance/Alimony:**
- Spouse maintenance based on income and needs
- Child maintenance until 18 years (or longer if studying)
- Interim maintenance during proceedings

**Important Laws:**
- **Hindu Marriage Act, 1955**
- **Muslim Personal Law**
- **Special Marriage Act, 1954**
- **Guardians and Wards Act, 1890**

**⚠️ Important**: Family law varies by religion. Consult a family lawyer for specific advice."""

    # Multilingual keyword matching for contract issues
    contract_keywords = [
        # English
        'contract', 'agreement', 'breach', 'damages', 'employment', 'job', 'work', 'salary',
        # Hindi
        'अनुबंध', 'समझौता', 'उल्लंघन', 'नुकसान', 'रोजगार', 'नौकरी', 'काम', 'वेतन',
        # Bengali
        'চুক্তি', 'চুক্তি', 'লঙ্ঘন', 'ক্ষতি', 'চাকরি', 'কাজ', 'বেতন',
        # Tamil
        'ஒப்பந்தம்', 'ஒப்பந்தம்', 'மீறல்', 'சேதம்', 'வேலை', 'வேலை', 'சம்பளம்',
        # Telugu
        'ఒప్పందం', 'ఒప్పందం', 'ఉల్లంఘన', 'నష్టం', 'ఉద్యోగం', 'పని', 'జీతం',
        # Marathi
        'करार', 'करार', 'उल्लंघन', 'नुकसान', 'रोजगार', 'नोकरी', 'काम', 'पगार',
        # Gujarati
        'કરાર', 'કરાર', 'ઉલ્લંઘન', 'નુકસાન', 'રોજગાર', 'નોકરી', 'કામ', 'પગાર',
        # Malayalam
        'കരാർ', 'കരാർ', 'ലംഘനം', 'നഷ്ടം', 'ജോലി', 'ജോലി', 'ശമ്പളം',
        # Punjabi
        'ਸਮਝੌਤਾ', 'ਸਮਝੌਤਾ', 'ਉਲੰਘਣ', 'ਨੁਕਸਾਨ', 'ਰੋਜ਼ਗਾਰ', 'ਨੌਕਰੀ', 'ਕੰਮ', 'ਤਨਖਾਹ',
        # Kannada
        'ಒಪ್ಪಂದ', 'ಒಪ್ಪಂದ', 'ಉಲ್ಲಂಘನೆ', 'ನಷ್ಟ', 'ಉದ್ಯೋಗ', 'ಕೆಲಸ', 'ಸಂಬಳ',
        # Odia
        'ଚୁକ୍ତି', 'ଚୁକ୍ତି', 'ଉଲ୍ଲଂଘନ', 'କ୍ଷତି', 'ଚାକିରି', 'କାମ', 'ବେତନ'
    ]
    
    if any(word in question_lower for word in contract_keywords):
        response = """**Contract Law in India**

**Essential Elements of Valid Contract:**
1. **Offer and Acceptance**
2. **Consideration** (something of value)
3. **Competent Parties** (18+ years, sound mind)
4. **Free Consent** (not under coercion, fraud, misrepresentation)
5. **Lawful Object** (not illegal or immoral)

**Types of Contracts:**
- **Employment Contracts**: Governed by labor laws
- **Service Agreements**: Professional services
- **Sales Contracts**: Goods and services
- **Lease Agreements**: Property rental

**Breach of Contract Remedies:**
1. **Specific Performance**: Court orders performance
2. **Damages**: Monetary compensation
3. **Injunction**: Court order to stop certain actions
4. **Rescission**: Cancellation of contract

**Important Laws:**
- **Indian Contract Act, 1872**
- **Sale of Goods Act, 1930**
- **Industrial Disputes Act, 1947**

**What to Do if Contract is Breached:**
1. Send legal notice
2. Try mediation/negotiation
3. File suit in appropriate court
4. Seek interim relief if urgent

**⚠️ Important**: Contract law is complex. Consult a contract lawyer for specific cases."""

    # Multilingual keyword matching for consumer issues
    consumer_keywords = [
        # English
        'consumer', 'refund', 'defective', 'warranty', 'complaint', 'product', 'service', 'purchase',
        # Hindi
        'उपभोक्ता', 'वापसी', 'दोषपूर्ण', 'वारंटी', 'शिकायत', 'उत्पाद', 'सेवा', 'खरीद',
        # Bengali
        'ভোক্তা', 'ফেরত', 'ত্রুটিপূর্ণ', 'ওয়ারেন্টি', 'অভিযোগ', 'পণ্য', 'সেবা', 'ক্রয়',
        # Tamil
        'நுகர்வோர்', 'திரும்ப', 'குறைபாடு', 'உத்தரவாதம்', 'புகார்', 'தயாரிப்பு', 'சேவை', 'வாங்குதல்',
        # Telugu
        'వినియోగదారుడు', 'వాపసు', 'లోపం', 'వారంటీ', 'ఫిర్యాదు', 'ఉత్పత్తి', 'సేవ', 'కొనుగోలు',
        # Marathi
        'ग्राहक', 'परतावा', 'दोषपूर्ण', 'वॉरंटी', 'तक्रार', 'उत्पाद', 'सेवा', 'खरेदी',
        # Gujarati
        'ગ્રાહક', 'પરતાવો', 'દોષપૂર્ણ', 'વોરંટી', 'ફરિયાદ', 'ઉત્પાદન', 'સેવા', 'ખરીદી',
        # Malayalam
        'ഉപഭോക്താവ്', 'തിരിച്ചുകൊടുക്കൽ', 'കുറ്റവാളി', 'വാറന്റി', 'പരാതി', 'ഉൽപ്പന്നം', 'സേവനം', 'വാങ്ങൽ',
        # Punjabi
        'ਗ੍ਰਾਹਕ', 'ਵਾਪਸੀ', 'ਦੋਸ਼ਪੂਰਨ', 'ਵਾਰੰਟੀ', 'ਸ਼ਿਕਾਇਤ', 'ਉਤਪਾਦ', 'ਸੇਵਾ', 'ਖਰੀਦ',
        # Kannada
        'ಗ್ರಾಹಕ', 'ಹಿಂತಿರುಗಿಸುವಿಕೆ', 'ದೋಷಪೂರಿತ', 'ಅಡೆತಡೆ', 'ದೂರು', 'ಉತ್ಪನ್ನ', 'ಸೇವೆ', 'ಖರೀದಿ',
        # Odia
        'ଗ୍ରାହକ', 'ଫେରସ୍ତ', 'ଦୋଷପୂର୍ଣ୍ଣ', 'ଓାରାଣ୍ଟି', 'ଅଭିଯୋଗ', 'ଉତ୍ପାଦ', 'ସେବା', 'କ୍ରୟ'
    ]
    
    if any(word in question_lower for word in consumer_keywords):
        response = """**Consumer Rights in India**

**Your Rights as a Consumer:**
1. **Right to Safety**: Protection from hazardous goods/services
2. **Right to Information**: Complete information about products
3. **Right to Choose**: Freedom to select from various options
4. **Right to be Heard**: Voice complaints and concerns
5. **Right to Redressal**: Seek compensation for unfair practices

**How to File Consumer Complaint:**
1. **District Consumer Forum** (up to ₹1 crore)
2. **State Commission** (₹1 crore to ₹10 crores)
3. **National Commission** (above ₹10 crores)

**Process:**
- File complaint with supporting documents
- Pay nominal fee (₹100-500)
- Hearing and evidence presentation
- Order and execution

**Important Laws:**
- **Consumer Protection Act, 2019**
- **Competition Act, 2002**

**⚠️ Important**: Keep all receipts and documents. File complaint within 2 years of cause of action."""

    else:
        response = """**General Legal Guidance for India**

**Your Fundamental Rights:**
1. **Right to Equality** (Article 14-18)
2. **Right to Freedom** (Article 19-22)
3. **Right against Exploitation** (Article 23-24)
4. **Right to Freedom of Religion** (Article 25-28)
5. **Cultural and Educational Rights** (Article 29-30)
6. **Right to Constitutional Remedies** (Article 32)

**Legal Aid Available:**
- **Free Legal Aid**: For those who cannot afford lawyers
- **Legal Services Authorities**: At district, state, and national levels
- **Lok Adalats**: For quick dispute resolution

**Important Legal Resources:**
- **Supreme Court of India**
- **High Courts** (state level)
- **District Courts** (local level)
- **Consumer Forums**
- **Family Courts**

**Emergency Legal Contacts:**
- Legal Aid: 1800-345-6789
- Women Helpline: 181
- Child Helpline: 1098
- Senior Citizen Helpline: 14567

**⚠️ Important Disclaimer**: 
This is general legal information. Laws are complex and vary by case. Always consult a qualified lawyer for specific legal advice. For urgent matters, contact legal aid services immediately."""

    # Translate if needed
    if language != 'en':
        try:
            translated_response = legal_advisor.translate_text(response, language)
            return translated_response
        except:
            return response
    
    return response
