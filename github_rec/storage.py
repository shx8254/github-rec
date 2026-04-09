import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path


def _dict_from_row(row, cols):
    return dict(zip(cols, row)) if row else None


class Storage:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS starred_repos (
                    id INTEGER PRIMARY KEY,
                    owner TEXT NOT NULL,
                    name TEXT NOT NULL,
                    full_name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    language TEXT,
                    stars INTEGER,
                    forks INTEGER,
                    topics TEXT,
                    pushed_at TEXT,
                    archived INTEGER DEFAULT 0,
                    size INTEGER DEFAULT 0,
                    has_wiki INTEGER DEFAULT 1,
                    starred_at TEXT,
                    fetched_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner TEXT NOT NULL,
                    name TEXT NOT NULL,
                    full_name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    language TEXT,
                    stars INTEGER,
                    forks INTEGER,
                    topics TEXT,
                    pushed_at TEXT,
                    score REAL,
                    reasons TEXT,
                    recommended_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS filters_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name TEXT,
                    reason TEXT,
                    filtered_at TEXT
                )
            """)

    def save_starred_repos(self, repos: list):
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            for repo in repos:
                topics = json.dumps(repo.get("topics") or [], ensure_ascii=False)
                conn.execute("""
                    INSERT OR REPLACE INTO starred_repos
                    (id, owner, name, full_name, description, language, stars,
                     forks, topics, pushed_at, archived, size, has_wiki, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    repo["id"],
                    repo["owner"]["login"],
                    repo["name"],
                    repo["full_name"],
                    repo.get("description"),
                    repo.get("language"),
                    repo.get("stargazers_count", 0),
                    repo.get("forks_count", 0),
                    topics,
                    repo.get("pushed_at"),
                    int(repo.get("archived", False)),
                    repo.get("size", 0),
                    int(repo.get("has_wiki", True)),
                    now,
                ))
            conn.commit()

    def get_starred_repos(self) -> list:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM starred_repos ORDER BY stars DESC").fetchall()
            return [dict(r) for r in rows]

    def get_repo_full_names(self) -> set:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT full_name FROM starred_repos").fetchall()
            return {r[0] for r in rows}

    def save_recommendations(self, recs: list):
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM recommendations")
            for rec in recs:
                conn.execute("""
                    INSERT INTO recommendations
                    (owner, name, full_name, description, language, stars,
                     forks, topics, pushed_at, score, reasons, recommended_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    rec["owner"]["login"] if isinstance(rec.get("owner"), dict) else rec.get("owner", ""),
                    rec["name"],
                    rec["full_name"],
                    rec.get("description"),
                    rec.get("language"),
                    rec.get("stargazers_count", 0),
                    rec.get("forks_count", 0),
                    json.dumps(rec.get("topics") or [], ensure_ascii=False),
                    rec.get("pushed_at"),
                    rec.get("score", 0),
                    json.dumps(rec.get("reasons") or [], ensure_ascii=False),
                    now,
                ))
            conn.commit()

    def get_recommendations(self) -> list:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM recommendations ORDER BY score DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def log_filter(self, full_name: str, reason: str):
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO filters_log (full_name, reason, filtered_at) VALUES (?, ?, ?)",
                (full_name, reason, now),
            )
            conn.commit()

    def set_meta(self, key: str, value: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                (key, value),
            )
            conn.commit()

    def get_meta(self, key: str, default=None) -> str:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT value FROM meta WHERE key = ?", (key,)
            ).fetchone()
            return row[0] if row else default
