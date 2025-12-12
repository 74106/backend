import os
import json
import sqlite3
import time
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# Resolve database path. Defaults to a file next to the backend folder.
_DEFAULT_DB_PATH = os.environ.get(
    "NYAYSETU_DB_PATH",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "nyaysetu.db"),
)


def get_db_connection(db_path: str = _DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Return a SQLite connection with Row factory for dict-like access."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = _DEFAULT_DB_PATH) -> None:
    """Initialize database with required tables if they don't exist."""
    conn = get_db_connection(db_path)
    try:
        cur = conn.cursor()
        
        # Chats table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                language TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )
        
        # Forms table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS forms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                form_type TEXT NOT NULL,
                form_text TEXT NOT NULL,
                responses_json TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )
        
        # Users table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                is_verified INTEGER NOT NULL DEFAULT 0,
                verification_token TEXT,
                created_at TEXT NOT NULL,
                verified_at TEXT
            )
            """
        )
        
        # Lawyer profiles table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS lawyer_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE,
                phone TEXT UNIQUE,
                full_name TEXT NOT NULL,
                specialization TEXT,
                experience_years INTEGER,
                languages TEXT,
                location TEXT,
                bio TEXT,
                is_available INTEGER NOT NULL DEFAULT 0,
                status TEXT,
                cases_handled INTEGER DEFAULT 0,
                rating REAL DEFAULT 4.8,
                hourly_rate REAL,
                photo_url TEXT,
                video_link TEXT,
                availability TEXT,
                communication TEXT,
                consultation_modes TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        
        # Subscription purchases table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS subscription_purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subscription_id TEXT NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                tier_id TEXT NOT NULL,
                tier_name TEXT NOT NULL,
                price REAL NOT NULL,
                payment_reference TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        
        # Lawyer bookings table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS lawyer_bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_id TEXT NOT NULL UNIQUE,
                subscription_id INTEGER,
                tier_id TEXT NOT NULL,
                tier_name TEXT,
                price REAL NOT NULL,
                user_id INTEGER NOT NULL,
                preferred_lawyer_id INTEGER,
                customer_name TEXT,
                customer_phone TEXT,
                customer_email TEXT,
                issue_description TEXT,
                payment_reference TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                notes TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (subscription_id) REFERENCES subscription_purchases(id),
                FOREIGN KEY (preferred_lawyer_id) REFERENCES lawyer_profiles(id)
            )
            """
        )
        
        # Indexes
        cur.execute("CREATE INDEX IF NOT EXISTS idx_chats_timestamp ON chats(timestamp DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_forms_timestamp ON forms(timestamp DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_chats_language ON chats(language)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_forms_form_type ON forms(form_type)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_verified ON users(is_verified)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_lawyer_profiles_email ON lawyer_profiles(email)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_lawyer_profiles_phone ON lawyer_profiles(phone)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_subscription_purchases_subscription_id ON subscription_purchases(subscription_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_subscription_purchases_user_id ON subscription_purchases(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_subscription_purchases_status ON subscription_purchases(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_lawyer_bookings_booking_id ON lawyer_bookings(booking_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_lawyer_bookings_subscription_id ON lawyer_bookings(subscription_id)")
        
        conn.commit()
        logger.info("SQLite database initialized successfully")
    except Exception as e:
        logger.warning(f"Database initialization failed (non-fatal): {e}")
    finally:
        conn.close()


def insert_chat(
    question: str,
    answer: str,
    language: str,
    timestamp: str,
    db_path: str = _DEFAULT_DB_PATH,
) -> int:
    """Insert a chat record and return its new id."""
    conn = get_db_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO chats (question, answer, language, timestamp) VALUES (?, ?, ?, ?)",
            (question, answer, language, timestamp),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def insert_form(
    form_type: str,
    form_text: str,
    responses: Dict[str, Any],
    timestamp: str,
    db_path: str = _DEFAULT_DB_PATH,
) -> int:
    """Insert a form record and return its new id."""
    conn = get_db_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO forms (form_type, form_text, responses_json, timestamp) VALUES (?, ?, ?, ?)",
            (form_type, form_text, json.dumps(responses, ensure_ascii=False), timestamp),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def fetch_all_chats(db_path: str = _DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Fetch all chat records, newest first."""
    conn = get_db_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, question, answer, language, timestamp FROM chats ORDER BY timestamp DESC, id DESC")
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def fetch_all_forms(db_path: str = _DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Fetch all form records, newest first."""
    conn = get_db_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, form_type, form_text, responses_json, timestamp FROM forms ORDER BY timestamp DESC, id DESC")
        rows = cur.fetchall()
        result = []
        for row in rows:
            r = dict(row)
            # Parse responses_json for compatibility
            if "responses_json" in r:
                try:
                    r["responses"] = json.loads(r["responses_json"])
                except Exception:
                    r["responses"] = {}
            result.append(r)
        return result
    finally:
        conn.close()


def fetch_chats_filtered(
    start: Optional[str] = None,
    end: Optional[str] = None,
    language: Optional[str] = None,
    q: Optional[str] = None,
    db_path: str = _DEFAULT_DB_PATH,
) -> List[Dict[str, Any]]:
    """Fetch chats with optional filters: start/end ISO timestamp, language, text query."""
    conn = get_db_connection(db_path)
    try:
        conditions = []
        params: List[Any] = []
        if start:
            conditions.append("timestamp >= ?")
            params.append(start)
        if end:
            conditions.append("timestamp <= ?")
            params.append(end)
        if language:
            conditions.append("language = ?")
            params.append(language)
        if q:
            conditions.append("(question LIKE ? OR answer LIKE ?)")
            like = f"%{q}%"
            params.extend([like, like])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = (
            "SELECT id, question, answer, language, timestamp FROM chats "
            + where_clause
            + " ORDER BY timestamp DESC, id DESC"
        )
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def fetch_forms_filtered(
    start: Optional[str] = None,
    end: Optional[str] = None,
    form_type: Optional[str] = None,
    q: Optional[str] = None,
    db_path: str = _DEFAULT_DB_PATH,
) -> List[Dict[str, Any]]:
    """Fetch forms with optional filters: start/end ISO timestamp, form_type, text query."""
    conn = get_db_connection(db_path)
    try:
        conditions = []
        params: List[Any] = []
        if start:
            conditions.append("timestamp >= ?")
            params.append(start)
        if end:
            conditions.append("timestamp <= ?")
            params.append(end)
        if form_type:
            conditions.append("form_type = ?")
            params.append(form_type)
        if q:
            conditions.append("(form_text LIKE ? OR responses_json LIKE ?)")
            like = f"%{q}%"
            params.extend([like, like])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = (
            "SELECT id, form_type, form_text, responses_json, timestamp FROM forms "
            + where_clause
            + " ORDER BY timestamp DESC, id DESC"
        )
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        result = []
        for row in rows:
            r = dict(row)
            # Parse responses_json for compatibility
            if "responses_json" in r:
                try:
                    r["responses"] = json.loads(r["responses_json"])
                except Exception:
                    r["responses"] = {}
            result.append(r)
        return result
    finally:
        conn.close()


def fetch_recent_chats(
    limit: int = 5,
    db_path: str = _DEFAULT_DB_PATH,
) -> List[Dict[str, Any]]:
    """Fetch the latest chat records to showcase past resolved cases."""
    conn = get_db_connection(db_path)
    try:
        clamp_limit = max(1, min(int(limit or 5), 50))
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, question, answer, language, timestamp
            FROM chats
            ORDER BY timestamp DESC, id DESC
            LIMIT ?
            """,
            (clamp_limit,),
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# Users helpers
def create_user(
    email: str,
    password_hash: str,
    verification_token: Optional[str],
    created_at: str,
    db_path: str = _DEFAULT_DB_PATH,
) -> int:
    conn = get_db_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (email, password_hash, is_verified, verification_token, created_at) VALUES (?, ?, 0, ?, ?)",
            (email.lower(), password_hash, verification_token, created_at),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def get_user_by_email(email: str, db_path: str = _DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, email, password_hash, is_verified, verification_token, created_at, verified_at FROM users WHERE email = ?",
            (email.lower(),),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_verification_token(token: str, db_path: str = _DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, email, password_hash, is_verified, verification_token, created_at, verified_at FROM users WHERE verification_token = ?",
            (token,),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def set_user_verified(user_id: int, verified_at: str, db_path: str = _DEFAULT_DB_PATH) -> None:
    conn = get_db_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET is_verified = 1, verification_token = NULL, verified_at = ? WHERE id = ?",
            (verified_at, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def set_verification_token(user_id: int, token: str, db_path: str = _DEFAULT_DB_PATH) -> None:
    """Set or replace a user's verification token (used for resend flows)."""
    conn = get_db_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET verification_token = ?, is_verified = 0 WHERE id = ?",
            (token, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_json_dump(value: Any) -> str:
    return json.dumps(value or [], ensure_ascii=False)


def _serialize_lawyer_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Convert lawyer database row to dict format."""
    data = dict(doc)
    # Parse JSON fields
    for field in ("availability", "communication", "consultation_modes"):
        if field in data and data[field] and isinstance(data[field], str):
            try:
                data[field] = json.loads(data[field])
            except Exception:
                data[field] = []
        elif field not in data:
            data[field] = []
    return data


def get_lawyer_profile_by_id(lawyer_id: int, db_path: str = _DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM lawyer_profiles WHERE id = ?",
            (lawyer_id,),
        )
        row = cur.fetchone()
        if row:
            return _serialize_lawyer_doc(dict(row))
        return None
    finally:
        conn.close()


def list_lawyer_profiles(
    only_available: bool = False,
    limit: Optional[int] = None,
    db_path: str = _DEFAULT_DB_PATH,
) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    try:
        query = "SELECT * FROM lawyer_profiles"
        params = []
        if only_available:
            query += " WHERE is_available = 1"
        query += " ORDER BY is_available DESC, updated_at DESC"
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        
        cur = conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()
        return [_serialize_lawyer_doc(dict(row)) for row in rows]
    finally:
        conn.close()


def set_lawyer_availability(
    lawyer_id: int,
    *,
    is_available: Optional[bool] = None,
    status: Optional[str] = None,
    db_path: str = _DEFAULT_DB_PATH,
) -> None:
    conn = get_db_connection(db_path)
    try:
        updates = []
        params = []
        if is_available is not None:
            updates.append("is_available = ?")
            params.append(1 if is_available else 0)
        if status:
            updates.append("status = ?")
            params.append(status)
        if updates:
            updates.append("updated_at = ?")
            params.append(_now_iso())
            params.append(lawyer_id)
            cur = conn.cursor()
            cur.execute(
                f"UPDATE lawyer_profiles SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            conn.commit()
    finally:
        conn.close()


def create_subscription_purchase(
    purchase: Dict[str, Any],
    db_path: str = _DEFAULT_DB_PATH,
) -> Dict[str, Any]:
    """Create a new subscription purchase and return it."""
    conn = get_db_connection(db_path)
    try:
        now = _now_iso()
        subscription_id = f"SUB_{int(time.time())}_{secrets.token_hex(4)}"
        
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO subscription_purchases 
            (subscription_id, user_id, tier_id, tier_name, price, payment_reference, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                subscription_id,
                purchase["user_id"],
                purchase["tier_id"],
                purchase["tier_name"],
                purchase["price"],
                purchase["payment_reference"],
                purchase.get("status", "active"),
                now,
            ),
        )
        conn.commit()
        purchase_id = int(cur.lastrowid)
        
        return {
            "id": purchase_id,
            "subscription_id": subscription_id,
            "user_id": purchase["user_id"],
            "tier_id": purchase["tier_id"],
            "tier_name": purchase["tier_name"],
            "price": purchase["price"],
            "payment_reference": purchase["payment_reference"],
            "status": purchase.get("status", "active"),
            "created_at": now,
        }
    finally:
        conn.close()


def get_subscription_purchase(
    subscription_id: int,
    db_path: str = _DEFAULT_DB_PATH,
) -> Optional[Dict[str, Any]]:
    """Get a subscription purchase by its database id."""
    conn = get_db_connection(db_path)
    try:
        cur = conn.cursor()
        # Try to find by id first (if it's an integer)
        if isinstance(subscription_id, int):
            cur.execute(
                "SELECT * FROM subscription_purchases WHERE id = ?",
                (subscription_id,),
            )
            row = cur.fetchone()
            if row:
                return dict(row)
        
        # Try to find by subscription_id string
        cur.execute(
            "SELECT * FROM subscription_purchases WHERE subscription_id = ?",
            (str(subscription_id),),
        )
        row = cur.fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


def get_user_subscriptions(
    user_id: int,
    status: Optional[str] = "active",
    db_path: str = _DEFAULT_DB_PATH,
) -> List[Dict[str, Any]]:
    """Get all subscriptions for a user, optionally filtered by status."""
    conn = get_db_connection(db_path)
    try:
        query = "SELECT * FROM subscription_purchases WHERE user_id = ?"
        params = [user_id]
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"
        
        cur = conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def insert_lawyer_booking(
    booking: Dict[str, Any],
    db_path: str = _DEFAULT_DB_PATH,
) -> Dict[str, Any]:
    conn = get_db_connection(db_path)
    try:
        now = _now_iso()
        
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO lawyer_bookings 
            (booking_id, tier_id, tier_name, price, user_id, preferred_lawyer_id, 
             customer_name, customer_phone, customer_email, issue_description, 
             payment_reference, subscription_id, status, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                booking["booking_id"],
                booking["tier_id"],
                booking.get("tier_name"),
                booking["price"],
                booking.get("user_id"),
                booking.get("preferred_lawyer_id"),
                booking.get("customer_name"),
                booking.get("customer_phone"),
                booking.get("customer_email"),
                booking.get("issue_description"),
                booking.get("payment_reference"),
                booking.get("subscription_id"),
                booking.get("status", "pending"),
                booking.get("notes"),
                now,
            ),
        )
        conn.commit()
        
        return {
            "booking_id": booking["booking_id"],
            "tier_id": booking["tier_id"],
            "status": booking.get("status", "pending"),
            "created_at": now,
        }
    finally:
        conn.close()
