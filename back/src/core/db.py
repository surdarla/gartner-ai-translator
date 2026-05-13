import sqlite3
import logging
from core.config import get_db_path

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
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS translation_jobs (
                        job_id TEXT PRIMARY KEY,
                        timestamp TEXT,
                        username TEXT,
                        filename TEXT,
                        provider TEXT,
                        target_lang TEXT,
                        status TEXT,
                        output_path TEXT,
                        file_size INTEGER DEFAULT 0,
                        cost REAL DEFAULT 0.0
                    )
                ''')
                # Migration: Add columns if they don't exist (for existing DBs)
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(translation_jobs)")
                columns = [column[1] for column in cursor.fetchall()]
                if "file_size" not in columns:
                    conn.execute("ALTER TABLE translation_jobs ADD COLUMN file_size INTEGER DEFAULT 0")
                if "cost" not in columns:
                    conn.execute("ALTER TABLE translation_jobs ADD COLUMN cost REAL DEFAULT 0.0")
                
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

    def log_job(self, job_id, username, filename, provider, target_lang, status, output_path="", file_size=0, cost=0.0):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    '''INSERT INTO translation_jobs (job_id, timestamp, username, filename, provider, target_lang, status, output_path, file_size, cost) 
                       VALUES (?, datetime('now','localtime'), ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(job_id) DO UPDATE SET 
                       status=excluded.status, output_path=excluded.output_path, cost=excluded.cost''',
                    (job_id, username, filename, provider, target_lang, status, output_path, file_size, cost)
                )
                conn.commit()
        except Exception as e:
            logging.error(f"Failed to log job: {e}")

    def get_jobs(self, username=None):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                if username:
                    cursor = conn.execute("SELECT * FROM translation_jobs WHERE username = ? ORDER BY timestamp DESC", (username,))
                else:
                    cursor = conn.execute("SELECT * FROM translation_jobs ORDER BY timestamp DESC")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Failed to get jobs: {e}")
            return []

    def get_user_stats(self):
        """Get per-user aggregated statistics for admin dashboard."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT 
                        username,
                        COUNT(*) as total_jobs,
                        SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed_jobs,
                        SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed_jobs,
                        COALESCE(SUM(cost), 0) as total_cost,
                        COALESCE(SUM(file_size), 0) as total_size,
                        MAX(timestamp) as last_activity
                    FROM translation_jobs
                    GROUP BY username
                    ORDER BY last_activity DESC
                """)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Failed to get user stats: {e}")
            return []

    def update_job_status(self, job_id, status):
        """Update a job's status (e.g. cancelled, timeout)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("UPDATE translation_jobs SET status = ? WHERE job_id = ?", (status, job_id))
                conn.commit()
        except Exception as e:
            logging.error(f"Failed to update job status: {e}")

    def delete_job(self, job_id):
        """Delete a job record (admin only)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM translation_jobs WHERE job_id = ?", (job_id,))
                conn.commit()
                return True
        except Exception as e:
            logging.error(f"Failed to delete job: {e}")
            return False

    def auto_timeout_stale_jobs(self, minutes=10):
        """Mark processing jobs older than N minutes as timeout."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE translation_jobs 
                    SET status = 'timeout' 
                    WHERE status = 'processing' 
                    AND timestamp < datetime('now', 'localtime', ?)
                """, (f'-{minutes} minutes',))
                conn.commit()
                logging.info(f"Auto-timeout stale jobs older than {minutes} minutes")
        except Exception as e:
            logging.error(f"Failed to auto-timeout stale jobs: {e}")
