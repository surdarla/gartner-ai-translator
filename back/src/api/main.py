import os
import sys
import json
import uuid
import tempfile
import asyncio
import hmac
import hashlib
import jwt
import bcrypt
import httpx
from datetime import datetime
from dotenv import load_dotenv
from typing import Dict, Any, List
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from google import genai
from google.genai import types

# Add back/src to sys.path for core modules
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from core.config import load_glossary, save_glossary, DIRECTION_MAP, get_base_dir
from core.translators import GeminiTranslator, ClaudeTranslator, FreeTranslator, UpstageTranslator
from core.document_processor import PDFProcessor, PPTXProcessor
from core.db import DatabaseManager, supabase

db_manager = DatabaseManager()

app = FastAPI(title="AI Document Translator API")

@app.on_event("startup")
async def startup_periodic_timeout():
    async def _auto_timeout_loop():
        while True:
            await asyncio.sleep(300)
            db_manager.auto_timeout_stale_jobs(minutes=10)
    asyncio.create_task(_auto_timeout_loop())

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")
ALGORITHM = "HS256"
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID") or os.getenv("CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET") or os.getenv("CLIENT_SECRET")

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# --- DB & Auth ---
def get_users_db():
    if supabase is None:
        return {}
    try:
        res = supabase.table("users").select("*").execute()
        return {u["email"]: u for u in res.data}
    except:
        return {}

def save_users_db(user_data):
    if supabase:
        try:
            supabase.table("users").upsert(user_data).execute()
        except Exception as e:
            print(f"DB Error: {e}")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {"username": payload["sub"], "role": payload.get("role", "user")}
    except:
        raise HTTPException(status_code=401)

async def get_current_username(user: dict = Depends(get_current_user)):
    return user["username"]

@app.post("/auth/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    users = get_users_db()
    user = users.get(form_data.username)
    if not user or not user.get("password"):
        raise HTTPException(status_code=400, detail="Invalid login")
    if not bcrypt.checkpw(form_data.password.encode(), user["password"].encode()):
        raise HTTPException(status_code=400, detail="Invalid login")
    token = jwt.encode({"sub": form_data.username, "role": user.get("role", "user")}, SECRET_KEY)
    return {"access_token": token, "token_type": "bearer"}

def get_frontend_url(request: Request = None):
    url = os.getenv("FRONTEND_URL")
    if os.getenv("VERCEL") == "1" and request:
        return f"{request.url.scheme}://{request.url.netloc}".replace("/api", "").rstrip("/")
    return (url or "http://localhost:5173").rstrip("/")

def get_backend_url():
    return (os.getenv("BACKEND_URL") or "http://localhost:8000").rstrip("/")

@app.get("/auth/google/login")
async def google_login(request: Request):
    import secrets
    from urllib.parse import urlencode
    
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Google SSO not configured")

    redirect_uri = f"{get_backend_url()}/auth/google/callback"
    nonce = secrets.token_urlsafe(16)
    signature = hmac.new(SECRET_KEY.encode(), nonce.encode(), hashlib.sha256).hexdigest()
    state = f"{nonce}.{signature}"

    params = urlencode({
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account"
    })
    return RedirectResponse(url=f"https://accounts.google.com/o/oauth2/v2/auth?{params}")

@app.get("/auth/google/callback")
async def google_callback(request: Request, code: str = None, state: str = None, error: str = None):
    if error or not code:
        raise HTTPException(status_code=400)
    async with httpx.AsyncClient() as client:
        t_res = await client.post("https://oauth2.googleapis.com/token", data={
            "code": code, "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": f"{get_backend_url()}/auth/google/callback", "grant_type": "authorization_code"
        })
        t_data = t_res.json()
        if "access_token" not in t_data:
            raise HTTPException(status_code=400)
        u_res = await client.get("https://www.googleapis.com/oauth2/v3/userinfo", headers={"Authorization": f"Bearer {t_data['access_token']}"})
        u_info = u_res.json()
    
    email = u_info.get("email")
    save_users_db({"email": email, "name": u_info.get("name", email), "sso": "google", "role": "user"})
    jwt_token = jwt.encode({"sub": email, "role": "user", "name": u_info.get("name")}, SECRET_KEY)
    return RedirectResponse(url=f"{get_frontend_url(request)}/login?token={jwt_token}")

# --- Features ---
@app.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    return user

@app.get("/glossary")
async def get_glossary():
    return load_glossary()

@app.post("/glossary")
async def update_glossary(data: dict):
    save_glossary(data.get("glossary", {}))
    return {"status": "ok"}

ACTIVE_JOBS: Dict[str, Any] = {}
WS_CONNECTIONS: Dict[str, List[WebSocket]] = {}
main_loop = None

@app.on_event("startup")
async def startup_loop():
    global main_loop
    main_loop = asyncio.get_running_loop()

@app.websocket("/ws/progress/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    await websocket.accept()
    if job_id not in WS_CONNECTIONS:
        WS_CONNECTIONS[job_id] = []
    WS_CONNECTIONS[job_id].append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except:
        if job_id in WS_CONNECTIONS:
            WS_CONNECTIONS[job_id].remove(websocket)

@app.get("/active-job/{job_id}")
async def get_active_job(job_id: str):
    return ACTIVE_JOBS.get(job_id, {"status": "not_found"})

@app.post("/translate")
async def start_translation(file_url: str = Form(...), filename: str = Form(...), provider: str = Form(...), direction: str = Form(...), username: str = Depends(get_current_username)):
    job_id = str(uuid.uuid4())
    ext = os.path.splitext(filename)[1].lower()
    ACTIVE_JOBS[job_id] = {"status": "processing", "current": 0, "total": 1, "text": "Downloading...", "filename": filename, "logs": [], "cost": 0.0}
    input_path = os.path.join("/tmp", f"{job_id}{ext}")
    output_path = os.path.join("/tmp", f"{job_id}_out{ext}")
    
    async with httpx.AsyncClient(timeout=600.0) as client:
        async with client.stream("GET", file_url) as res:
            with open(input_path, "wb") as f:
                for chunk in res.aiter_bytes():
                    f.write(chunk)
    
    db_manager.log_job(job_id, username, filename, provider, direction, "processing", "")
    
    # Vercel Serverless 대응: 글로벌 변수 대신 요청 시점에 즉시 루프 획득
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _sync_translation, job_id, input_path, output_path, provider, direction, ext, username, loop)
    return {"job_id": job_id}

def _sync_translation(job_id, input_path, output_path, provider, direction, ext, username, loop):
    try:
        dir_info = DIRECTION_MAP[direction]
        def cb(c, t, txt="", log=""):
            if job_id in ACTIVE_JOBS:
                ACTIVE_JOBS[job_id].update({"current": c, "total": t, "text": txt})
                if log:
                    ACTIVE_JOBS[job_id]["logs"].append(log)
                if job_id in WS_CONNECTIONS:
                    for ws in WS_CONNECTIONS[job_id]:
                        loop.call_soon_threadsafe(lambda: asyncio.create_task(ws.send_json({"current": c, "total": t, "text": txt, "log": log})))
        
        print(f"DEBUG: Starting translation for job {job_id} with {provider}")
        
        api_key = os.getenv("GEMINI_API_KEY")
        if provider == "Gemini" and not api_key:
            raise Exception("GEMINI_API_KEY가 서버에 설정되지 않았습니다.")
            
        if provider == "Gemini":
            translator = GeminiTranslator(api_key, dir_info["src_code"], dir_info["tgt_code"], dir_info["src_lang_name"], dir_info["lang_name"], load_glossary(), "")
        else:
            translator = FreeTranslator(dir_info["src_code"], dir_info["tgt_code"], dir_info["src_lang_name"], dir_info["lang_name"], load_glossary(), "")
        
        processor = PDFProcessor(translator) if ext == ".pdf" else PPTXProcessor(translator)
        print(f"DEBUG: Processing file: {input_path}")
        
        if processor.process(input_path, output_path, cb):
            print(f"DEBUG: Processing success. Uploading {output_path} to Vercel Blob...")
            out_key = f"results/{job_id}/{os.path.basename(output_path)}"
            
            try:
                # Cloudflare R2에 결과물 업로드 (가벼운 minio 사용)
                account_id = os.getenv("R2_ACCOUNT_ID")
                access_key = os.getenv("R2_ACCESS_KEY_ID")
                secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
                bucket_name = os.getenv("R2_BUCKET_NAME", "uploads")
                public_domain = os.getenv("R2_PUBLIC_DOMAIN")
                
                if not account_id or not access_key or not secret_key or not public_domain:
                    raise Exception("R2 credentials missing on server")
                
                from minio import Minio
                minio_client = Minio(
                    f"{account_id}.r2.cloudflarestorage.com",
                    access_key=access_key,
                    secret_key=secret_key,
                    secure=True
                )
                
                content_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation" if ext == ".pptx" else "application/pdf"
                
                # R2 업로드 실행
                minio_client.fput_object(
                    bucket_name,
                    out_key,
                    output_path,
                    content_type=content_type
                )
                
                base_url = public_domain[:-1] if public_domain.endswith('/') else public_domain
                final_url = f"{base_url}/{out_key}"
                
                print(f"DEBUG: Upload complete to Cloudflare R2 (via MinIO). Public URL: {final_url}")
                ACTIVE_JOBS[job_id].update({"status": "completed", "text": "완료!", "output_path": final_url})
                db_manager.log_job(job_id, username, ACTIVE_JOBS[job_id]["filename"], provider, direction, "completed", final_url)
            except Exception as upload_err:
                raise Exception(f"결과물 업로드 실패: {str(upload_err)}")
        else:
            raise Exception("문서 처리 중 알 수 없는 오류가 발생했습니다.")
            
    except Exception as e:
        error_msg = str(e)
        print(f"CRITICAL ERROR in _sync_translation: {error_msg}")
        if job_id in ACTIVE_JOBS:
            ACTIVE_JOBS[job_id].update({
                "status": "failed",
                "text": f"오류: {error_msg}"
            })
    finally:
        if os.path.exists(input_path):
            os.remove(input_path)

@app.get("/history")
async def get_history(user: dict = Depends(get_current_user)):
    return db_manager.get_jobs(user["username"]) if user["role"] != "admin" else db_manager.get_jobs()

@app.get("/download/{job_id}")
async def download_file(job_id: str):
    job = ACTIVE_JOBS.get(job_id)
    if job and job.get("output_path"):
        return RedirectResponse(url=job["output_path"])
    if supabase:
        res = supabase.table("jobs").select("output_path").eq("job_id", job_id).execute()
        if res.data:
            return RedirectResponse(url=res.data[0]["output_path"])
    raise HTTPException(status_code=404)
