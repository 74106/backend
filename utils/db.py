import os
import json
import sqlite3
import time
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

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
    import logging
    logger = logging.getLogger(__name__)
    
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
        # Indexes for users - wrap in try/except to handle schema mismatches
        try:
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)
                """
            )
        except Exception as e:
            logger.debug(f"Index idx_users_email may already exist or table schema mismatch: {e}")
        try:
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_users_verified ON users(is_verified)
                """
            )
        except Exception as e:
            logger.debug(f"Index idx_users_verified may already exist or table schema mismatch: {e}")
        # Lawyer profiles table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS lawyer_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                specialization TEXT NOT NULL,
                experience_years INTEGER DEFAULT 0,
                qualification TEXT,
                bio TEXT,
                languages TEXT,
                phone TEXT,
                email TEXT,
                hourly_rate INTEGER,
                location TEXT,
                availability_json TEXT,
                communication_json TEXT,
                consultation_modes_json TEXT,
                status TEXT NOT NULL DEFAULT 'available',
                is_available INTEGER NOT NULL DEFAULT 1,
                rating REAL DEFAULT 4.8,
                cases_handled INTEGER DEFAULT 0,
                photo_url TEXT,
                video_link TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        try:
            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_lawyer_profiles_email
                ON lawyer_profiles (lower(email))
                WHERE email IS NOT NULL
                """
            )
        except Exception as e:
            logger.debug(f"Index idx_lawyer_profiles_email may already exist or table schema mismatch: {e}")
        try:
            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_lawyer_profiles_phone
                ON lawyer_profiles (phone)
                WHERE phone IS NOT NULL
                """
            )
        except Exception as e:
            logger.debug(f"Index idx_lawyer_profiles_phone may already exist or table schema mismatch: {e}")
        # Subscription purchases table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS subscription_purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subscription_id TEXT NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                tier_id TEXT NOT NULL,
                tier_name TEXT NOT NULL,
                price INTEGER NOT NULL,
                payment_reference TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        try:
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_subscription_purchases_user_id
                ON subscription_purchases (user_id)
                """
            )
        except Exception as e:
            logger.debug(f"Index idx_subscription_purchases_user_id may already exist or table schema mismatch: {e}")
        try:
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_subscription_purchases_subscription_id
                ON subscription_purchases (subscription_id)
                """
            )
        except Exception as e:
            logger.debug(f"Index idx_subscription_purchases_subscription_id may already exist or table schema mismatch: {e}")
        try:
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_subscription_purchases_status
                ON subscription_purchases (status)
                """
            )
        except Exception as e:
            logger.debug(f"Index idx_subscription_purchases_status may already exist or table schema mismatch: {e}")
        # Lawyer bookings table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS lawyer_bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_id TEXT NOT NULL,
                tier_id TEXT NOT NULL,
                tier_name TEXT,
                price INTEGER NOT NULL,
                user_id INTEGER,
                preferred_lawyer_id INTEGER,
                customer_name TEXT,
                customer_phone TEXT,
                customer_email TEXT,
                issue_description TEXT,
                payment_reference TEXT,
                subscription_id INTEGER,
                status TEXT NOT NULL DEFAULT 'pending',
                notes TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (preferred_lawyer_id) REFERENCES lawyer_profiles(id),
                FOREIGN KEY (subscription_id) REFERENCES subscription_purchases(id)
            )
            """
        )
        try:
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_lawyer_bookings_booking_id
                ON lawyer_bookings (booking_id)
                """
            )
        except Exception as e:
            logger.debug(f"Index idx_lawyer_bookings_booking_id may already exist or table schema mismatch: {e}")
        try:
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_lawyer_bookings_subscription_id
                ON lawyer_bookings (subscription_id)
                """
            )
        except Exception as e:
            logger.debug(f"Index idx_lawyer_bookings_subscription_id may already exist or table schema mismatch: {e}")
        conn.commit()
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
        return int(cur.lastrowid) # pyright: ignore[reportArgumentType]
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
        return int(cur.lastrowid) # pyright: ignore[reportArgumentType]
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
        return [dict(r) for r in rows]
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
            conditions.append("timestamp >= ?") # pyright: ignore[reportUnknownMemberType]
            params.append(start)
        if end:
            conditions.append("timestamp <= ?") # pyright: ignore[reportUnknownMemberType]
            params.append(end)
        if language:
            conditions.append("language = ?") # pyright: ignore[reportUnknownMemberType]
            params.append(language)
        if q:
            conditions.append("(question LIKE ? OR answer LIKE ?)") # pyright: ignore[reportUnknownMemberType]
            like = f"%{q}%"
            params.extend([like, like])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else "" # pyright: ignore[reportUnknownArgumentType]
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
            conditions.append("timestamp >= ?") # pyright: ignore[reportUnknownMemberType]
            params.append(start)
        if end:
            conditions.append("timestamp <= ?") # pyright: ignore[reportUnknownMemberType]
            params.append(end)
        if form_type:
            conditions.append("form_type = ?") # pyright: ignore[reportUnknownMemberType]
            params.append(form_type)
        if q:
            conditions.append("(form_text LIKE ? OR responses_json LIKE ?)") # pyright: ignore[reportUnknownMemberType]
            like = f"%{q}%"
            params.extend([like, like])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else "" # pyright: ignore[reportUnknownArgumentType]
        sql = (
            "SELECT id, form_type, form_text, responses_json, timestamp FROM forms "
            + where_clause
            + " ORDER BY timestamp DESC, id DESC"
        )
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# Recently resolved chats -----------------------------------------------------
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
            (email, password_hash, verification_token, created_at),
        )
        conn.commit()
        return int(cur.lastrowid) # pyright: ignore[reportArgumentType]
    finally:
        conn.close()


def get_user_by_email(email: str, db_path: str = _DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, email, password_hash, is_verified, verification_token, created_at, verified_at FROM users WHERE email = ?",
            (email,),
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


# Initialize the database when this module is imported


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_json_dump(value: Any) -> str:
    return json.dumps(value or [], ensure_ascii=False)


def get_lawyer_profile_by_id(lawyer_id: int, db_path: str = _DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM lawyer_profiles WHERE id = ?", (lawyer_id,))
        row = cur.fetchone()
        return _serialize_lawyer_row(row) if row else None
    finally:
        conn.close()


def _serialize_lawyer_row(row: sqlite3.Row) -> Dict[str, Any]:
    data = dict(row)
    for key in ("availability_json", "communication_json", "consultation_modes_json"):
        value = data.pop(key, None)
        field_name = key.replace("_json", "")
        if value:
            try:
                data[field_name] = json.loads(value)
            except Exception:
                data[field_name] = []
        else:
            data[field_name] = []
    return data


def create_subscription_purchase(
    purchase: Dict[str, Any],
    db_path: str = _DEFAULT_DB_PATH,
) -> Dict[str, Any]:
    """Create a new subscription purchase and return it."""
    conn = get_db_connection(db_path)
    try:
        cur = conn.cursor()
        now = _now_iso()
        subscription_id = f"SUB_{int(time.time())}_{secrets.token_hex(4)}"
        
        cur.execute(
            """
            INSERT INTO subscription_purchases (
                subscription_id,
                user_id,
                tier_id,
                tier_name,
                price,
                payment_reference,
                status,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
        cur.execute(
            "SELECT * FROM subscription_purchases WHERE id = ?",
            (subscription_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None
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
        cur = conn.cursor()
        if status:
            cur.execute(
                "SELECT * FROM subscription_purchases WHERE user_id = ? AND status = ? ORDER BY created_at DESC",
                (user_id, status),
            )
        else:
            cur.execute(
                "SELECT * FROM subscription_purchases WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            )
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def list_lawyer_profiles(
    only_available: bool = False,
    limit: Optional[int] = None,
    db_path: str = _DEFAULT_DB_PATH,
) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    try:
        cur = conn.cursor()
        clauses = []
        params: List[Any] = []
        if only_available:
            clauses.append("is_available = 1")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = (
            "SELECT * FROM lawyer_profiles "
            f"{where} "
            "ORDER BY is_available DESC, updated_at DESC"
        )
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        cur.execute(sql, params)
        rows = cur.fetchall()
        return [_serialize_lawyer_row(r) for r in rows]
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
        cur = conn.cursor()
        updates = []
        params: List[Any] = []
        if is_available is not None:
            updates.append("is_available = ?")
            params.append(1 if is_available else 0)
        if status:
            updates.append("status = ?")
            params.append(status)
        if not updates:
            return
        params.append(_now_iso())
        params.append(lawyer_id)
        cur.execute(
            f"UPDATE lawyer_profiles SET {', '.join(updates)}, updated_at = ? WHERE id = ?",
            params,
        )
        conn.commit()
    finally:
        conn.close()


def insert_lawyer_booking(
    booking: Dict[str, Any],
    db_path: str = _DEFAULT_DB_PATH,
) -> Dict[str, Any]:
    conn = get_db_connection(db_path)
    try:
        cur = conn.cursor()
        now = _now_iso()
        cur.execute(
            """
            INSERT INTO lawyer_bookings (
                booking_id,
                tier_id,
                tier_name,
                price,
                user_id,
                preferred_lawyer_id,
                customer_name,
                customer_phone,
                customer_email,
                issue_description,
                payment_reference,
                subscription_id,
                status,
                notes,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
