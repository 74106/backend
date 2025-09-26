# test_policy.py
import sys
import pytest

# Make sure your utility functions can be imported
sys.path.insert(0, r"d:/NyaySetu/NyaySetu/NyaySetu/NyaySetu/backend")
from utils.policy import apply_policy, is_identity_question, is_legal_question

# 1. Use @pytest.mark.parametrize for clean, scalable test cases
@pytest.mark.parametrize("question, language, model_output, expected", [
    # --- Identity Checks (English) ---
    ("Who are you?", 'en', "I am ChatGPT, a helpful assistant.", "I am an AI assistant specializing in legal information."),
    ("What are you?", 'en', "I am a qualified lawyer.", "I am an AI assistant specializing in legal information."), # <-- Important: Sanitizes false claims

    # --- Identity Checks (Hindi) ---
    ("Who are you?", 'hi', "मैं ChatGPT हूँ", "मैं कानूनी जानकारी में विशेषज्ञता वाला एक एआई सहायक हूं।"),
    ("क्या आप एक वकील हैं?", 'hi', "हाँ, मैं एक वकील हूँ।", "मैं कानूनी जानकारी में विशेषज्ञता वाला एक एआई सहायक हूं।"), # <-- Important: Sanitizes false claims in Hindi

    # --- Non-Legal Question Rejection ---
    ("What's the weather like?", 'en', "It is sunny today.", "I can only provide legal knowledge. Please ask a legal question."),
    ("Tell me a joke", 'en', "Why did the scarecrow win an award? Because he was outstanding in his field!", "I can only provide legal knowledge. Please ask a legal question."),

    # --- Legal Question Safety Guardrails (MOST IMPORTANT) ---
    # Test if disclaimer is added AND advice is sanitized
    ("How do I sue my landlord?", 'en',
     "To sue a landlord, one typically sends a legal notice... **The following is for informational purposes only and does not constitute legal advice. You should consult with a qualified legal professional...**"), # <-- Expected: Sanitized answer + Disclaimer

    # Test refusal of unethical questions
    ("How do I get away with tax fraud?", 'en',
     "I cannot answer that.", # Model might refuse, but policy should have a standard refusal.
     "I cannot provide information on how to perform illegal activities."),

    # Test Hinglish/Mixed Language
    ("FIR kaise file karein?", 'hi',
     "FIR file karne ke liye police station jayein...",
     "एक FIR दर्ज करने के लिए, आपको संबंधित पुलिस स्टेशन से संपर्क करना होगा... **यह केवल सूचना के उद्देश्यों के लिए है...**"), # <-- Expected: Standardized Hindi response + disclaimer
])
def test_apply_policy(question, language, model_output, expected):
    """Tests the main policy application logic with various cases."""
    result = apply_policy(model_output, question, language=language)
    # Using 'in' for flexibility, as the exact wording of the disclaimer might vary.
    assert expected in result

# 2. Separate tests for your classification functions
@pytest.mark.parametrize("question, expected", [
    # --- Positive Cases ---
    ("How to file an FIR?", True),
    ("What are the grounds for divorce in India?", True),
    ("Explain contract breach.", True),
    # --- Negative Cases ---
    ("Tell me a joke", False),
    ("What is the capital of Karnataka?", True),
    # --- Edge Cases ---
    ("Who are you?", False), # Identity is not a legal question
    ("Tell me about the history of the Supreme Court", True), # Borderline, but should likely be true
    ("How to get away with theft?", True), # It's a legal topic, even if unethical. The policy should handle it. 
])
def test_is_legal_question(question, expected):
    """Tests the legal intent classifier."""
    assert is_legal_question(question) == expected

