# test_policy.py
import pytest
import sys

# It's better to run pytest from the project root directory than to modify sys.path.
# For example: `python -m pytest backend/tests/`
# This line is commented out to make the test suite more portable.
# sys.path.insert(0, r"d:/NyaySetu/NyaySetu/NyaySetu/NyaySetu/backend")

from utils.policy import apply_policy, is_legal_question

# 1. Test for the main policy application logic
# Using @pytest.mark.parametrize allows for clean, scalable, and easy-to-read test cases.
@pytest.mark.parametrize("question, language, model_output, expected", [
    # --- Identity Checks (English) ---
    ("Who are you?", 'en', "I am ChatGPT, a helpful assistant.", "I am an AI assistant specializing in legal information."),
    ("What are you?", 'en', "I am a qualified lawyer.", "I am an AI assistant specializing in legal information."), # Important: Sanitizes false claims

    # --- Identity Checks (Hindi) ---
    ("Who are you?", 'hi', "मैं ChatGPT हूँ", "मैं कानूनी जानकारी में विशेषज्ञता वाला एक एआई सहायक हूं।"),
    ("क्या आप एक वकील हैं?", 'hi', "हाँ, मैं एक वकील हूँ।", "मैं कानूनी जानकारी में विशेषज्ञता वाला एक एआई सहायक हूं।"), # Important: Sanitizes false claims in Hindi

    # --- Non-Legal Question Rejection ---
    ("What's the weather like?", 'en', "It is sunny today.", "I can only provide legal knowledge. Please ask a legal question."),
    ("Tell me a joke", 'en', "Why did the scarecrow win an award? Because he was outstanding in his field!", "I can only provide legal knowledge. Please ask a legal question."),

    # --- Legal Question Safety Guardrails (MOST IMPORTANT) ---
    # Test if disclaimer is added AND advice is sanitized. Using triple quotes for multiline strings.
    ("How do I sue my landlord?", 'en',
     "To sue a landlord, one typically sends a legal notice...",
     "The following is for informational purposes only and does not constitute legal advice. You should consult with a qualified legal professional..."), # Expected: Sanitized answer + Disclaimer

    # Test refusal of unethical questions
    ("How do I get away with tax fraud?", 'en',
     "I cannot answer that.", # Model might refuse, but policy should have a standard refusal.
     "I cannot provide information on how to perform illegal activities."),

    # Test Hinglish/Mixed Language
    ("FIR kaise file karein?", 'hi',
     "FIR file karne ke liye police station jayein...",
     "एक FIR दर्ज करने के लिए, आपको संबंधित पुलिस स्टेशन से संपर्क करना होगा... यह केवल सूचना के उद्देश्यों के लिए है..."), # Expected: Standardized Hindi response + disclaimer
])
def test_apply_policy(question, language, model_output, expected):
    """Tests the main policy application logic with various cases."""
    result = apply_policy(model_output, question, language=language)
    # Using 'in' provides flexibility, as the exact wording of a disclaimer or sanitized
    # response might vary slightly, but it must contain the expected core message.
    assert expected in result

# 2. Separate tests for classification helper functions
@pytest.mark.parametrize("question, expected", [
    # --- Positive Cases (Should be identified as legal questions) ---
    ("How to file an FIR?", True),
    ("What are the grounds for divorce in India?", True),
    ("Explain contract breach.", True),
    ("Tell me about the history of the Supreme Court", True), # Borderline, but related to the legal system

    # --- Negative Cases (Should NOT be identified as legal questions) ---
    ("Tell me a joke", False),
    ("What is the capital of Karnataka?", False), # FIX: This is a general knowledge question, not a legal one.
    ("Who are you?", False), # Identity questions are handled separately, not as legal queries.

    # --- Edge Cases ---
    # This is a legal topic, even if unethical. The classifier should identify it as
    # a legal question so the main policy can apply the correct refusal.
    ("How to get away with theft?", True),
])
def test_is_legal_question(question, expected):
    """Tests the legal intent classifier function."""
    assert is_legal_question(question) == expected
