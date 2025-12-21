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
        self.base_legal_prompt = """You are a legal AI assistant specializing in Indian law. Provide clear, practical legal advice based on Indian legal framework.

CRITICAL FORMATTING REQUIREMENT: ALWAYS format your answer in clear bullet points or numbered points. Use markdown formatting:
- Use bullet points (- or •) for lists
- Use numbered points (1., 2., 3.) for sequential steps
- Use bold text (**text**) for emphasis on key terms
- Use headers (##) for major sections
- NEVER write long paragraphs. Break everything into points.

Focus on:
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

Keep responses helpful, accurate, and actionable. Format everything in clear points. If you're unsure about specific legal details, recommend consulting a qualified lawyer.

Question: {question}

Provide legal advice in point format:"""
        
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

# Keywords for filing FIR (general police complaints)
FIR_KEYWORDS = [
    'fir', 'file fir', 'filing fir', 'police complaint', 'register complaint', 'police report',
    'एफआईआर दर्ज', 'पुलिस शिकायत', 'शिकायत दर्ज',
    'এফআইআর দায়ের', 'পুলিশ অভিযোগ',
    'எஃப்ஐஆர் பதிவு', 'காவல்துறை புகார்',
    'ఎఫ్ఐఆర్ నమోదు', 'పోలీసు ఫిర్యాదు',
    'એફઆઈઆર દાખલ', 'પોલીસ ફરિયાદ',
    'എഫ്ഐആർ രജിസ്റ്റർ', 'പോലീസ് പരാതി',
    'ਏਫਆਈਆਰ ਦਰਜ', 'ਪੁਲਿਸ ਸ਼ਿਕਾਇਤ',
    'ಎಫ್ಐಆರ್ ದಾಖಲೆ', 'ಪೊಲೀಸ್ ದೂರು',
    'ଏଫଆଇଆର ଦାଖଲ', 'ପୋଲିସ ଅଭିଯୋଗ'
]

# Keywords for arrest rights (specific to rights when arrested)
ARREST_RIGHTS_KEYWORDS = [
    'arrest', 'arrested', 'rights if arrested', 'what are my rights', 'arrest rights', 'police arrest',
    'गिरफ्तार', 'गिरफ्तारी', 'अधिकार', 'गिरफ्तारी के अधिकार',
    'গ্রেফতার', 'অধিকার', 'গ্রেফতারের অধিকার',
    'கைது', 'உரிமைகள்', 'கைது உரிமைகள்',
    'అరెస్టు', 'అధికారాలు', 'అరెస్టు అధికారాలు',
    'अटक', 'अधिकार', 'अटक अधिकार',
    'અટક', 'અધિકાર', 'અટક અધિકાર',
    'അറസ്റ്റ്', 'അവകാശങ്ങൾ', 'അറസ്റ്റ് അവകാശങ്ങൾ',
    'ਗਿਰਫਤਾਰੀ', 'ਅਧਿਕਾਰ', 'ਗਿਰਫਤਾਰੀ ਅਧਿਕਾਰ',
    'ಅರೆಸ್ಟ್', 'ಅಧಿಕಾರಗಳು', 'ಅರೆಸ್ಟ್ ಅಧಿಕಾರಗಳು',
    'ଗିରଫତାରି', 'ଅଧିକାର', 'ଗିରଫତାରି ଅଧିକାର'
]

# Keywords for cybercrime (all cybercrime cases - victims, perpetrators, general questions)
CYBERCRIME_KEYWORDS = [
    # General cybercrime terms
    'cybercrime', 'cyber crime', 'cyber law', 'cyber security', 'cyber attack', 'cyber offence',
    'cyber fraud', 'online fraud', 'digital fraud', 'internet fraud', 'computer crime',
    'victim of cybercrime', 'cybercrime victim', 'cybercrime case', 'cybercrime complaint',
    # Specific types of cybercrime
    'hacking', 'phishing', 'upi fraud', 'bank fraud', 'online scam', 'digital scam',
    'identity theft', 'data breach', 'malware', 'ransomware', 'cyber stalking', 'cyber harassment',
    'online harassment', 'sextortion', 'revenge porn', 'cyber bullying', 'social media crime',
    'email fraud', 'credit card fraud', 'online transaction fraud', 'e-commerce fraud',
    'it act', 'information technology act', 'it act 2000', 'cyber law india',
    # Hindi
    'साइबर अपराध', 'साइबर क्राइम', 'साइबर कानून', 'साइबर धोखाधड़ी', 'ऑनलाइन धोखाधड़ी',
    'साइबर अपराध का शिकार', 'साइबर अपराध मामला', 'साइबर अपराध शिकायत',
    'हैकिंग', 'फ़िशिंग', 'यूपीआई धोखाधड़ी', 'बैंक धोखाधड़ी', 'ऑनलाइन स्कैम',
    'आईटी अधिनियम', 'सूचना प्रौद्योगिकी अधिनियम',
    # Bengali
    'সাইবার অপরাধ', 'সাইবার ক্রাইম', 'সাইবার আইন', 'অনলাইন প্রতারণা',
    'সাইবার অপরাধের শিকার', 'সাইবার অপরাধ মামলা', 'সাইবার অপরাধ অভিযোগ',
    # Tamil
    'சைபர் குற்றம்', 'சைபர் சட்டம்', 'ஆன்லைன் மோசடி', 'சைபர் குற்றத்தின் பாதிக்கப்பட்டவர்',
    'சைபர் குற்ற வழக்கு', 'சைபர் குற்ற புகார்',
    # Telugu
    'సైబర్ నేరం', 'సైబర్ చట్టం', 'ఆన్లైన్ మోసం', 'సైబర్ నేరం బాధితుడు',
    'సైబర్ నేరం కేసు', 'సైబర్ నేరం ఫిర్యాదు',
    # Marathi
    'सायबर गुन्हा', 'सायबर कायदा', 'ऑनलाइन फसवणूक', 'सायबर गुन्हा बळी',
    'सायबर गुन्हा केस', 'सायबर गुन्हा तक्रार',
    # Gujarati
    'સાયબર ગુનો', 'સાયબર કાયદો', 'ઓનલાઇન ફસાવટ', 'સાયબર ગુનો ભોગવનાર',
    'સાયબર ગુનો કેસ', 'સાયબર ગુનો ફરિયાદ',
    # Malayalam
    'സൈബർ കുറ്റം', 'സൈബർ നിയമം', 'ഓൺലൈൻ തട്ടിപ്പ്', 'സൈബർ കുറ്റത്തിന്റെ ഇര',
    'സൈബർ കുറ്റം കേസ്', 'സൈബർ കുറ്റം പരാതി',
    # Punjabi
    'ਸਾਈਬਰ ਅਪਰਾਧ', 'ਸਾਈਬਰ ਕਾਨੂੰਨ', 'ਔਨਲਾਈਨ ਧੋਖਾਧੜੀ', 'ਸਾਈਬਰ ਅਪਰਾਧ ਦਾ ਸ਼ਿਕਾਰ',
    'ਸਾਈਬਰ ਅਪਰਾਧ ਕੇਸ', 'ਸਾਈਬਰ ਅਪਰਾਧ ਸ਼ਿਕਾਇਤ',
    # Kannada
    'ಸೈಬರ್ ಅಪರಾಧ', 'ಸೈಬರ್ ಕಾನೂನು', 'ಆನ್ಲೈನ್ ವಂಚನೆ', 'ಸೈಬರ್ ಅಪರಾಧದ ಬಲಿ',
    'ಸೈಬರ್ ಅಪರಾಧ ಪ್ರಕರಣ', 'ಸೈಬರ್ ಅಪರಾಧ ದೂರು',
    # Odia
    'ସାଇବର ଅପରାଧ', 'ସାଇବର ଆଇନ', 'ଅନଲାଇନ୍ ଠକାମି', 'ସାଇବର ଅପରାଧର ବଳି',
    'ସାଇବର ଅପରାଧ ମାମଲା', 'ସାଇବର ଅପରାଧ ଅଭିଯୋଗ'
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
        CYBERCRIME_KEYWORDS,
        """**Cybercrime Law & Remedies in India - Comprehensive Guide**

**If you are a victim of cybercrime:**

**Immediate Steps:**
1. **Preserve Evidence**: Save screenshots, emails, transaction records, chat logs, and any digital evidence
2. **Report to Cyber Police**: File a complaint at your nearest cyber police station or online at cybercrime.gov.in
3. **File e-FIR**: For cognizable cyber offences, file an e-FIR through the National Cyber Crime Reporting Portal
4. **Contact Helpline**: Call 1930 (National Cyber Crime Helpline) for assistance

**Your Rights as a Cybercrime Victim:**
1. **Right to File Complaint**: You can file a complaint at any police station (Section 154 BNSS)
2. **Right to Investigation**: Police must investigate cognizable offences (Section 157 BNSS)
3. **Right to Compensation**: You may seek compensation under Section 357 BNSS
4. **Right to Legal Aid**: Free legal aid available through Legal Services Authority

**Common Cybercrime Offences & Penalties:**
1. **Hacking** (Section 66 IT Act): Up to 3 years imprisonment and/or fine
2. **Phishing/Fraud** (Section 66C IT Act): Up to 3 years and fine up to ₹1 lakh
3. **Identity Theft** (Section 66C IT Act): Up to 3 years and fine
4. **Cyber Stalking/Harassment** (Section 354D BNS): Up to 3 years and fine
5. **Data Breach** (Section 43A IT Act): Compensation for damages
6. **Online Fraud** (Section 420 BNS): Up to 7 years and fine

**Relevant Laws:**
- **Information Technology Act, 2000** (IT Act) - Primary cyber law
- **Bharatiya Nyaya Sanhita (BNS), 2023** (replaces IPC) - Criminal offences
- **Bharatiya Nagarik Suraksha Sanhita (BNSS), 2023** (replaces CrPC) - Procedure
- **Bharatiya Sakshya Adhiniyam (BSA), 2023** (replaces Evidence Act) - Digital evidence

**Important**: Act quickly to preserve digital evidence as it can be deleted or modified. Document everything and seek legal assistance if needed."""
    ),
    (
        ARREST_RIGHTS_KEYWORDS,
        """**Your Rights if Arrested (India) - Comprehensive Guide**

**Fundamental Rights When Arrested:**

1. **Right to Know the Grounds**: You have the right to be informed of the grounds of arrest (Article 22(1) of Constitution, Section 50 BNSS)

2. **Right to Legal Representation**: 
   - You can consult a lawyer of your choice
   - Right to free legal aid if you cannot afford a lawyer (Article 39A)
   - Police must inform you of this right (Section 41D BNSS)

3. **Right to Inform Family/Friend**: 
   - You can have someone informed about your arrest (Section 41A BNSS)
   - Police must inform a relative or friend of your choice

4. **Right to Medical Examination**: 
   - You can request medical examination if needed
   - Mandatory for women (Section 53 BNSS)

5. **Right to Bail**: 
   - For bailable offences, bail is a right (Section 436 BNSS)
   - For non-bailable offences, you can apply for bail (Section 437 BNSS)

6. **Right Against Self-Incrimination**: 
   - You cannot be compelled to be a witness against yourself (Article 20(3))
   - You have the right to remain silent

7. **Right to Speedy Trial**: 
   - You have the right to a speedy and fair trial
   - Cannot be detained indefinitely without trial

**Important Legal Framework:**
- Article 20, 21, 22 of the Constitution of India
- Bharatiya Nagarik Suraksha Sanhita (BNSS), 2023
- Bharatiya Nyaya Sanhita (BNS), 2023

**If Your Rights are Violated:**
1. File a complaint with the Human Rights Commission
2. Approach the Magistrate or High Court
3. Seek compensation for illegal detention
4. Contact Legal Services Authority for free legal aid"""
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


def get_openai_answer(question: str, language: str = 'en', previous_cases: list[dict] = None) -> str:
    """Get answer from OpenAI API with context from previous cases"""
    try:
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            return "OpenAI API key not set. Set OPENAI_API_KEY environment variable."

        # Fetch relevant court cases from Indian court databases (not local SQLite)
        # Only fetch if previous_cases is None AND question is legal (not identity/unrelated)
        if previous_cases is None:
            previous_cases = []
            # Check if this is a legal question before fetching cases
            try:
                from policy import is_legal_question, is_identity_question
                is_legal = is_legal_question(question)
                is_identity = is_identity_question(question)
                should_fetch_cases = is_legal and not is_identity
            except Exception:
                # If policy functions not available, default to fetching (backward compatibility)
                should_fetch_cases = True
            
            if should_fetch_cases:
                try:
                    # Search for relevant cases from Indian courts using RSS feeds
                    if requests is not None:
                        try:
                            # Use RSS feeds from Indian Kanoon
                            from app import _parse_rss_feed
                            rss_feeds = [
                                'https://indiankanoon.org/feeds/sc.rss',  # Supreme Court
                                'https://indiankanoon.org/feeds/hc.rss',  # High Courts
                            ]
                            
                            for feed_url in rss_feeds[:2]:  # Limit to 2 feeds
                                try:
                                    feed_results = _parse_rss_feed(feed_url, limit=3)
                                    for item in feed_results:
                                        previous_cases.append({
                                            'title': item.get('title', ''),
                                            'court': item.get('court', ''),
                                            'date': item.get('date', ''),
                                            'citation': item.get('citation', ''),
                                            'url': item.get('url', ''),
                                            'summary': item.get('summary', '')
                                        })
                                        if len(previous_cases) >= 5:
                                            break
                                    if len(previous_cases) >= 5:
                                        break
                                except Exception as feed_err:
                                    try:
                                        from app import logger
                                        logger.debug(f"RSS feed {feed_url} failed: {feed_err}")
                                    except Exception:
                                        pass
                                    continue
                            
                            # If RSS feeds didn't return enough results, fallback to DuckDuckGo
                            if len(previous_cases) < 3:
                                try:
                                    from app import _duckduckgo_search_official
                                    results = _duckduckgo_search_official(question, limit=5)
                                    for item in results:
                                        previous_cases.append({
                                            'title': item.get('title', ''),
                                            'court': item.get('court', ''),
                                            'date': item.get('date', ''),
                                            'citation': item.get('citation', ''),
                                            'url': item.get('url', ''),
                                            'summary': item.get('snippet', '')
                                        })
                                        if len(previous_cases) >= 5:
                                            break
                                except Exception as ddg_err:
                                    try:
                                        from app import logger
                                        logger.warning(f"DuckDuckGo fallback also failed: {ddg_err}")
                                    except Exception:
                                        pass
                        except Exception as rss_err:
                            try:
                                from app import logger
                                logger.info(f"RSS feed search failed: {rss_err}")
                            except Exception:
                                pass
                            # Fallback to DuckDuckGo if RSS fails
                            try:
                                from app import _duckduckgo_search_official
                                results = _duckduckgo_search_official(question, limit=5)
                                for item in results:
                                    previous_cases.append({
                                        'title': item.get('title', ''),
                                        'court': item.get('court', ''),
                                        'date': item.get('date', ''),
                                        'citation': item.get('citation', ''),
                                        'url': item.get('url', ''),
                                        'summary': item.get('snippet', '')
                                    })
                            except Exception as ddg_err:
                                try:
                                    from app import logger
                                    logger.warning(f"DuckDuckGo search failed: {ddg_err}")
                                except Exception:
                                    pass
                    else:
                        # Fallback to DuckDuckGo if requests not available
                        try:
                            from app import _duckduckgo_search_official
                            results = _duckduckgo_search_official(question, limit=5)
                            for item in results:
                                previous_cases.append({
                                    'title': item.get('title', ''),
                                    'court': item.get('court', ''),
                                    'date': item.get('date', ''),
                                    'citation': item.get('citation', ''),
                                    'url': item.get('url', ''),
                                    'summary': item.get('snippet', '')
                                })
                        except Exception as ddg_err:
                            try:
                                from app import logger
                                logger.warning(f"DuckDuckGo search failed: {ddg_err}")
                            except Exception:
                                pass
                except Exception as e:
                    try:
                        from app import logger
                        logger.warning(f"Failed to fetch court cases: {e}")
                    except Exception:
                        pass

        # Build context from previous court cases
        cases_context = ""
        if previous_cases:
            cases_context = "\n\n**Relevant Indian Court Cases (from Indian court databases):**\n"
            for idx, case in enumerate(previous_cases, 1):
                cases_context += f"\n**Case {idx}:**\n"
                if case.get('title'):
                    cases_context += f"- **Title:** {case.get('title')}\n"
                if case.get('court'):
                    cases_context += f"- **Court:** {case.get('court')}\n"
                if case.get('date'):
                    cases_context += f"- **Date:** {case.get('date')}\n"
                if case.get('citation'):
                    cases_context += f"- **Citation:** {case.get('citation')}\n"
                if case.get('summary'):
                    cases_context += f"- **Summary:** {case.get('summary')}\n"
                if case.get('url'):
                    cases_context += f"- **Link:** {case.get('url')}\n"
            cases_context += "\n**IMPORTANT:** Reference these court cases in your answer. Include relevant case citations and explain how these precedents relate to the user's question. Format your answer in clear points, mentioning specific cases where relevant.\n"

        # Get legal prompt
        legal_prompt = legal_advisor.get_legal_prompt(question, language)

        # Use translated instruction based on the language
        base_instruction = """You are a helpful legal AI for Indian law. Answer clearly and practically in POINT FORMAT (use bullet points or numbered lists). Always reference current Indian legal framework (BNS, BNSS, BSA instead of IPC, CrPC, Evidence Act). Cite specific laws and sections. If unsure, advise consulting a qualified lawyer.

FORMATTING REQUIREMENTS:
- Always format answers as bullet points (-) or numbered points (1., 2., 3.)
- Use bold (**text**) for emphasis on important terms, laws, or sections
- Use headers (##) for major sections
- Keep each point concise and clear
- Organize information in logical sections with clear headers
- NEVER write long paragraphs. Always break information into points.

When answering questions, you have access to previous court cases and their results. Use this information to:
1. Reference similar cases and their outcomes
2. Provide context about how similar situations were handled
3. Explain patterns or precedents from previous cases
4. Help users understand what to expect based on similar cases

Always prioritize accuracy and cite specific laws and sections. Format everything in clear, organized points.
IMPORTANT: You must respond in the same language as this instruction. All your responses must be written entirely in the language of this instruction."""
        
        instruction = legal_advisor.translate_text(base_instruction, language)

        # Combine instruction, cases context, and legal prompt
        full_prompt = instruction + cases_context + "\n\n" + legal_prompt

        # OpenAI API call
        model = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')
        api_url = "https://api.openai.com/v1/chat/completions"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": instruction
                },
                {
                    "role": "user",
                    "content": full_prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 2000
        }

        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            try:
                choices = data.get("choices", [])
                if choices and len(choices) > 0:
                    text = choices[0].get("message", {}).get("content", "").strip()
                    if text:
                        return text
            except Exception as e:
                try:
                    from app import logger
                    logger.error(f"Error parsing OpenAI response: {e}")
                except Exception:
                    pass
        else:
            error_text = f"{response.status_code}: {response.text}"
            try:
                from app import logger
                logger.error(f"OpenAI API error: {error_text}")
            except Exception:
                pass

        return legal_advisor.get_fallback_response(language)

    except Exception as e:
        try:
            from app import logger
            logger.error(f"OpenAI API error: {str(e)}")
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

def get_legal_advice(question: str, language: str = 'en', previous_cases: list[dict] = None) -> str:
    """Main function to get legal advice using OpenAI first, then fallback"""
    if not question or not question.strip():
        base_message = "Could you please provide a question that addresses a specific legal issue."
        return legal_advisor.translate_text(base_message, language)
    
    try:
        # Try OpenAI first with language-specific prompt and previous cases context
        openai_answer = get_openai_answer(question.strip(), language, previous_cases)
        fallback_signature = legal_advisor.get_fallback_response(language).strip().lower()
        normalized_answer = (openai_answer or '').strip()
        lower_answer = normalized_answer.lower()
        if (
            normalized_answer
            and not lower_answer.startswith("openai api key not set")
            and not lower_answer.startswith("error")
            and lower_answer != fallback_signature
        ):
            # If OpenAI returns answer in English but we need another language, translate it
            if language != 'en' and normalized_answer == legal_advisor.get_fallback_response('en'):
                return legal_advisor.translate_text(normalized_answer, language)
            return normalized_answer

        # Fallback to intelligent response
        return get_intelligent_legal_response(question, language)
        
    except Exception:
        # Fallback to intelligent response
        return get_intelligent_legal_response(question, language)

def get_intelligent_legal_response(question: str, language: str = 'en') -> str:
    """Provide intelligent legal responses using curated templates with priority-based matching."""
    question_lower = (question or '').lower()

    # Use priority-based matching: more specific keywords should match first
    # Calculate match scores for each template (number of matching keywords)
    scored_templates = []
    for keywords, template in OFFLINE_RESPONSE_TEMPLATES:
        matches = sum(1 for word in keywords if word in question_lower)
        if matches > 0:
            scored_templates.append((matches, template))
    
    # Sort by match count (descending) to prioritize templates with more keyword matches
    scored_templates.sort(key=lambda x: x[0], reverse=True)
    
    # Use the template with the highest match score
    response = None
    if scored_templates:
        response = scored_templates[0][1]
    else:
        response = DEFAULT_OFFLINE_RESPONSE

    if language != 'en':
        try:
            return legal_advisor.translate_text(response, language)
        except Exception:
            return response
    return response

