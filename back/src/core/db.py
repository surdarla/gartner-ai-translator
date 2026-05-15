import logging
import os
from datetime import datetime

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False


# Initialize global supabase client
def _get_global_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except:
        return None

supabase = _get_global_supabase()

class DatabaseManager:
    def __init__(self):
        self.db = supabase

    # Redundant method removed, now using global supabase
    pass

    # ------------------------------------------------------------------
    # Usage Logs
    # ------------------------------------------------------------------

    def log_usage(self, username, action, provider="", target_lang="", file_type=""):
        if not self.db:
            return
        try:
            self.db.table("usage_logs").insert({
                "timestamp": datetime.now().isoformat(),
                "username": username,
                "action": action,
                "provider": provider,
                "target_lang": target_lang,
                "file_type": file_type,
            }).execute()
        except Exception as e:
            logging.error(f"Supabase usage_logs insert failed: {e}")

    def get_recent_logs(self, limit=100):
        if not self.db:
            return None
        try:
            res = (
                self.db.table("usage_logs")
                .select("*")
                .order("timestamp", desc=True)
                .limit(limit)
                .execute()
            )
            return res.data
        except Exception as e:
            logging.error(f"Failed to fetch usage_logs from Supabase: {e}")
            return None

    # ------------------------------------------------------------------
    # Translation Jobs
    # ------------------------------------------------------------------

    def log_job(
        self,
        job_id,
        username,
        filename,
        provider,
        target_lang,
        status,
        output_path="",
        file_size=0,
        cost=0.0,
    ):
        if not self.db:
            return
        try:
            self.db.table("translation_jobs").upsert({
                "job_id": job_id,
                "timestamp": datetime.now().isoformat(),
                "username": username,
                "filename": filename,
                "provider": provider,
                "target_lang": target_lang,
                "status": status,
                "output_path": output_path,
                "file_size": file_size,
                "cost": cost,
            }).execute()
        except Exception as e:
            logging.error(f"Failed to log job to Supabase: {e}")

    def get_jobs(self, username=None):
        if not self.db:
            return []
        try:
            query = (
                self.db.table("translation_jobs")
                .select("*")
                .order("timestamp", desc=True)
            )
            if username:
                query = query.eq("username", username)
            res = query.execute()
            return res.data
        except Exception as e:
            logging.error(f"Failed to get jobs from Supabase: {e}")
            return []

    def get_user_stats(self):
        """Get per-user aggregated statistics from Supabase."""
        if not self.db:
            return []
        try:
            res = self.db.table("translation_jobs").select("*").execute()
            jobs = res.data

            stats = {}
            for job in jobs:
                user = job.get("username", "unknown")
                if user not in stats:
                    stats[user] = {
                        "username": user,
                        "total_jobs": 0,
                        "completed_jobs": 0,
                        "failed_jobs": 0,
                        "total_cost": 0.0,
                        "total_size": 0,
                        "last_activity": job.get("timestamp", ""),
                    }

                s = stats[user]
                s["total_jobs"] += 1
                if job.get("status") == "completed":
                    s["completed_jobs"] += 1
                elif job.get("status") == "failed":
                    s["failed_jobs"] += 1

                s["total_cost"] += job.get("cost", 0.0)
                s["total_size"] += job.get("file_size", 0)
                ts = job.get("timestamp", "")
                if ts > s["last_activity"]:
                    s["last_activity"] = ts

            return sorted(stats.values(), key=lambda x: x["last_activity"], reverse=True)
        except Exception as e:
            logging.error(f"Failed to get user stats from Supabase: {e}")
            return []

    def update_job_status(self, job_id, status):
        if not self.db:
            return
        try:
            self.db.table("translation_jobs").update({"status": status}).eq(
                "job_id", job_id
            ).execute()
        except Exception as e:
            logging.error(f"Failed to update job status in Supabase: {e}")

    def delete_job(self, job_id):
        if not self.db:
            return False
        try:
            self.db.table("translation_jobs").delete().eq("job_id", job_id).execute()
            return True
        except Exception as e:
            logging.error(f"Failed to delete job from Supabase: {e}")
            return False

    def auto_timeout_stale_jobs(self, minutes=10):
        if not self.db:
            return
        try:
            res = (
                self.db.table("translation_jobs")
                .select("job_id, timestamp")
                .eq("status", "processing")
                .execute()
            )
            count = 0
            for job in res.data:
                try:
                    job_time = datetime.fromisoformat(job["timestamp"])
                    if (datetime.now() - job_time).total_seconds() > minutes * 60:
                        self.db.table("translation_jobs").update(
                            {"status": "timeout"}
                        ).eq("job_id", job["job_id"]).execute()
                        count += 1
                except Exception:
                    continue
            if count > 0:
                logging.info(f"Auto-timeout {count} stale jobs in Supabase")
        except Exception as e:
            logging.error(f"Failed to auto-timeout jobs in Supabase: {e}")
