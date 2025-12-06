import sqlite3
import os
import requests
import sys
from pathlib import Path

DB_PATH = "../requirements.db"

def init_database():
    """Initialize SQLite database with required tables"""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT NOT NULL,
            description TEXT,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            modified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'active'
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS requirements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            content TEXT NOT NULL,
            req_type TEXT DEFAULT 'functional',
            priority TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'captured',
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ambiguities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            content TEXT NOT NULL,
            status TEXT DEFAULT 'detected',
            resolution TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contradictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            message TEXT NOT NULL,
            status TEXT DEFAULT 'flagged',
            resolution TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            user_message TEXT,
            bot_response TEXT,
            intent TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            project_name TEXT,
            content TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'generated',
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print(f"✓ Database initialized at {DB_PATH}")

def check_rasa_server():
    """Verify Rasa server is running on port 5005"""
    try:
        response = requests.get("http://localhost:5005/", timeout=5)
        print("✓ Rasa server is running on http://localhost:5005")
        return True
    except:
        print("✗ Rasa server NOT running. Start with: rasa run -m models --enable-api --port 5005")
        return False

def check_action_server():
    """Verify action server is running on port 5055"""
    try:
        response = requests.get("http://localhost:5055/webhook", timeout=5)
        print("✓ Action server is running on http://localhost:5055")
        return True
    except:
        print("✗ Action server NOT running. Start with: rasa run actions")
        return False

def check_ollama_server():
    """Verify Ollama server is running on port 11434"""
    try:
        response = requests.post(
            "http://localhost:11434/api/tags",
            timeout=5
        )
        models = response.json().get("models", [])
        if models:
            print(f"✓ Ollama server is running with models: {[m.get('name') for m in models[:3]]}")
            return True
        else:
            print("✗ Ollama running but no models found. Pull a model: ollama pull phi3:mini")
            return False
    except:
        print("✗ Ollama server NOT running. Start with: ollama serve")
        return False

def check_flask_backend():
    """Verify Flask backend is running on port 5000"""
    try:
        response = requests.get("http://localhost:5000/api/health", timeout=5)
        print("✓ Flask backend is running on http://localhost:5000")
        return True
    except:
        print("✗ Flask backend NOT running. Start with: python backend/app.py")
        return False

def check_database():
    """Verify database exists and has proper schema"""
    db_path = "requirements.db"
    if not os.path.exists(db_path):
        print(f"✗ Database not found at {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        required_tables = ['projects', 'requirements', 'ambiguities', 'contradictions', 'conversation_history']
        missing = [t for t in required_tables if t not in tables]
        
        conn.close()
        
        if missing:
            print(f"✗ Database missing tables: {missing}")
            return False
        
        print(f"✓ Database OK with tables: {', '.join(required_tables)}")
        return True
    except Exception as e:
        print(f"✗ Database error: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("REQUIREMENTS BOT - SETUP VERIFICATION")
    print("="*60 + "\n")
    
    checks = [
        ("Rasa Server (port 5005)", check_rasa_server),
        ("Action Server (port 5055)", check_action_server),
        ("Ollama Server (port 11434)", check_ollama_server),
        ("Flask Backend (port 5000)", check_flask_backend),
        ("SQLite Database", check_database),
    ]
    
    results = []
    for name, check_func in checks:
        print(f"Checking {name}...")
        results.append(check_func())
        print()
    
    print("="*60)
    passed = sum(results)
    total = len(results)
    print(f"SUMMARY: {passed}/{total} checks passed")
    print("="*60 + "\n")
    
    if passed == total:
        print("✓ All systems ready! Bot is operational.")
        print("\nYou can now access the chatbot at: http://localhost:3000")
    else:
        print("✗ Some systems are not running. Please check the messages above.")
    
    return passed == total

if __name__ == "__main__":
    init_database()
    sys.exit(0 if main() else 1)
