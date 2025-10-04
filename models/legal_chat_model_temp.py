def get_intelligent_legal_response(question: str, language: str = 'en') -> str:
    """Provide intelligent legal responses based on question analysis"""
    question_lower = question.lower()
    
    # Multilingual keyword matching for FIR/police issues
    fir_keywords = [
        # English
        'fir', 'police', 'complaint', 'crime', 'criminal', 'arrest', 'bail', 'court',
        # Hindi
        'एफआईआर', 'पुलिस', 'शिकायत', 'अपराध', 'अपराधी', 'गिरफ्तार', 'जमानत', 'अदालत', 'कानूनी',
        # Bengali
        'এফআইআর', 'পুলিশ', 'অভিযোগ', 'অপরাধ', 'অপরাধী', 'গ্রেফতার', 'জামিন', 'আদালত', 'আইনি',
        # Tamil
        'எஃப்ஐஆர்', 'காவல்துறை', 'புகார்', 'குற்றம்', 'குற்றவாளி', 'கைது', 'ஜாமீன்', 'நீதிமன்றம்', 'சட்ட',
        # Telugu
        'ఎఫ్ఐఆర్', 'పోలీసు', 'ఫిర్యాదు', 'నేరం', 'నేరస్థుడు', 'అరెస్టు', 'జామీను', 'కోర్టు', 'చట్టపరమైన',
        # Marathi
        'एफआयआर', 'पोलिस', 'तक्रार', 'गुन्हा', 'गुन्हेगार', 'अटक', 'जामीन', 'न्यायालय', 'कायदेशीर',
        # Gujarati
        'એફઆઈઆર', 'પોલીસ', 'ફરિયાદ', 'ગુનો', 'ગુનેગાર', 'અટકાવ', 'જામીન', 'કોર્ટ', 'કાયદાકીય',
        # Malayalam
        'എഫ്ഐആർ', 'പോലീസ്', 'പരാതി', 'കുറ്റം', 'കുറ്റവാളി', 'അറസ്റ്റ്', 'ജാമ്യം', 'കോടതി', 'നിയമപരമായ',
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