import sqlite3
import logging
from py.core.config import get_db_path

class DatabaseManager:
    def __init__(self):
        self.db_path = get_db_path()
        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS usage_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, 
                        timestamp TEXT, 
                        username TEXT, 
                        action TEXT, 
                        provider TEXT, 
                        target_lang TEXT, 
                        file_type TEXT
                    )
                ''')
                conn.commit()
        except Exception as e:
            logging.error(f"Failed to initialize DB: {e}")

    def log_usage(self, username, action, provider="", target_lang="", file_type=""):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO usage_logs (timestamp, username, action, provider, target_lang, file_type) VALUES (datetime('now','localtime'), ?, ?, ?, ?, ?)",
                    (username, action, provider, target_lang, file_type)
                )
                conn.commit()
        except Exception as e:
            logging.error(f"DB Logging failed: {e}")
            
    def get_recent_logs(self, limit=100):
        try:
            import pandas as pd
            with sqlite3.connect(self.db_path) as conn:
                return pd.read_sql_query(f"SELECT * FROM usage_logs ORDER BY timestamp DESC LIMIT {limit}", conn)
        except Exception as e:
            logging.error(f"Failed to fetch DB logs: {e}")
            return None
