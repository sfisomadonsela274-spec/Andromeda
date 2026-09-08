import sqlite3
import os
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../data'))
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, 'andromeda.db')

def get_db_connection():
    """Returns a SQLite connection configured with WAL mode and row factory."""
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """Hashes password using PBKDF2-HMAC-SHA256 with 100,000 iterations and a 32-byte salt."""
    if not salt:
        salt = secrets.token_hex(32)
    pwd_bytes = password.encode('utf-8')
    salt_bytes = salt.encode('utf-8')
    hash_bytes = hashlib.pbkdf2_hmac('sha256', pwd_bytes, salt_bytes, 100000)
    return hash_bytes.hex(), salt

def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    """Safely verifies password against expected hash using constant-time comparison."""
    computed_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(computed_hash, expected_hash)

def init_db():
    """Initializes the unified Andromeda SQLite3 schema."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Users Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL COLLATE NOCASE,
            email TEXT UNIQUE NOT NULL COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            display_name TEXT,
            preferred_model TEXT DEFAULT 'llama3.2:latest',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login DATETIME
        )
    ''')

    # 2. User Tokens Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_tokens (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            expires_at DATETIME NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # 3. Sessions (Conversations) Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_active DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # 4. Messages Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # 5. User Preferences Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, key),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # Indexes for lightning-fast queries
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, timestamp ASC);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id, last_active DESC);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tokens_lookup ON user_tokens(token, expires_at);')

    # Provision default guest account for demo / backwards compatibility
    cursor.execute("SELECT id FROM users WHERE id = 'guest'")
    if not cursor.fetchone():
        guest_pwd_hash, guest_salt = hash_password('andromeda_guest_demo')
        cursor.execute('''
            INSERT INTO users (id, username, email, password_hash, salt, display_name, preferred_model)
            VALUES ('guest', 'guest', 'guest@andromeda.local', ?, ?, 'Guest Explorer', 'llama3.2:latest')
        ''', (guest_pwd_hash, guest_salt))

    # 6. Schema Migrations Tracking Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schema_migrations (
            migration_name TEXT PRIMARY KEY,
            applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Migration from legacy sessions.db - executes AT MOST ONCE ever
    cursor.execute("SELECT migration_name FROM schema_migrations WHERE migration_name = 'legacy_sessions_migrated'")
    if not cursor.fetchone():
        legacy_db = os.path.join(DATA_DIR, 'sessions.db')
        cursor.execute('SELECT COUNT(*) as cnt FROM messages')
        if cursor.fetchone()['cnt'] == 0 and os.path.exists(legacy_db):
            try:
                legacy_conn = sqlite3.connect(legacy_db)
                legacy_cur = legacy_conn.cursor()
                legacy_cur.execute("SELECT session_id, role, content, timestamp FROM messages ORDER BY id ASC")
                legacy_msgs = legacy_cur.fetchall()
                legacy_conn.close()

                # Populate guest sessions & messages
                session_set = set()
                for s_id, role, content, tstamp in legacy_msgs:
                    if s_id not in session_set:
                        cursor.execute('''
                            INSERT OR IGNORE INTO sessions (session_id, user_id, title, created_at, last_active)
                            VALUES (?, 'guest', ?, ?, ?)
                        ''', (s_id, content[:30] if content else 'Session', tstamp, tstamp))
                        session_set.add(s_id)
                    cursor.execute('''
                        INSERT INTO messages (session_id, user_id, role, content, timestamp)
                        VALUES (?, 'guest', ?, ?, ?)
                    ''', (s_id, role, content, tstamp))
            except Exception as e:
                print(f"[DB Migration Warning] Could not migrate legacy sessions.db: {e}")

        # Record migration completed so it NEVER executes again even if messages are 0
        cursor.execute("INSERT OR IGNORE INTO schema_migrations (migration_name) VALUES ('legacy_sessions_migrated')")
        if os.path.exists(legacy_db):
            try:
                os.rename(legacy_db, legacy_db + ".migrated")
            except Exception:
                pass

    conn.commit()
    conn.close()

# Initialize DB on import
init_db()

# ==========================================
# USER & AUTH MANAGEMENT
# ==========================================

def create_user(username: str, email: str, password: str, display_name: Optional[str] = None, preferred_model: str = "llama3.2:latest") -> Dict[str, Any]:
    """Creates a new user with hashed password."""
    username = username.strip().lower()
    email = email.strip().lower()
    if not display_name:
        display_name = username.capitalize()

    pwd_hash, salt = hash_password(password)
    user_id = secrets.token_hex(12)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO users (id, username, email, password_hash, salt, display_name, preferred_model)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, email, pwd_hash, salt, display_name, preferred_model))
        conn.commit()
    finally:
        conn.close()

    return {
        "id": user_id,
        "username": username,
        "email": email,
        "display_name": display_name,
        "preferred_model": preferred_model
    }

def authenticate_user(username_or_email: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticates credentials against the users table."""
    identifier = username_or_email.strip().lower()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, username, email, password_hash, salt, display_name, preferred_model
        FROM users
        WHERE username = ? OR email = ?
    ''', (identifier, identifier))
    user = cursor.fetchone()

    if not user:
        conn.close()
        return None

    if not verify_password(password, user['salt'], user['password_hash']):
        conn.close()
        return None

    # Update last_login
    cursor.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user['id'],))
    conn.commit()
    conn.close()

    return {
        "id": user['id'],
        "username": user['username'],
        "email": user['email'],
        "display_name": user['display_name'],
        "preferred_model": user['preferred_model']
    }

def create_user_token(user_id: str, days_valid: int = 30) -> str:
    """Generates and persists a cryptographically secure token."""
    token = secrets.token_urlsafe(36)
    expires_at = datetime.utcnow() + timedelta(days=days_valid)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO user_tokens (token, user_id, expires_at)
        VALUES (?, ?, ?)
    ''', (token, user_id, expires_at.strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()
    return token

def get_user_by_token(token: str) -> Optional[Dict[str, Any]]:
    """Resolves a valid user record from a session token."""
    if not token:
        return None

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.id, u.username, u.email, u.display_name, u.preferred_model, t.expires_at
        FROM user_tokens t
        JOIN users u ON u.id = t.user_id
        WHERE t.token = ? AND t.expires_at > CURRENT_TIMESTAMP
    ''', (token,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "id": row['id'],
        "username": row['username'],
        "email": row['email'],
        "display_name": row['display_name'],
        "preferred_model": row['preferred_model']
    }

def revoke_user_token(token: str) -> bool:
    """Revokes a session token on logout."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_tokens WHERE token = ?", (token,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

# ==========================================
# USER-SCOPED SESSIONS & MESSAGING
# ==========================================

def save_message(session_id: str, role: str, content: str, user_id: str = "guest"):
    """Saves a message scoped to a user and ensures session metadata exists."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Ensure session exists
    cursor.execute("SELECT session_id FROM sessions WHERE session_id = ?", (session_id,))
    if not cursor.fetchone():
        title = content[:30] + "..." if len(content) > 30 else content
        if not title.strip():
            title = "New Conversation"
        cursor.execute('''
            INSERT INTO sessions (session_id, user_id, title, last_active)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ''', (session_id, user_id, title))
    else:
        cursor.execute('''
            UPDATE sessions 
            SET last_active = CURRENT_TIMESTAMP
            WHERE session_id = ?
        ''', (session_id,))

    cursor.execute('''
        INSERT INTO messages (session_id, user_id, role, content)
        VALUES (?, ?, ?, ?)
    ''', (session_id, user_id, role, content))
    conn.commit()
    conn.close()

def get_session_history(session_id: str, user_id: str = "guest") -> List[Dict[str, str]]:
    """Fetches ordered messages for a given session and user, ensuring session exists."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Verify session exists in sessions table
    cursor.execute('''
        SELECT session_id FROM sessions 
        WHERE session_id = ? AND (user_id = ? OR user_id = 'guest' OR ? = 'guest')
    ''', (session_id, user_id, user_id))
    if not cursor.fetchone():
        conn.close()
        return []

    cursor.execute('''
        SELECT role, content FROM messages
        WHERE session_id = ?
        ORDER BY timestamp ASC, id ASC
    ''', (session_id,))
    rows = cursor.fetchall()
    conn.close()

    history = []
    for row in rows:
        history.append({"role": row['role'], "content": row['content']})
    return history

def get_all_sessions(user_id: str = "guest") -> List[Dict[str, Any]]:
    """Fetches all sessions belonging to the user ordered by most recently active."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT s.session_id, s.last_active, s.title,
               (SELECT content FROM messages m WHERE m.session_id = s.session_id AND m.role = 'user' ORDER BY timestamp ASC, id ASC LIMIT 1) as first_user_msg
        FROM sessions s
        WHERE s.user_id = ? OR s.user_id = 'guest' OR ? = 'guest'
        GROUP BY s.session_id
        ORDER BY s.last_active DESC
    ''', (user_id, user_id))
    rows = cursor.fetchall()
    conn.close()

    sessions = []
    for row in rows:
        title = row['title']
        if not title or title == "New Conversation":
            first_msg = row['first_user_msg']
            if first_msg:
                title = first_msg[:30] + "..." if len(first_msg) > 30 else first_msg
            else:
                title = "Empty Session"
        sessions.append({
            "session_id": row['session_id'],
            "last_active": row['last_active'],
            "title": title
        })
    return sessions

def delete_session(session_id: str, user_id: str = "guest") -> bool:
    """Permanently deletes a session and all its messages across all tables."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # 1. Explicitly purge messages
    cursor.execute('DELETE FROM messages WHERE session_id = ?', (session_id,))
    # 2. Explicitly purge session metadata
    cursor.execute('''
        DELETE FROM sessions 
        WHERE session_id = ? AND (user_id = ? OR user_id = 'guest' OR ? = 'guest')
    ''', (session_id, user_id, user_id))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return True

def delete_all_sessions(user_id: str = "guest") -> int:
    """Permanently deletes all sessions and messages for the user or all if guest."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if user_id and user_id != "guest":
        cursor.execute('DELETE FROM messages WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM sessions WHERE user_id = ?', (user_id,))
    else:
        cursor.execute('DELETE FROM messages')
        cursor.execute('DELETE FROM sessions')
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted

# ==========================================
# USER PREFERENCES
# ==========================================

def get_user_preferences(user_id: str) -> Dict[str, str]:
    """Retrieves all key-value preferences for a user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM user_preferences WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return {row['key']: row['value'] for row in rows}

def set_user_preference(user_id: str, key: str, value: str):
    """Sets a key-value preference for a user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO user_preferences (user_id, key, value, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id, key) DO UPDATE SET
            value = excluded.value,
            updated_at = CURRENT_TIMESTAMP
    ''', (user_id, key, value))
    conn.commit()
    conn.close()
