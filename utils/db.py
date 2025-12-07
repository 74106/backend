import os
import json
import time
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
import logging

logger = logging.getLogger(__name__)

# MongoDB connection configuration
MONGO_URI = os.environ.get(
    "MONGODB_URI",
    os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
)
MONGO_DB_NAME = os.environ.get("MONGODB_DB_NAME", "nyaysetu")

_client = None
_db = None


def get_mongo_client():
    """Get or create MongoDB client connection. Returns None if connection fails."""
    global _client
    if _client is None:
        try:
            _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            # Test connection
            _client.admin.command('ping')
            logger.info(f"Connected to MongoDB at {MONGO_URI}")
        except Exception as e:
            logger.warning(f"MongoDB connection failed: {e}. The app will continue but database operations will fail.")
            logger.info("To fix: Install MongoDB locally or set MONGODB_URI environment variable to a MongoDB connection string.")
            _client = None
    return _client


def get_db():
    """Get MongoDB database instance. Returns None if connection is not available."""
    global _db
    if _db is None:
        client = get_mongo_client()
        if client is None:
            return None
        _db = client[MONGO_DB_NAME]
    return _db


def init_db() -> None:
    """Initialize MongoDB database with required collections and indexes.
    Does not raise exceptions - logs warnings if MongoDB is unavailable."""
    try:
        db = get_db()
        if db is None:
            logger.warning("MongoDB is not available. Database operations will fail until MongoDB is connected.")
            logger.info("To connect MongoDB:")
            logger.info("  1. Install MongoDB locally: https://www.mongodb.com/try/download/community")
            logger.info("  2. Or use MongoDB Atlas (cloud): https://www.mongodb.com/cloud/atlas")
            logger.info("  3. Set MONGODB_URI environment variable: export MONGODB_URI='mongodb://localhost:27017/'")
            return
        
        # Create collections (MongoDB creates them automatically on first insert)
        collections = [
            'chats', 'forms', 'users', 'lawyer_profiles', 
            'subscription_purchases', 'lawyer_bookings'
        ]
        
        for collection_name in collections:
            if collection_name not in db.list_collection_names():
                db.create_collection(collection_name)
                logger.info(f"Created collection: {collection_name}")
        
        # Create indexes
        try:
            db.users.create_index("email", unique=True)
            db.users.create_index("is_verified")
            db.lawyer_profiles.create_index("email", unique=True, sparse=True)
            db.lawyer_profiles.create_index("phone", unique=True, sparse=True)
            db.subscription_purchases.create_index("subscription_id", unique=True)
            db.subscription_purchases.create_index("user_id")
            db.subscription_purchases.create_index("status")
            db.lawyer_bookings.create_index("booking_id", unique=True)
            db.lawyer_bookings.create_index("subscription_id")
            db.chats.create_index("timestamp")
            db.forms.create_index("timestamp")
        except Exception as idx_err:
            logger.warning(f"Some indexes may already exist: {idx_err}")
        
        logger.info("MongoDB database initialized successfully")
    except Exception as e:
        logger.warning(f"MongoDB initialization failed (non-fatal): {e}")
        logger.info("The app will continue but database operations will fail until MongoDB is available.")


def insert_chat(
    question: str,
    answer: str,
    language: str,
    timestamp: str,
) -> str:
    """Insert a chat record and return its new id."""
    db = get_db()
    if db is None:
        logger.warning("MongoDB not available - chat not saved")
        return "0"
    chat_doc = {
        "question": question,
        "answer": answer,
        "language": language,
        "timestamp": timestamp
    }
    result = db.chats.insert_one(chat_doc)
    return str(result.inserted_id)


def insert_form(
    form_type: str,
    form_text: str,
    responses: Dict[str, Any],
    timestamp: str,
) -> str:
    """Insert a form record and return its new id."""
    db = get_db()
    if db is None:
        logger.warning("MongoDB not available - form not saved")
        return "0"
    form_doc = {
        "form_type": form_type,
        "form_text": form_text,
        "responses": responses,  # MongoDB stores dicts natively
        "timestamp": timestamp
    }
    result = db.forms.insert_one(form_doc)
    return str(result.inserted_id)


def fetch_all_chats() -> List[Dict[str, Any]]:
    """Fetch all chat records, newest first."""
    db = get_db()
    if db is None:
        return []
    chats = db.chats.find().sort("timestamp", -1)
    result = []
    for chat in chats:
        chat["id"] = str(chat["_id"])
        del chat["_id"]
        result.append(chat)
    return result


def fetch_all_forms() -> List[Dict[str, Any]]:
    """Fetch all form records, newest first."""
    db = get_db()
    if db is None:
        return []
    forms = db.forms.find().sort("timestamp", -1)
    result = []
    for form in forms:
        form["id"] = str(form["_id"])
        del form["_id"]
        # Convert responses dict back to JSON string for compatibility
        if "responses" in form and isinstance(form["responses"], dict):
            form["responses_json"] = json.dumps(form["responses"], ensure_ascii=False)
        result.append(form)
    return result


def fetch_chats_filtered(
    start: Optional[str] = None,
    end: Optional[str] = None,
    language: Optional[str] = None,
    q: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Fetch chats with optional filters: start/end ISO timestamp, language, text query.
    
    NOTE: This function is kept for compatibility but should NOT be used for similar_cases.
    The similar_cases endpoint should use external sources (RSS feeds) instead of MongoDB data.
    """
    db = get_db()
    if db is None:
        return []
    query = {}
    
    if start:
        query["timestamp"] = {"$gte": start}
    if end:
        if "timestamp" in query:
            query["timestamp"]["$lte"] = end
        else:
            query["timestamp"] = {"$lte": end}
    if language:
        query["language"] = language
    if q:
        query["$or"] = [
            {"question": {"$regex": q, "$options": "i"}},
            {"answer": {"$regex": q, "$options": "i"}}
        ]
    
    chats = db.chats.find(query).sort("timestamp", -1)
    result = []
    for chat in chats:
        chat["id"] = str(chat["_id"])
        del chat["_id"]
        result.append(chat)
    return result


def fetch_forms_filtered(
    start: Optional[str] = None,
    end: Optional[str] = None,
    form_type: Optional[str] = None,
    q: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Fetch forms with optional filters: start/end ISO timestamp, form_type, text query."""
    db = get_db()
    if db is None:
        return []
    query = {}
    
    if start:
        query["timestamp"] = {"$gte": start}
    if end:
        if "timestamp" in query:
            query["timestamp"]["$lte"] = end
        else:
            query["timestamp"] = {"$lte": end}
    if form_type:
        query["form_type"] = form_type
    if q:
        query["$or"] = [
            {"form_text": {"$regex": q, "$options": "i"}},
            {"responses": {"$regex": q, "$options": "i"}}
        ]
    
    forms = db.forms.find(query).sort("timestamp", -1)
    result = []
    for form in forms:
        form["id"] = str(form["_id"])
        del form["_id"]
        # Convert responses dict back to JSON string for compatibility
        if "responses" in form and isinstance(form["responses"], dict):
            form["responses_json"] = json.dumps(form["responses"], ensure_ascii=False)
        result.append(form)
    return result


def fetch_recent_chats(
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Fetch the latest chat records to showcase past resolved cases."""
    db = get_db()
    if db is None:
        return []
    chats = db.chats.find().sort("timestamp", -1).limit(min(max(1, limit), 50))
    result = []
    for chat in chats:
        chat["id"] = str(chat["_id"])
        del chat["_id"]
        result.append(chat)
    return result


# Users helpers
def create_user(
    email: str,
    password_hash: str,
    verification_token: Optional[str],
    created_at: str,
) -> str:
    db = get_db()
    if db is None:
        raise RuntimeError("MongoDB is not available. Please configure MONGODB_URI environment variable.")
    user_doc = {
        "email": email.lower(),
        "password_hash": password_hash,
        "is_verified": 0,
        "verification_token": verification_token,
        "created_at": created_at,
        "verified_at": None
    }
    result = db.users.insert_one(user_doc)
    return str(result.inserted_id)


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    if db is None:
        return None
    user = db.users.find_one({"email": email.lower()})
    if user:
        user["id"] = str(user["_id"])
        del user["_id"]
        return user
    return None


def get_user_by_verification_token(token: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    if db is None:
        return None
    user = db.users.find_one({"verification_token": token})
    if user:
        user["id"] = str(user["_id"])
        del user["_id"]
        return user
    return None


def set_user_verified(user_id: str, verified_at: str) -> None:
    db = get_db()
    if db is None:
        logger.warning("MongoDB not available - user verification not saved")
        return
    from bson import ObjectId
    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "is_verified": 1,
            "verification_token": None,
            "verified_at": verified_at
        }}
    )


def set_verification_token(user_id: str, token: str) -> None:
    """Set or replace a user's verification token (used for resend flows)."""
    db = get_db()
    if db is None:
        logger.warning("MongoDB not available - verification token not saved")
        return
    from bson import ObjectId
    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "verification_token": token,
            "is_verified": 0
        }}
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_json_dump(value: Any) -> str:
    return json.dumps(value or [], ensure_ascii=False)


def get_lawyer_profile_by_id(lawyer_id: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    if db is None:
        return None
    from bson import ObjectId
    try:
        lawyer = db.lawyer_profiles.find_one({"_id": ObjectId(lawyer_id)})
        if lawyer:
            lawyer["id"] = str(lawyer["_id"])
            del lawyer["_id"]
            return _serialize_lawyer_doc(lawyer)
        return None
    except Exception:
        return None


def _serialize_lawyer_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Convert MongoDB document to dict format compatible with old SQLite format."""
    data = dict(doc)
    # MongoDB stores lists/dicts natively, so we don't need to parse JSON
    # But we ensure these fields exist
    for field in ("availability", "communication", "consultation_modes"):
        if field not in data:
            data[field] = []
    return data


def create_subscription_purchase(
    purchase: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a new subscription purchase and return it."""
    db = get_db()
    if db is None:
        raise RuntimeError("MongoDB is not available. Please configure MONGODB_URI environment variable.")
    now = _now_iso()
    subscription_id = f"SUB_{int(time.time())}_{secrets.token_hex(4)}"
    
    purchase_doc = {
        "subscription_id": subscription_id,
        "user_id": purchase["user_id"],
        "tier_id": purchase["tier_id"],
        "tier_name": purchase["tier_name"],
        "price": purchase["price"],
        "payment_reference": purchase["payment_reference"],
        "status": purchase.get("status", "active"),
        "created_at": now
    }
    
    result = db.subscription_purchases.insert_one(purchase_doc)
    
    return {
        "id": str(result.inserted_id),
        "subscription_id": subscription_id,
        "user_id": purchase["user_id"],
        "tier_id": purchase["tier_id"],
        "tier_name": purchase["tier_name"],
        "price": purchase["price"],
        "payment_reference": purchase["payment_reference"],
        "status": purchase.get("status", "active"),
        "created_at": now,
    }


def get_subscription_purchase(
    subscription_id: int,
) -> Optional[Dict[str, Any]]:
    """Get a subscription purchase by its database id (MongoDB ObjectId as string or int)."""
    db = get_db()
    if db is None:
        return None
    from bson import ObjectId
    try:
        # Try to convert to ObjectId if it's a string, otherwise use as int
        if isinstance(subscription_id, str):
            try:
                obj_id = ObjectId(subscription_id)
                purchase = db.subscription_purchases.find_one({"_id": obj_id})
            except Exception:
                # If not a valid ObjectId, try to find by subscription_id field
                purchase = db.subscription_purchases.find_one({"subscription_id": subscription_id})
        else:
            # If it's an int, try to find by _id (ObjectId) or by subscription_id field
            try:
                obj_id = ObjectId(str(subscription_id))
                purchase = db.subscription_purchases.find_one({"_id": obj_id})
            except Exception:
                # If conversion fails, try finding by subscription_id field
                purchase = db.subscription_purchases.find_one({"subscription_id": str(subscription_id)})
        
        if purchase:
            purchase["id"] = str(purchase["_id"])
            del purchase["_id"]
            return purchase
        return None
    except Exception:
        return None


def get_user_subscriptions(
    user_id: int,
    status: Optional[str] = "active",
) -> List[Dict[str, Any]]:
    """Get all subscriptions for a user, optionally filtered by status."""
    db = get_db()
    if db is None:
        return []
    # MongoDB stores user_id as int, so we can query directly
    query = {"user_id": int(user_id)}
    if status:
        query["status"] = status
    
    subscriptions = db.subscription_purchases.find(query).sort("created_at", -1)
    result = []
    for sub in subscriptions:
        sub["id"] = str(sub["_id"])
        del sub["_id"]
        result.append(sub)
    return result


def list_lawyer_profiles(
    only_available: bool = False,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    db = get_db()
    if db is None:
        return []
    query = {}
    if only_available:
        query["is_available"] = 1
    
    cursor = db.lawyer_profiles.find(query).sort([("is_available", -1), ("updated_at", -1)])
    if limit:
        cursor = cursor.limit(limit)
    
    result = []
    for lawyer in cursor:
        lawyer["id"] = str(lawyer["_id"])
        del lawyer["_id"]
        result.append(_serialize_lawyer_doc(lawyer))
    return result


def set_lawyer_availability(
    lawyer_id: str,
    *,
    is_available: Optional[bool] = None,
    status: Optional[str] = None,
) -> None:
    db = get_db()
    if db is None:
        logger.warning("MongoDB not available - lawyer availability not updated")
        return
    from bson import ObjectId
    updates = {}
    if is_available is not None:
        updates["is_available"] = 1 if is_available else 0
    if status:
        updates["status"] = status
    if updates:
        updates["updated_at"] = _now_iso()
        db.lawyer_profiles.update_one(
            {"_id": ObjectId(lawyer_id)},
            {"$set": updates}
        )


def insert_lawyer_booking(
    booking: Dict[str, Any],
) -> Dict[str, Any]:
    db = get_db()
    if db is None:
        raise RuntimeError("MongoDB is not available. Please configure MONGODB_URI environment variable.")
    now = _now_iso()
    
    booking_doc = {
        "booking_id": booking["booking_id"],
        "tier_id": booking["tier_id"],
        "tier_name": booking.get("tier_name"),
        "price": booking["price"],
        "user_id": booking.get("user_id"),
        "preferred_lawyer_id": booking.get("preferred_lawyer_id"),
        "customer_name": booking.get("customer_name"),
        "customer_phone": booking.get("customer_phone"),
        "customer_email": booking.get("customer_email"),
        "issue_description": booking.get("issue_description"),
        "payment_reference": booking.get("payment_reference"),
        "subscription_id": booking.get("subscription_id"),
        "status": booking.get("status", "pending"),
        "notes": booking.get("notes"),
        "created_at": now
    }
    
    result = db.lawyer_bookings.insert_one(booking_doc)
    
    return {
        "booking_id": booking["booking_id"],
        "tier_id": booking["tier_id"],
        "status": booking.get("status", "pending"),
        "created_at": now,
    }
