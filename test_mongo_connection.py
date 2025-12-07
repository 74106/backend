#!/usr/bin/env python3
"""Quick MongoDB connection test"""

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

print("Testing MongoDB connection...")
print("=" * 50)

try:
    client = MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=5000)
    result = client.admin.command('ping')
    
    if result.get('ok') == 1.0:
        print("✅ SUCCESS: MongoDB is running and accessible!")
        print()
        
        # Test database access
        db = client['nyaysetu']
        collections = db.list_collection_names()
        
        print(f"Database: nyaysetu")
        print(f"Collections found: {len(collections)}")
        if collections:
            for col in collections:
                count = db[col].count_documents({})
                print(f"  - {col}: {count} documents")
        else:
            print("  (No collections yet - will be created on first use)")
        
        print()
        print("✅ Your Flask app should be able to connect to MongoDB!")
        client.close()
    else:
        print("❌ MongoDB responded but ping failed")
        
except ServerSelectionTimeoutError:
    print("❌ FAILED: MongoDB connection timeout")
    print("   MongoDB is not running on localhost:27017")
    print()
    print("To start MongoDB:")
    print("  1. Run: start_mongodb.bat")
    print("  2. Or manually: \"C:\\Program Files\\MongoDB\\bin\\mongod.exe\" --dbpath \"C:\\data\\db\"")
    
except ConnectionFailure as e:
    print(f"❌ FAILED: Connection error - {e}")
    
except Exception as e:
    print(f"❌ FAILED: Unexpected error - {e}")

print("=" * 50)
