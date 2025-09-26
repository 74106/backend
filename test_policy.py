import pytest
import sys
import os
# Add backend folder to sys.path so we can import policy module directly
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)



import policy

is_identity_question = policy.is_identity_question
is_legal_question = policy.is_legal_question
apply_policy = policy.apply_policy


def test_is_identity_question():
    assert is_identity_question("Who are you?")
    assert is_identity_question("what are you")
    assert not is_identity_question("How do I file an FIR?")

def test_is_identity_question_new():
    assert is_identity_question('Who are you?')
    assert is_identity_question('what are you')
    assert is_identity_question('Are you a bot?')
    assert not is_identity_question('How do I file a complaint?')


def test_is_legal_question():
    assert is_legal_question("How do I file an FIR for theft?")
    assert is_legal_question("What are my legal rights regarding eviction?")
    assert not is_legal_question("What's the weather?")
    assert not is_legal_question("Who are you?")

def test_is_legal_question_new():
    assert is_legal_question('How do I file an FIR?')
    assert is_legal_question('What are my rights if arrested?')
    assert not is_legal_question('What is the weather?')
    # identity-like short strings should not be considered legal
    assert not is_legal_question('Who are you')


def test_apply_policy_identity():
    ans = apply_policy("some model text", "Who are you?", language='en')
    assert ans == 'I am a legal chat bot'

def test_apply_policy_identity_new():
    res = apply_policy('some answer', 'Who are you?', language='en')
    assert res == 'I am a legal chat bot'


def test_apply_policy_non_legal_refuse():
    ans = apply_policy("I can tell you about weather", "What's the weather?", language='en')
    assert 'only provide legal' in ans or 'legal knowledge' in ans

def test_apply_policy_nonlegal_new():
    res = apply_policy('I like pizza', 'What is the weather today?', language='en')
    assert res == 'I can only provide legal knowledge. Please ask a legal question.'

def test_apply_policy_allows_definitions():
    model_out = 'An FIR is a First Information Report, a written document prepared by police when they receive information about a cognizable offence.'
    res = apply_policy(model_out, 'What is FIR?', language='en')
    assert 'FIR' in res and 'Report' in res

def test_apply_policy_sanitizes_identity_mentions():
    model_text = "I am ChatGPT and I can answer legal questions about court procedure."
    ans = apply_policy(model_text, "How do I appeal a conviction?", language='en')
    assert ans == 'I am a legal chat bot'

def test_apply_policy_sanitizes_identity_mentions_new():
    model_out = 'I am ChatGPT and can help with legal advice about criminal law.'
    res = apply_policy(model_out, 'How do I file a FIR?', language='en')
    # Should return fixed identity since model mentioned ChatGPT
    assert res == 'I am a legal chat bot'

def test_apply_policy_accepts_legal_answer():
    model_out = 'To file an FIR, go to the police station and provide details.'
    res = apply_policy(model_out, 'How do I file an FIR?', language='en')
    assert 'FIR' in res or 'police' in res or 'file' in res

