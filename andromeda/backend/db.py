import sqlite3
import os
import json

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../data'))
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, 'sessions.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# Initialize DB on import
init_db()

def save_message(session_id: str, role: str, content: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO messages (session_id, role, content)
        VALUES (?, ?, ?)
    ''', (session_id, role, content))
    conn.commit()
    conn.close()

def get_session_history(session_id: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT role, content FROM messages
        WHERE session_id = ?
        ORDER BY timestamp ASC
    ''', (session_id,))
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for role, content in rows:
        history.append({"role": role, "content": content})
    return history

def get_all_sessions():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT m1.session_id, MAX(m1.timestamp) as last_active, 
               (SELECT content FROM messages m2 WHERE m2.session_id = m1.session_id AND m2.role = 'user' ORDER BY timestamp ASC LIMIT 1) as title
        FROM messages m1
        GROUP BY m1.session_id
        ORDER BY last_active DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    
    sessions = []
    for session_id, last_active, title in rows:
        if not title:
            title = "Empty Session"
        else:
            title = title[:30] + "..." if len(title) > 30 else title
        sessions.append({
            "session_id": session_id,
            "last_active": last_active,
            "title": title
        })
    return sessions

def delete_session(session_id: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM messages WHERE session_id = ?', (session_id,))
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted_count > 0
