import json
import sqlite3
from pathlib import Path

DB_PATH = Path("wordwave_projects.sqlite3")

def initialize():
    with sqlite3.connect(DB_PATH) as con:
        con.execute("""CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, mode TEXT, text TEXT, voice TEXT,
            settings TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")

def save(name, mode, text, voice="", settings=None):
    initialize()
    with sqlite3.connect(DB_PATH) as con:
        con.execute(
            "INSERT INTO projects(name,mode,text,voice,settings) VALUES(?,?,?,?,?)",
            (name, mode, text, voice, json.dumps(settings or {}))
        )

def list_all():
    initialize()
    with sqlite3.connect(DB_PATH) as con:
        return con.execute(
            "SELECT id,name,mode,voice,created_at FROM projects ORDER BY id DESC"
        ).fetchall()

def get_text(project_id):
    initialize()
    with sqlite3.connect(DB_PATH) as con:
        row = con.execute("SELECT text FROM projects WHERE id=?", (int(project_id),)).fetchone()
    return row[0] if row else None

def delete(project_id):
    initialize()
    with sqlite3.connect(DB_PATH) as con:
        con.execute("DELETE FROM projects WHERE id=?", (int(project_id),))
