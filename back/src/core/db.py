import logging
import os
import json
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore

class DatabaseManager:
    def __init__(self):
        self.db = self._init_firebase()

    def _init_firebase(self):
        try:
            if not firebase_admin._apps:
                # Try to load credentials from environment variables
                cert_json = os.getenv("FIREBASE_SERVICE_ACCOUNT")
                if cert_json:
                    try:
                        cert_dict = json.loads(cert_json)
                        cred = credentials.Certificate(cert_dict)
                    except Exception as e:
                        logging.error(f"Failed to parse FIREBASE_SERVICE_ACCOUNT JSON: {e}")
                        return None
                else:
                    # Fallback for local development
                    cred_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "firebase_key.json")
                    if os.path.exists(cred_path):
                        cred = credentials.Certificate(cred_path)
                    else:
                        logging.warning("Firebase credentials not found. Set FIREBASE_SERVICE_ACCOUNT env var.")
                        return None
                
                firebase_admin.initialize_app(cred)
            return firestore.client()
        except Exception as e:
            logging.error(f"Failed to initialize Firebase: {e}")
            return None

    def log_usage(self, username, action, provider="", target_lang="", file_type=""):
        if not self.db: return
        try:
            self.db.collection("usage_logs").add({
                "timestamp": datetime.now().isoformat(),
                "username": username,
                "action": action,
                "provider": provider,
                "target_lang": target_lang,
                "file_type": file_type
            })
        except Exception as e:
            logging.error(f"Firebase Logging failed: {e}")
            
    def get_recent_logs(self, limit=100):
        if not self.db: return None
        try:
            import pandas as pd
            docs = self.db.collection("usage_logs").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit).stream()
            data = [doc.to_dict() for doc in docs]
            return pd.DataFrame(data)
        except Exception as e:
            logging.error(f"Failed to fetch Firebase logs: {e}")
            return None

    def log_job(self, job_id, username, filename, provider, target_lang, status, output_path="", file_size=0, cost=0.0):
        if not self.db: return
        try:
            doc_ref = self.db.collection("translation_jobs").document(job_id)
            doc_ref.set({
                "job_id": job_id,
                "timestamp": datetime.now().isoformat(),
                "username": username,
                "filename": filename,
                "provider": provider,
                "target_lang": target_lang,
                "status": status,
                "output_path": output_path,
                "file_size": file_size,
                "cost": cost
            }, merge=True)
        except Exception as e:
            logging.error(f"Failed to log job to Firebase: {e}")

    def get_jobs(self, username=None):
        if not self.db: return []
        try:
            query = self.db.collection("translation_jobs")
            if username:
                query = query.where("username", "==", username)
            
            docs = query.order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            logging.error(f"Failed to get jobs from Firebase: {e}")
            return []

    def get_user_stats(self):
        """Get per-user aggregated statistics from Firestore."""
        if not self.db: return []
        try:
            docs = self.db.collection("translation_jobs").stream()
            jobs = [doc.to_dict() for doc in docs]
            
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
                        "last_activity": job.get("timestamp", "")
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
            logging.error(f"Failed to get user stats from Firebase: {e}")
            return []

    def update_job_status(self, job_id, status):
        if not self.db: return
        try:
            self.db.collection("translation_jobs").document(job_id).update({"status": status})
        except Exception as e:
            logging.error(f"Failed to update job status in Firebase: {e}")

    def delete_job(self, job_id):
        if not self.db: return False
        try:
            self.db.collection("translation_jobs").document(job_id).delete()
            return True
        except Exception as e:
            logging.error(f"Failed to delete job from Firebase: {e}")
            return False

    def auto_timeout_stale_jobs(self, minutes=10):
        if not self.db: return
        try:
            docs = self.db.collection("translation_jobs")\
                .where("status", "==", "processing")\
                .stream()
            
            count = 0
            for doc in docs:
                job = doc.to_dict()
                try:
                    job_time = datetime.fromisoformat(job["timestamp"])
                    if (datetime.now() - job_time).total_seconds() > minutes * 60:
                        doc.reference.update({"status": "timeout"})
                        count += 1
                except:
                    continue
            if count > 0:
                logging.info(f"Auto-timeout {count} stale jobs in Firebase")
        except Exception as e:
            logging.error(f"Failed to auto-timeout jobs in Firebase: {e}")
