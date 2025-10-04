#!/usr/bin/env python3
"""
Test script to verify the NyaySetu backend setup.
Run this after setting up your .env file to test the configuration.
"""

import os
import sys
from dotenv import load_dotenv

def test_env_config():
    """Test if environment variables are properly configured."""
    print("🔍 Testing environment configuration...")
    
    # Load environment variables
    load_dotenv()
    
    required_vars = {
        'SMTP_USER': 'Email configuration',
        'SMTP_PASS': 'Email configuration', 
        'JWT_SECRET': 'JWT configuration',
        'GEMINI_API_KEY': 'Gemini API configuration'
    }
    
    missing_vars = []
    for var, description in required_vars.items():
        value = os.environ.get(var)
        if not value or value.startswith('your-') or value == 'your-secret-key-here-change-this-in-production':
            missing_vars.append(f"{var} ({description})")
        else:
            print(f"✅ {var}: {'*' * min(len(value), 10)}...")
    
    if missing_vars:
        print(f"\n❌ Missing or invalid configuration:")
        for var in missing_vars:
            print(f"   - {var}")
        print(f"\n📝 Please update your .env file with proper values.")
        return False
    
    print("✅ All environment variables are configured!")
    return True

def test_gemini_api():
    """Test Gemini API connectivity."""
    print("\n🤖 Testing Gemini API...")
    
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        print("❌ GEMINI_API_KEY not found")
        return False
    
    try:
        import requests
        
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": "Hello, this is a test message. Please respond with 'API working correctly'."}]}],
            "generationConfig": {
                "temperature": 0.7,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 1024,
            }
        }
        
        response = requests.post(f"{url}?key={api_key}", headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        if 'candidates' in data and len(data['candidates']) > 0:
            print("✅ Gemini API is working correctly!")
            return True
        else:
            print("❌ Unexpected response format from Gemini API")
            return False
            
    except ImportError:
        print("❌ 'requests' library not installed. Run: pip install requests")
        return False
    except Exception as e:
        print(f"❌ Gemini API test failed: {e}")
        return False

def test_database():
    """Test database initialization."""
    print("\n🗄️ Testing database...")
    
    try:
        from utils.db import init_db, get_db_connection
        
        # Initialize database
        init_db()
        
        # Test connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        conn.close()
        
        table_names = [table[0] for table in tables]
        expected_tables = ['chats', 'forms', 'users']
        
        if all(table in table_names for table in expected_tables):
            print("✅ Database tables created successfully!")
            return True
        else:
            print(f"❌ Missing tables. Found: {table_names}, Expected: {expected_tables}")
            return False
            
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def test_auth_functions():
    """Test authentication functions."""
    print("\n🔐 Testing authentication functions...")
    
    try:
        from utils.auth import send_verification_email
        from app import hash_password, verify_password, create_jwt, decode_jwt
        
        # Test password hashing
        test_password = "test123"
        hashed = hash_password(test_password)
        if verify_password(test_password, hashed):
            print("✅ Password hashing/verification working!")
        else:
            print("❌ Password verification failed")
            return False
        
        # Test JWT creation/decoding
        test_payload = {'user_id': 1, 'email': 'test@example.com'}
        token = create_jwt(test_payload, expires_minutes=60)
        decoded = decode_jwt(token)
        
        if decoded and decoded['user_id'] == test_payload['user_id']:
            print("✅ JWT creation/decoding working!")
        else:
            print("❌ JWT verification failed")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Authentication test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 NyaySetu Backend Configuration Test\n")
    
    tests = [
        test_env_config,
        test_database, 
        test_auth_functions,
        test_gemini_api
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Your backend is ready to run.")
        print("\n📋 Next steps:")
        print("1. Start the server: python app.py")
        print("2. Test registration: POST /auth/register")
        print("3. Test login: POST /auth/login")
        print("4. Test chat: POST /chat (with Bearer token)")
    else:
        print("⚠️ Some tests failed. Please fix the issues above before running the server.")
        sys.exit(1)

if __name__ == "__main__":
    main()
