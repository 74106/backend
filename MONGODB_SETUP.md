# MongoDB Setup Guide

## Quick Setup Options

### Option 1: MongoDB Atlas (Cloud - Recommended for Production)

1. Go to https://www.mongodb.com/cloud/atlas
2. Create a free account
3. Create a free cluster
4. Get your connection string (looks like: `mongodb+srv://username:password@cluster.mongodb.net/`)
5. Set environment variable:
   ```bash
   export MONGODB_URI="mongodb+srv://username:password@cluster.mongodb.net/"
   export MONGODB_DB_NAME="nyaysetu"
   ```

### Option 2: Local MongoDB Installation

#### Windows:
1. Download MongoDB Community Server from: https://www.mongodb.com/try/download/community
2. Install MongoDB
3. Start MongoDB service:
   ```powershell
   # MongoDB usually starts automatically, but if not:
   net start MongoDB
   ```
4. Default connection: `mongodb://localhost:27017/`
5. Set environment variable (optional, this is the default):
   ```powershell
   $env:MONGODB_URI="mongodb://localhost:27017/"
   $env:MONGODB_DB_NAME="nyaysetu"
   ```

#### Linux/Mac:
1. Install MongoDB:
   ```bash
   # Ubuntu/Debian
   sudo apt-get install mongodb
   
   # Mac (using Homebrew)
   brew tap mongodb/brew
   brew install mongodb-community
   ```
2. Start MongoDB:
   ```bash
   # Ubuntu/Debian
   sudo systemctl start mongodb
   
   # Mac
   brew services start mongodb-community
   ```
3. Set environment variable (optional):
   ```bash
   export MONGODB_URI="mongodb://localhost:27017/"
   export MONGODB_DB_NAME="nyaysetu"
   ```

### Option 3: Docker (Quick Setup)

```bash
docker run -d -p 27017:27017 --name mongodb mongo:latest
```

This starts MongoDB on `mongodb://localhost:27017/`

## Environment Variables

Create a `.env` file in the `backend` directory:

```env
MONGODB_URI=mongodb://localhost:27017/
MONGODB_DB_NAME=nyaysetu
```

Or set them in your system environment.

## Current Status

The application will:
- ✅ Start successfully even if MongoDB is not available
- ✅ Log warnings when MongoDB operations fail
- ✅ Continue to work for non-database operations (chat, legal advice, etc.)
- ❌ Database operations (user registration, chat history, forms) will fail until MongoDB is connected

## Testing Connection

Once MongoDB is set up, restart the Flask app. You should see:
```
INFO:utils.db:Connected to MongoDB at mongodb://localhost:27017/
INFO:utils.db:MongoDB database initialized successfully
```

If you see warnings instead, check:
1. MongoDB is running
2. Connection string is correct
3. Network/firewall allows connection
4. MongoDB credentials are correct (for Atlas)

