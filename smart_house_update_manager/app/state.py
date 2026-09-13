"""Crash-safe SQLite journal and persistent logical execution lock."""
import json
import sqlite3
from pathlib import Path


class Busy(RuntimeError):
    pass


class State:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY, run_id TEXT, at TEXT, phase TEXT, message TEXT);
        """)

    def get(self, key, default=None):
        row = self.db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def put(self, key, value):
        self.put_many({key: value})

    def put_many(self, items):
        with self.db:
            for key, value in items.items():
                self.db.execute("INSERT OR REPLACE INTO kv VALUES (?,?)", (key, json.dumps(value)))

    def acquire(self, run):
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            row = self.db.execute("SELECT value FROM kv WHERE key='lock'").fetchone()
            if row and json.loads(row[0]):
                raise Busy("Uma execução anterior ainda precisa ser resolvida")
            self.db.execute("INSERT OR REPLACE INTO kv VALUES ('lock',?)", (json.dumps(run["run_id"]),))
            self.db.execute("INSERT OR REPLACE INTO runs VALUES (?,?)", (run["run_id"], json.dumps(run)))
            if run.get("scheduled_date"):
                self.db.execute("INSERT OR REPLACE INTO kv VALUES ('maintenance_date',?)",
                                (json.dumps(run["scheduled_date"]),))

    def save(self, run, release=False):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO runs VALUES (?,?)", (run["run_id"], json.dumps(run)))
            if release:
                self.db.execute("UPDATE kv SET value='null' WHERE key='lock'")

    def active(self):
        key = self.get("lock")
        row = self.db.execute("SELECT value FROM runs WHERE id=?", (key,)).fetchone() if key else None
        if key and not row:
            raise RuntimeError("Lock sem execução: intervenção necessária")
        return json.loads(row[0]) if row else None

    def history(self):
        return [json.loads(r[0]) for r in self.db.execute("SELECT value FROM runs ORDER BY rowid DESC LIMIT 100")]

    def event(self, run_id, at, phase, message):
        with self.db:
            self.db.execute("INSERT INTO events(run_id,at,phase,message) VALUES (?,?,?,?)",
                            (run_id, at, phase, message))

    def events(self):
        return [dict(zip(("run_id", "at", "phase", "message"), row)) for row in
                self.db.execute("SELECT run_id,at,phase,message FROM events ORDER BY id DESC LIMIT 300")]

    def close(self):
        self.db.close()
