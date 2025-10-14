"""Policy helpers for NyaySetu legal chat.

Provides functions to detect identity questions, detect legal intent heuristically,
and apply a policy that enforces legal-only responses with trusted source citations.
"""
from __future__ import annotations

from typing import Optional

# Trusted legal sources and databases for Indian law
TRUSTED_LEGAL_SOURCES = {
    'primary_laws': {
        'criminal_law': 'Bharatiya Nyaya Sanhita (BNS), 2023',
        'criminal_procedure': 'Bharatiya Nagarik Suraksha Sanhita (BNSS), 2023', 
        'evidence_law': 'Bharatiya Sakshya Adhiniyam (BSA), 2023',
        'civil_law': 'Code of Civil Procedure (CPC), 1908',
        'constitutional_law': 'Constitution of India, 1950'
        'legal_law': 'National Portal of India'
    },
    'secondary_sources': [
        'Supreme Court of India judgments',
        'High Court judgments',
        'Legal Services Authorities Act, 1987',
        'Consumer Protection Act, 2019',
        'Right to Information Act, 2005',
        'Protection of Women from Domestic Violence Act, 2005',
        'Motor Vehicles Act, 1988',
        'Indian Contract Act, 1872',
        'Transfer of Property Act, 1882'
        'Ministry of Law and Justice'
        'Law Comission of India'
    ],
    'databases': [
        'Supreme Court of India official website',
        'High Court official websites',
        'Ministry of Law and Justice, Government of India',
        'Legal Information Management and Briefing System (LIMBS)',
        'National Legal Services Authority (NALSA)'
    ]
}


def is_identity_question(text: Optional[str]) -> bool:
    t = (text or '').strip().lower()
    triggers = [
        "who are you",
        "what are you",
        "who is this",
        "identify yourself",
        "what is your name",
        "are you a bot",
    ]
    return any(trigger in t for trigger in triggers)


def is_legal_question(text: Optional[str]) -> bool:
    t = (text or '').strip().lower()
    legal_keywords = [
        # English keywords
        'law', 'legal', 'rights', 'police', 'court', 'complaint', 'fir', 'appeal', 'rti', 'eviction',
        'divorce', 'custody', 'contract', 'agreement', 'charge', 'arrest', 'evidence', 'bail', 'sue', 'lawsuit',
        # New Indian legal framework keywords
        'bns', 'bharatiya nyaya sanhita', 'bnss', 'bharatiya nagarik suraksha sanhita', 
        'bsa', 'bharatiya sakshya adhiniyam', 'ipc', 'crpc', 'evidence act',
        'constitution', 'article', 'fundamental rights', 'legal aid', 'advocate', 'lawyer',
        'judgment', 'verdict', 'legal precedent', 'case law', 'statute', 'act', 'section',
        
        # Hindi legal keywords
        'कानून', 'कानूनी', 'अधिकार', 'पुलिस', 'अदालत', 'शिकायत', 'गिरफ्तार', 'जमानत', 'वकील', 'न्याय',
        'तलाक', 'संरक्षण', 'अनुबंध', 'समझौता', 'आरोप', 'साक्ष्य', 'मुकदमा', 'संविधान', 'अनुच्छेद',
        'मौलिक अधिकार', 'कानूनी सहायता', 'न्यायाधीश', 'फैसला', 'कानूनी मिसाल', 'अधिनियम', 'धारा',
        'भारतीय न्याय संहिता', 'भारतीय नागरिक सुरक्षा संहिता', 'भारतीय साक्ष्य अधिनियम',
        
        # Bengali legal keywords
        'আইন', 'আইনি', 'অধিকার', 'পুলিশ', 'আদালত', 'অভিযোগ', 'গ্রেফতার', 'জামিন', 'আইনজীবী', 'বিচার',
        'তালাক', 'অভিভাবকত্ব', 'চুক্তি', 'চুক্তি', 'অভিযোগ', 'প্রমাণ', 'মামলা', 'সংবিধান', 'অনুচ্ছেদ',
        'মৌলিক অধিকার', 'আইনি সহায়তা', 'বিচারক', 'রায়', 'আইনি নজির', 'আইন', 'ধারা',
        
        # Tamil legal keywords
        'சட்டம்', 'சட்ட', 'உரிமைகள்', 'காவல்துறை', 'நீதிமன்றம்', 'புகார்', 'கைது', 'ஜாமீன்', 'வழக்கறிஞர்', 'நீதி',
        'விவாகரத்து', 'வளர்ப்பு', 'ஒப்பந்தம்', 'ஒப்பந்தம்', 'குற்றச்சாட்டு', 'சாட்சியம்', 'வழக்கு', 'அரசியலமைப்பு', 'பிரிவு',
        'அடிப்படை உரிமைகள்', 'சட்ட உதவி', 'நீதிபதி', 'தீர்ப்பு', 'சட்ட முன்னோடி', 'சட்டம்', 'பிரிவு',
        
        # Telugu legal keywords
        'చట్టం', 'చట్టపరమైన', 'అధికారాలు', 'పోలీసు', 'కోర్టు', 'ఫిర్యాదు', 'అరెస్టు', 'జామీను', 'వకీలు', 'న్యాయం',
        'విడాకులు', 'సంరక్షణ', 'ఒప్పందం', 'ఒప్పందం', 'ఆరోపణ', 'రుజువు', 'కేసు', 'రాజ్యాంగం', 'అధికరణం',
        'ప్రాథమిక హక్కులు', 'చట్టపరమైన సహాయం', 'న్యాయమూర్తి', 'తీర్పు', 'చట్టపరమైన మునుపటి', 'చట్టం', 'సెక్షన్',
        
        # Marathi legal keywords
        'कायदा', 'कायदेशीर', 'अधिकार', 'पोलिस', 'न्यायालय', 'तक्रार', 'अटक', 'जामीन', 'वकील', 'न्याय',
        'घटस्फोट', 'संरक्षण', 'करार', 'करार', 'आरोप', 'पुरावा', 'खटला', 'घटना', 'कलम',
        'मूलभूत अधिकार', 'कायदेशीर मदत', 'न्यायाधीश', 'निर्णय', 'कायदेशीर पूर्वनिर्णय', 'कायदा', 'कलम',
        
        # Gujarati legal keywords
        'કાયદો', 'કાયદાકીય', 'અધિકારો', 'પોલીસ', 'કોર્ટ', 'ફરિયાદ', 'અટકાવ', 'જામીન', 'વકીલ', 'ન્યાય',
        'છૂટાછેડા', 'સંભાળ', 'કરાર', 'કરાર', 'આરોપ', 'પુરાવો', 'કેસ', 'રાજ્યબંધારણ', 'કલમ',
        'મૂળભૂત અધિકારો', 'કાયદાકીય મદદ', 'ન્યાયાધીશ', 'ફેંસલો', 'કાયદાકીય પૂર્વનિર્ણય', 'કાયદો', 'કલમ',
        
        # Malayalam legal keywords
        'നിയമം', 'നിയമപരമായ', 'അവകാശങ്ങൾ', 'പോലീസ്', 'കോടതി', 'പരാതി', 'അറസ്റ്റ്', 'ജാമ്യം', 'വക്കീൽ', 'നീതി',
        'വിവാഹമോചനം', 'സംരക്ഷണം', 'കരാർ', 'കരാർ', 'ആരോപണം', 'തെളിവ്', 'കേസ്', 'ഭരണഘടന', 'അനുഛേദം',
        'അടിസ്ഥാന അവകാശങ്ങൾ', 'നിയമപരമായ സഹായം', 'ജഡ്ജ്', 'വിധി', 'നിയമപരമായ മുൻനിർണയം', 'നിയമം', 'സെക്ഷൻ',
        
        # Punjabi legal keywords
        'ਕਾਨੂੰਨ', 'ਕਾਨੂੰਨੀ', 'ਅਧਿਕਾਰ', 'ਪੁਲਿਸ', 'ਕੋਰਟ', 'ਸ਼ਿਕਾਇਤ', 'ਗਿਰਫਤਾਰੀ', 'ਜ਼ਮਾਨਤ', 'ਵਕੀਲ', 'ਨਿਆਂ',
        'ਤਲਾਕ', 'ਸੰਭਾਲ', 'ਸਮਝੌਤਾ', 'ਸਮਝੌਤਾ', 'ਇਲਜ਼ਾਮ', 'ਸਬੂਤ', 'ਮੁਕੱਦਮਾ', 'ਸੰਵਿਧਾਨ', 'ਧਾਰਾ',
        'ਮੂਲ ਅਧਿਕਾਰ', 'ਕਾਨੂੰਨੀ ਸਹਾਇਤਾ', 'ਜੱਜ', 'ਫੈਸਲਾ', 'ਕਾਨੂੰਨੀ ਪੂਰਵ-ਨਿਰਣਾ', 'ਕਾਨੂੰਨ', 'ਧਾਰਾ',
        
        # Kannada legal keywords
        'ಕಾನೂನು', 'ಕಾನೂನುಬದ್ಧ', 'ಅಧಿಕಾರಗಳು', 'ಪೊಲೀಸ್', 'ನ್ಯಾಯಾಲಯ', 'ದೂರು', 'ಅರೆಸ್ಟ್', 'ಜಾಮೀನು', 'ವಕೀಲ', 'ನ್ಯಾಯ',
        'ವಿವಾಹ ವಿಚ್ಛೇದನ', 'ಸಂರಕ್ಷಣೆ', 'ಒಪ್ಪಂದ', 'ಒಪ್ಪಂದ', 'ಆರೋಪ', 'ಪುರಾವೆ', 'ಕೇಸ್', 'ಸಂವಿಧಾನ', 'ಲೇಖನ',
        'ಮೂಲಭೂತ ಹಕ್ಕುಗಳು', 'ಕಾನೂನುಬದ್ಧ ಸಹಾಯ', 'ನ್ಯಾಯಾಧೀಶ', 'ತೀರ್ಪು', 'ಕಾನೂನುಬದ್ಧ ಮುನ್ನಡೆ', 'ಕಾನೂನು', 'ವಿಭಾಗ',
        
        # Odia legal keywords
        'କାନୁନ', 'କାନୁନିକ', 'ଅଧିକାର', 'ପୋଲିସ', 'କୋର୍ଟ', 'ଅଭିଯୋଗ', 'ଗିରଫତାରି', 'ଜାମିନ', 'ଓକିଲ', 'ନ୍ୟାୟ',
        'ବିବାହ ବିଚ୍ଛେଦ', 'ସଂରକ୍ଷଣ', 'ଚୁକ୍ତି', 'ଚୁକ୍ତି', 'ଆରୋପ', 'ପ୍ରମାଣ', 'କେସ', 'ସମ୍ବିଧାନ', 'ଧାରା',
        'ମୂଳଭୂତ ଅଧିକାର', 'କାନୁନିକ ସହାୟତା', 'ନ୍ୟାୟାଧୀଶ', 'ତିନିପୁ', 'କାନୁନିକ ପୂର୍ବନିର୍ଣ୍ଣୟ', 'କାନୁନ', 'ଧାରା'
    ]
    # Short identity-like questions are not legal questions
    if len(t.split()) <= 5 and is_identity_question(t):
        return False
    return any(k in t for k in legal_keywords)


def apply_policy(original_answer: Optional[str], user_question: str, language: str = 'en') -> str:
    """Enforce policy:
    - Mandatory Legal Disclaimer with source attribution.
    - If user asks about identity, return fixed identity sentence.
    - If user's question is not legal, refuse.
    - Sanitize model output to avoid alternative identity claims.
    - Ensure answer contains legal keywords and source references, else refuse.
    - Maintain a Formal and Neutral Tone.
    - Request Clarification for Ambiguous Queries.
    - Enforce reference to trusted legal sources (BNS, BNSS, BSA for India).
    """
    # Identity question -> fixed identity
    if is_identity_question(user_question):
        if language.startswith('hi'):
            return 'मैं कानूनी जानकारी में विशेषज्ञता वाला एक एआई सहायक हूं।'
        return 'I am a legal chat bot'

    ans = (original_answer or '').strip()
    lower = ans.lower()

    if user_question.lower().startswith("what is") or "explain" in user_question.lower():
        # For definitions, ensure they include source attribution
        if not _has_source_attribution(ans):
            ans = _add_source_attribution(ans, language)
        return ans

    # Non-legal user question -> refusal
    if not is_legal_question(user_question):
        if language.startswith('hi'):
            return 'मैं केवल कानूनी जानकारी प्रदान कर सकता/सकती हूँ। कृपया एक कानूनी प्रश्न पूछें।'
        return 'My function is to provide information on legal topics. Please frame your question accordingly.'

    # Replace or suppress identity mentions
    identity_patterns = [
        'i am chatgpt', 'i am gpt', 'i am a language model', 'i am an ai', 'i am ai', 'i am a chatbot',
        'this is chatgpt', 'chatgpt', 'openai', 'this is gemini', 'this is gemma', 'i am an llm'
    ]
    if any(pat in lower for pat in identity_patterns):
        if language.startswith('hi'):
            return 'मैं कानूनी जानकारी में विशेषज्ञता वाला एक एआई सहायक हूं।'
        return 'I am a legal chat bot'

    # Ensure answer contains legal-related content
    legal_keywords = [
        # English keywords
        'law', 'legal', 'court', 'police', 'rights', 'complaint', 'fir', 'appeal', 'contract', 'bns', 'bnss', 'bsa',
        # Hindi keywords
        'कानून', 'कानूनी', 'अदालत', 'पुलिस', 'अधिकार', 'शिकायत', 'गिरफ्तार', 'अनुबंध', 'भारतीय न्याय संहिता', 'भारतीय नागरिक सुरक्षा संहिता', 'भारतीय साक्ष्य अधिनियम',
        # Bengali keywords
        'আইন', 'আইনি', 'আদালত', 'পুলিশ', 'অধিকার', 'অভিযোগ', 'গ্রেফতার', 'চুক্তি', 'ভারতীয় ন্যায় সংহিতা', 'ভারতীয় নাগরিক সুরক্ষা সংহিতা', 'ভারতীয় সাক্ষ্য অধিনিয়ম',
        # Tamil keywords
        'சட்டம்', 'சட்ட', 'நீதிமன்றம்', 'காவல்துறை', 'உரிமைகள்', 'புகார்', 'கைது', 'ஒப்பந்தம்', 'இந்திய நீதி சங்கிதா', 'இந்திய நாகரிக பாதுகாப்பு சங்கிதா', 'இந்திய சாட்சிய சட்டம்',
        # Telugu keywords
        'చట్టం', 'చట్టపరమైన', 'కోర్టు', 'పోలీసు', 'అధికారాలు', 'ఫిర్యాదు', 'అరెస్టు', 'ఒప్పందం', 'భారతీయ న్యాయ సంహిత', 'భారతీయ నాగరిక సురక్షా సంహిత', 'భారతీయ సాక్ష్య చట్టం',
        # Marathi keywords
        'कायदा', 'कायदेशीर', 'न्यायालय', 'पोलिस', 'अधिकार', 'तक्रार', 'अटक', 'करार', 'भारतीय न्याय संहिता', 'भारतीय नागरिक सुरक्षा संहिता', 'भारतीय साक्ष्य अधिनियम',
        # Gujarati keywords
        'કાયદો', 'કાયદાકીય', 'કોર્ટ', 'પોલીસ', 'અધિકારો', 'ફરિયાદ', 'અટકાવ', 'કરાર', 'ભારતીય ન્યાય સંહિતા', 'ભારતીય નાગરિક સુરક્ષા સંહિતા', 'ભારતીય સાક્ષ્ય અધિનિયમ',
        # Malayalam keywords
        'നിയമം', 'നിയമപരമായ', 'കോടതി', 'പോലീസ്', 'അവകാശങ്ങൾ', 'പരാതി', 'അറസ്റ്റ്', 'കരാർ', 'ഭാരതീയ നീതി സംഹിത', 'ഭാരതീയ നാഗരിക സുരക്ഷാ സംഹിത', 'ഭാരതീയ സാക്ഷ്യ നിയമം',
        # Punjabi keywords
        'ਕਾਨੂੰਨ', 'ਕਾਨੂੰਨੀ', 'ਕੋਰਟ', 'ਪੁਲਿਸ', 'ਅਧਿਕਾਰ', 'ਸ਼ਿਕਾਇਤ', 'ਗਿਰਫਤਾਰੀ', 'ਸਮਝੌਤਾ', 'ਭਾਰਤੀ ਨਿਆਂ ਸੰਹਿਤਾ', 'ਭਾਰਤੀ ਨਾਗਰਿਕ ਸੁਰੱਖਿਆ ਸੰਹਿਤਾ', 'ਭਾਰਤੀ ਸਾਕਸ਼ਯ ਐਕਟ',
        # Kannada keywords
        'ಕಾನೂನು', 'ಕಾನೂನುಬದ್ಧ', 'ನ್ಯಾಯಾಲಯ', 'ಪೊಲೀಸ್', 'ಅಧಿಕಾರಗಳು', 'ದೂರು', 'ಅರೆಸ್ಟ್', 'ಒಪ್ಪಂದ', 'ಭಾರತೀಯ ನ್ಯಾಯ ಸಂಹಿತೆ', 'ಭಾರತೀಯ ನಾಗರಿಕ ಸುರಕ್ಷಾ ಸಂಹಿತೆ', 'ಭಾರತೀಯ ಸಾಕ್ಷ್ಯ ಅಧಿನಿಯಮ',
        # Odia keywords
        'କାନୁନ', 'କାନୁନିକ', 'କୋର୍ଟ', 'ପୋଲିସ', 'ଅଧିକାର', 'ଅଭିଯୋଗ', 'ଗିରଫତାରି', 'ଚୁକ୍ତି', 'ଭାରତୀୟ ନ୍ୟାୟ ସଂହିତା', 'ଭାରତୀୟ ନାଗରିକ ସୁରକ୍ଷା ସଂହିତା', 'ଭାରତୀୟ ସାକ୍ଷ୍ୟ ଅଧିନିୟମ'
    ]
    if not any(k in lower for k in legal_keywords):
        if language.startswith('hi'):
            return 'मैं केवल कानूनी जानकारी प्रदान कर सकता/सकती हूँ। कृपया एक कानूनी प्रश्न पूछें।'
        return 'My function is to provide information on legal topics. Please frame your question accordingly.'

    # Enforce source attribution for legal answers
    if not _has_source_attribution(ans):
        ans = _add_source_attribution(ans, language)

    return ans


def _has_source_attribution(text: str) -> bool:
    """Check if the text already contains source attribution."""
    text_lower = text.lower()
    source_indicators = [
        # English indicators
        'according to', 'as per', 'under', 'section', 'article', 'act of', 'law of',
        'bns', 'bnss', 'bsa', 'ipc', 'crpc', 'constitution', 'supreme court',
        'high court', 'judgment', 'case law', 'legal precedent', 'statute',
        
        # Hindi indicators
        'के अनुसार', 'के तहत', 'धारा', 'अनुच्छेद', 'अधिनियम', 'कानून के अनुसार',
        'भारतीय न्याय संहिता', 'भारतीय नागरिक सुरक्षा संहिता', 'भारतीय साक्ष्य अधिनियम',
        'सुप्रीम कोर्ट', 'हाई कोर्ट', 'फैसला', 'कानूनी मिसाल', 'संविधान',
        
        # Bengali indicators
        'অনুসারে', 'অধীনে', 'ধারা', 'অনুচ্ছেদ', 'আইন', 'আইন অনুসারে',
        'ভারতীয় ন্যায় সংহিতা', 'ভারতীয় নাগরিক সুরক্ষা সংহিতা', 'ভারতীয় সাক্ষ্য অধিনিয়ম',
        'সুপ্রিম কোর্ট', 'হাই কোর্ট', 'রায়', 'আইনি নজির', 'সংবিধান',
        
        # Tamil indicators
        'படி', 'கீழ்', 'பிரிவு', 'அனுசோதனை', 'சட்டம்', 'சட்டத்தின் படி',
        'இந்திய நீதி சங்கிதா', 'இந்திய நாகரிக பாதுகாப்பு சங்கிதா', 'இந்திய சாட்சிய சட்டம்',
        'சுப்ரீம் கோர்ட்', 'ஹை கோர்ட்', 'தீர்ப்பு', 'சட்ட முன்னோடி', 'அரசியலமைப்பு',
        
        # Telugu indicators
        'ప్రకారం', 'కింద', 'సెక్షన్', 'అధికరణం', 'చట్టం', 'చట్టం ప్రకారం',
        'భారతీయ న్యాయ సంహిత', 'భారతీయ నాగరిక సురక్షా సంహిత', 'భారతీయ సాక్ష్య చట్టం',
        'సుప్రీం కోర్ట్', 'హై కోర్ట్', 'తీర్పు', 'చట్టపరమైన మునుపటి', 'రాజ్యాంగం',
        
        # Marathi indicators
        'नुसार', 'खाली', 'कलम', 'अनुच्छेद', 'कायदा', 'कायद्यानुसार',
        'भारतीय न्याय संहिता', 'भारतीय नागरिक सुरक्षा संहिता', 'भारतीय साक्ष्य अधिनियम',
        'सुप्रीम कोर्ट', 'हाई कोर्ट', 'निर्णय', 'कायदेशीर पूर्वनिर्णय', 'घटना',
        
        # Gujarati indicators
        'અનુસાર', 'નીચે', 'કલમ', 'અનુછેદ', 'કાયદો', 'કાયદા અનુસાર',
        'ભારતીય ન્યાય સંહિતા', 'ભારતીય નાગરિક સુરક્ષા સંહિતા', 'ભારતીય સાક્ષ્ય અધિનિયમ',
        'સુપ્રીમ કોર્ટ', 'હાઈ કોર્ટ', 'ફેંસલો', 'કાયદાકીય પૂર્વનિર્ણય', 'રાજ્યબંધારણ',
        
        # Malayalam indicators
        'പ്രകാരം', 'കീഴിൽ', 'സെക്ഷൻ', 'അനുഛേദം', 'നിയമം', 'നിയമം പ്രകാരം',
        'ഭാരതീയ നീതി സംഹിത', 'ഭാരതീയ നാഗരിക സുരക്ഷാ സംഹിത', 'ഭാരതീയ സാക്ഷ്യ നിയമം',
        'സുപ്രീം കോടതി', 'ഹൈ കോടതി', 'വിധി', 'നിയമപരമായ മുൻനിർണയം', 'ഭരണഘടന',
        
        # Punjabi indicators
        'ਅਨੁਸਾਰ', 'ਹੇਠ', 'ਧਾਰਾ', 'ਅਨੁਛੇਦ', 'ਕਾਨੂੰਨ', 'ਕਾਨੂੰਨ ਅਨੁਸਾਰ',
        'ਭਾਰਤੀ ਨਿਆਂ ਸੰਹਿਤਾ', 'ਭਾਰਤੀ ਨਾਗਰਿਕ ਸੁਰੱਖਿਆ ਸੰਹਿਤਾ', 'ਭਾਰਤੀ ਸਾਕਸ਼ਯ ਐਕਟ',
        'ਸੁਪਰੀਮ ਕੋਰਟ', 'ਹਾਈ ਕੋਰਟ', 'ਫੈਸਲਾ', 'ਕਾਨੂੰਨੀ ਪੂਰਵ-ਨਿਰਣਾ', 'ਸੰਵਿਧਾਨ',
        
        # Kannada indicators
        'ಅನುಸಾರ', 'ಕೆಳಗೆ', 'ವಿಭಾಗ', 'ಲೇಖನ', 'ಕಾನೂನು', 'ಕಾನೂನು ಅನುಸಾರ',
        'ಭಾರತೀಯ ನ್ಯಾಯ ಸಂಹಿತೆ', 'ಭಾರತೀಯ ನಾಗರಿಕ ಸುರಕ್ಷಾ ಸಂಹಿತೆ', 'ಭಾರತೀಯ ಸಾಕ್ಷ್ಯ ಅಧಿನಿಯಮ',
        'ಸುಪ್ರೀಂ ಕೋರ್ಟ್', 'ಹೈ ಕೋರ್ಟ್', 'ತೀರ್ಪು', 'ಕಾನೂನುಬದ್ಧ ಮುನ್ನಡೆ', 'ಸಂವಿಧಾನ',
        
        # Odia indicators
        'ଅନୁସାରେ', 'ତଳେ', 'ଧାରା', 'ଅନୁଛେଦ', 'କାନୁନ', 'କାନୁନ ଅନୁସାରେ',
        'ଭାରତୀୟ ନ୍ୟାୟ ସଂହିତା', 'ଭାରତୀୟ ନାଗରିକ ସୁରକ୍ଷା ସଂହିତା', 'ଭାରତୀୟ ସାକ୍ଷ୍ୟ ଅଧିନିୟମ',
        'ସୁପ୍ରିମ କୋର୍ଟ', 'ହାଇ କୋର୍ଟ', 'ତିନିପୁ', 'କାନୁନିକ ପୂର୍ବନିର୍ଣ୍ଣୟ', 'ସମ୍ବିଧାନ'
    ]
    return any(indicator in text_lower for indicator in source_indicators)


def _add_source_attribution(text: str, language: str = 'en') -> str:
    """Add source attribution to legal answers."""
    if language.startswith('hi'):
        disclaimer = """

**स्रोत और अस्वीकरण:**
- यह जानकारी भारतीय कानूनी ढांचे के आधार पर है: भारतीय न्याय संहिता (BNS), 2023, भारतीय नागरिक सुरक्षा संहिता (BNSS), 2023, और भारतीय साक्ष्य अधिनियम (BSA), 2023
- यह सामान्य जानकारी है और विशिष्ट मामलों के लिए योग्य वकील से सलाह लें
- कानून जटिल हैं और मामले के अनुसार भिन्न हो सकते हैं"""
    else:
        disclaimer = """

**Source and Disclaimer:**
- This information is based on Indian legal framework: Bharatiya Nyaya Sanhita (BNS), 2023, Bharatiya Nagarik Suraksha Sanhita (BNSS), 2023, and Bharatiya Sakshya Adhiniyam (BSA), 2023
- This is general information only. For specific cases, consult a qualified lawyer
- Laws are complex and may vary by case and jurisdiction"""
    
    return text + disclaimer


def test_apply_policy_allows_definitions():
    model_out = 'An FIR is a First Information Report, a written document prepared by police when they receive information about a cognizable offence.'
    res = apply_policy(model_out, 'What is FIR?', language='en')
    assert 'FIR' in res and 'Report' in res

