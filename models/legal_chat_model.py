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
            'ka': 'ka',  # kannada 
        }
        
        # Legal context prompts for AI models
        self.legal_prompts = {
            'en': """You are a legal AI assistant specializing in Indian law. Provide clear, practical legal advice based on Indian legal framework. Focus on:
1. Relevant Indian laws and regulations
2. Practical steps the person can take
3. Available legal remedies and procedures
4. Important deadlines and time limits
5. When to consult a lawyer
6. Available legal aid resources

Keep responses helpful, accurate, and actionable. If you're unsure about specific legal details, recommend consulting a qualified lawyer.

Question: {question}

Provide legal advice:""",
            
            'hi': """आप भारतीय कानून में विशेषज्ञता रखने वाले कानूनी AI सहायक हैं। भारतीय कानूनी ढांचे के आधार पर स्पष्ट, व्यावहारिक कानूनी सलाह दें। इन पर ध्यान दें:
1. प्रासंगिक भारतीय कानून और नियम
2. व्यक्ति द्वारा उठाए जा सकने वाले व्यावहारिक कदम
3. उपलब्ध कानूनी उपचार और प्रक्रियाएं
4. महत्वपूर्ण समय सीमाएं
5. वकील से कब सलाह लें
6. उपलब्ध कानूनी सहायता संसाधन

प्रतिक्रियाएं सहायक, सटीक और कार्रवाई योग्य रखें। यदि आप विशिष्ट कानूनी विवरणों के बारे में अनिश्चित हैं, तो योग्य वकील से सलाह लेने की सिफारिश करें।

प्रश्न: {question}

कानूनी सलाह दें:""",
            
            'or': """ଆପଣ ଭାରତୀୟ ଆଇନରେ ବିଶେଷଜ୍ଞତା ଥିବା ଆଇନଗତ AI ସହାୟକ ଅଟନ୍ତି। ଭାରତୀୟ ଆଇନଗତ ଢାଞ୍ଚା ଉପରେ ଆଧାର କରି ସ୍ପଷ୍ଟ, ବ୍ୟବହାରିକ ଆଇନଗତ ପରାମର୍ଶ ଦିଅନ୍ତୁ। ଏହା ଉପରେ ଧ୍ୟାନ ଦିଅନ୍ତୁ:
1. ପ୍ରାସଙ୍ଗିକ ଭାରତୀୟ ଆଇନ ଏବଂ ନିୟମ
2. ବ୍ୟକ୍ତି ଦ୍ୱାରା ନିଆଯାଇପାରିବା ବ୍ୟବହାରିକ ପଦକ୍ଷେପ
3. ଉପଲବ୍ଧ ଆଇନଗତ ପ୍ରତିକାର ଏବଂ ପ୍ରକ୍ରିୟା
4. ଗୁରୁତ୍ୱପୂର୍ଣ୍ଣ ସମୟ ସୀମା
5. କେବେ ବକୀଳଙ୍କ ସହ ପରାମର୍ଶ ନିଅନ୍ତୁ
6. ଉପଲବ୍ଧ ଆଇନଗତ ସହାୟତା ସମ୍ବଳ

ପ୍ରତିକ୍ରିୟା ସହାୟକ, ସଠିକ ଏବଂ କାର୍ଯ୍ୟକାରୀ ରଖନ୍ତୁ। ଯଦି ଆପଣ ବିଶେଷ ଆଇନଗତ ବିବରଣୀ ବିଷୟରେ ଅନିଶ୍ଚିତ ଅଟନ୍ତି, ତେବେ ଯୋଗ୍ୟ ବକୀଳଙ୍କ ସହ ପରାମର୍ଶ ନେବାକୁ ପରାମର୍ଶ ଦିଅନ୍ତୁ।

ପ୍ରଶ୍ନ: {question}

ଆଇନଗତ ପରାମର୍ଶ ଦିଅନ୍ତୁ:"""
        }
        
        # Fallback responses for when all AI models are not available
        self.fallback_responses = {
            'en': 'I apologize, but I\'m currently unable to provide detailed legal advice. Please consult a qualified lawyer for your specific situation.',
            'hi': 'मैं क्षमा चाहता हूं, लेकिन मैं वर्तमान में विस्तृत कानूनी सलाह प्रदान करने में असमर्थ हूं। कृपया अपनी विशिष्ट स्थिति के लिए योग्य वकील से सलाह लें।',
            'or': 'ମୁଁ କ୍ଷମା ଚାହୁଁଛି, କିନ୍ତୁ ମୁଁ ବର୍ତ୍ତମାନ ବିସ୍ତୃତ ଆଇନଗତ ପରାମର୍ଶ ପ୍ରଦାନ କରିପାରୁ ନାହିଁ। ଦୟାକରି ଆପଣଙ୍କ ବିଶେଷ ପରିସ୍ଥିତି ପାଇଁ ଯୋଗ୍ୟ ବକୀଳଙ୍କ ସହ ପରାମର୍ଶ ନିଅନ୍ତୁ।'
        }
    
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
        """Get appropriate legal prompt for the language"""
        if language in self.legal_prompts:
            return self.legal_prompts[language].format(question=question)
        else:
            # Default to English prompt
            return self.legal_prompts['en'].format(question=question)
    
    def get_fallback_response(self, language: str = 'en') -> str:
        """Get fallback response when all AI models are not available"""
        return self.fallback_responses.get(language, self.fallback_responses['en'])

# Global instance
legal_advisor = LegalAdviceGenerator()


def get_gemini_answer(question: str) -> str:
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
            'gemini-1.5-pro-latest',
            'gemini-1.5-flash-latest'
        ]

        legal_prompt = legal_advisor.get_legal_prompt(question, 'en')

        headers = {
            "Content-Type": "application/json",
        }

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": "You are a helpful legal AI for Indian law. Answer clearly and practically. If unsure, advise consulting a qualified lawyer."},
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
        return get_fallback_legal_response(question)

    except Exception as e:
        try:
            from app import logger
            logger.error(f"Gemini API error: {str(e)}")
        except Exception:
            pass
        return get_fallback_legal_response(question)

 

 

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
        return "Could you please provide a question that addresses a specific legal issue."
    
    try:
        # Try Gemini first
        gemini_answer = get_gemini_answer(question.strip())
        if gemini_answer and not gemini_answer.startswith("Gemini API key not set") and not gemini_answer.startswith("Error"):
            if language != 'en':
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
    
    # Enhanced keyword-based responses with more detailed information
    if any(word in question_lower for word in ['tenant', 'rent', 'eviction', 'landlord', 'lease', 'rental']):
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

    elif any(word in question_lower for word in ['fir', 'police', 'complaint', 'crime', 'criminal']):
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
2. File a complaint with the Magistrate under Section 156(3) CrPC
3. Send a written complaint to the State Human Rights Commission

**Important Laws:**
- **Criminal Procedure Code (CrPC)**
- **Indian Penal Code (IPC)**
- **Protection of Human Rights Act**

**Emergency Contacts:**
- Police: 100
- Women Helpline: 181
- Child Helpline: 1098

**⚠️ Important**: For serious crimes, contact a criminal lawyer immediately."""

    elif any(word in question_lower for word in ['divorce', 'marriage', 'custody', 'alimony', 'maintenance']):
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

    elif any(word in question_lower for word in ['contract', 'agreement', 'breach', 'damages', 'employment']):
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

    elif any(word in question_lower for word in ['consumer', 'refund', 'defective', 'warranty', 'complaint']):
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
