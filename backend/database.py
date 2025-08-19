# backend/database.py
import sqlite3
import json

DATABASE_NAME = "learning_platform.db"

def init_db():
    """Initializes the database with all necessary tables."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    # --- Core Tables ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            auth0_id TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_name TEXT NOT NULL,
            teacher_id INTEGER NOT NULL,
            FOREIGN KEY (teacher_id) REFERENCES users (id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_title TEXT NOT NULL,
            course_id INTEGER NOT NULL,
            original_text TEXT NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses (id)
        )
    """)
    
    # --- Caching and Performance Tables ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS generated_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id INTEGER NOT NULL,
            style TEXT NOT NULL,
            content_type TEXT NOT NULL,
            data TEXT NOT NULL,
            quiz_data TEXT,
            UNIQUE(lesson_id, style)
        )
    """)
    
    # Table to store results from the Socratic Tutor
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS socratic_dialogues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id INTEGER NOT NULL,
            session_id TEXT NOT NULL,
            style TEXT NOT NULL,
            conversation_history TEXT NOT NULL,
            understanding_score INTEGER,
            FOREIGN KEY (lesson_id) REFERENCES lessons (id)
        )
    """)
    
    conn.commit()
    conn.close()

def get_cached_content(lesson_id: int, style: str):
    """Checks the database for cached content for a given lesson_id and style."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT content_type, data, quiz_data FROM generated_content WHERE lesson_id = ? AND style = ?",
        (lesson_id, style)
    )
    result = cursor.fetchone()
    conn.close()
    
    if result:
        quiz_data = json.loads(result[2]) if result[2] else None
        return {
            "content_type": result[0], 
            "data": json.loads(result[1]),
            "quiz_data": quiz_data
        }
    return None

def cache_content(lesson_id: int, style: str, content_type: str, data: dict, quiz_data: dict):
    """Saves newly generated content to the database."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        data_json = json.dumps(data)
        quiz_json = json.dumps(quiz_data) if quiz_data else None
        cursor.execute(
            "INSERT INTO generated_content (lesson_id, style, content_type, data, quiz_data) VALUES (?, ?, ?, ?, ?)",
            (lesson_id, style, content_type, data_json, quiz_json)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # This can happen if two requests try to insert the same thing at once.
        # It's safe to ignore in this caching context.
        pass
    finally:
        conn.close()
