@echo off
title NyaySetu AI Setup
color 0A

echo.
echo ========================================
echo    NyaySetu AI Models Setup
echo ========================================
echo.
echo This script will help you set up free AI models for NyaySetu.
echo.
echo Available options:
echo 1. Google Gemini (Recommended - No credit card required)
echo.

echo ========================================
echo    Google Gemini Setup
echo ========================================
echo.
echo To get your Gemini API key:
echo 1. Visit: https://makersuite.google.com/app/apikey
echo 2. Sign in with your Google account
echo 3. Click "Create API Key"
echo 4. Copy the API key (starts with "AIza...")
echo.

echo Enter your Google Gemini API Key (or press Enter to skip):
set /p GEMINI_KEY=
if not "%GEMINI_KEY%"=="" (
    setx GEMINI_API_KEY "AIzaSyDV0SNPq0XuX_ySF2fPvC50kanqxnpQgck"
    echo ✅ Gemini API Key set successfully!
) else (
    echo ⏭️  Skipping Gemini setup
)

echo.
echo.
echo ========================================
echo    Setup Complete!
echo ========================================
echo.
echo Environment variables have been set.
echo.
echo To test your setup:
echo 1. Restart your terminal/command prompt
echo 2. Run: python app.py
echo 3. Test the chat functionality
echo.
echo The system will use Google Gemini when configured, else fallback to local model.
echo.
echo For more information, see: README_FREE_AI_SETUP.md
echo.
pause
