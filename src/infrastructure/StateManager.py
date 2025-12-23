import sqlite3
import json

class StateManager:
    def __init__(self, db_path="state.db"):
        self.db_path = db_path
        self._init_db()
        self._cache = {}

    def _init_db(self):
        """Create table if it doesn't exist"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS strategy_state (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.commit()

    def load_state(self, key, default=None):
        """Load state from DB, fallback to default"""
        if key in self._cache:
            return self._cache[key]

        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM strategy_state WHERE key=?", (key,))
            row = c.fetchone()
            if row:
                value = json.loads(row[0])
            else:
                value = default
            self._cache[key] = value
            return value

    def save_state(self, key, value):
        """Save only if value changed to reduce writes"""
        if self._cache.get(key) == value:
            return

        self._cache[key] = value
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO strategy_state(key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """, (key, json.dumps(value)))
            conn.commit()

    def reset(self):
        """Clear all stored state"""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM strategy_state")
            conn.commit()
        self._cache.clear()