# NyaySetu Backend Setup Guide

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy `env_example.txt` to `.env` and update the values:

```bash
# Copy the example file
cp env_example.txt .env
```

**Required Configuration:**

#### Email Configuration (for user registration)
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
```

**For Gmail:**
1. Enable 2-factor authentication
2. Generate an App Password: Google Account → Security → App passwords
3. Use the App Password (not your regular password)

#### JWT Configuration
```env
JWT_SECRET=your-secure-secret-key-here
```

#### Gemini API Configuration
```env
GEMINI_API_KEY=your-gemini-api-key-here
```

**To get Gemini API Key:**
1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Copy the key to your `.env` file

### 3. Test Configuration
```bash
python test_setup.py
```

### 4. Start the Server
```bash
python app.py
```

The server will start on `http://localhost:5000`

## 📋 API Endpoints

### Authentication
- `POST /auth/register` - Register new user
- `GET /auth/verify?token=...` - Verify email
- `POST /auth/login` - Login user
- `POST /auth/logout` - Logout user
- `GET /auth/me` - Get current user info

### Legal Chat
- `POST /chat` - Ask legal questions (requires Bearer token)

### Forms
- `POST /generate_form` - Generate legal forms (requires Bearer token)

### Data
- `GET /data/chats` - Get chat history
- `GET /data/forms` - Get form history

## 🔧 Troubleshooting

### Common Issues

#### 1. "SMTP_USER or SMTP_PASS not configured"
- Make sure your `.env` file exists and has correct email credentials
- For Gmail, use App Password, not regular password

#### 2. "GEMINI_API_KEY not set"
- Add your Gemini API key to the `.env` file
- Get API key from Google AI Studio

#### 3. "JWT_SECRET not configured"
- Add a secure secret key to your `.env` file
- Use a long, random string

#### 4. Database errors
- The database will be created automatically
- Make sure the directory is writable

### Testing Individual Components

#### Test Email Configuration
```python
from utils.auth import send_verification_email
send_verification_email("test@example.com", "http://localhost:5000/auth/verify?token=test123")
```

#### Test Gemini API
```python
from app import call_gemini_api
result = call_gemini_api("What is the legal definition of contract?")
print(result)
```

#### Test Authentication
```python
from app import hash_password, verify_password
hashed = hash_password("test123")
print(verify_password("test123", hashed))  # Should return True
```

## 🛡️ Security Notes

1. **Never commit `.env` files** to version control
2. **Use strong JWT secrets** in production
3. **Enable HTTPS** in production
4. **Use App Passwords** for email, not regular passwords
5. **Rotate API keys** regularly

## 📝 Example Usage

### Register a User
```bash
curl -X POST http://localhost:5000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123"}'
```

### Login
```bash
curl -X POST http://localhost:5000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123"}'
```

### Ask Legal Question
```bash
curl -X POST http://localhost:5000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{"question": "What are my rights as a tenant?", "language": "en"}'
```

## 🔄 Development

### Running in Development Mode
```bash
export FLASK_ENV=development
python app.py
```

### Database Reset
```bash
rm nyaysetu.db
python app.py  # Database will be recreated
```

## 📞 Support

If you encounter issues:
1. Run `python test_setup.py` to diagnose problems
2. Check the logs for error messages
3. Verify all environment variables are set correctly
4. Ensure all dependencies are installed
