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

# Add back/src to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import load_glossary, save_glossary, DIRECTION_MAP, get_base_dir
from core.translators import GeminiTranslator, ClaudeTranslator, FreeTranslator, UpstageTranslator
from core.document_processor import PDFProcessor, PPTXProcessor
from core.db import DatabaseManager, supabase

db_manager = DatabaseManager()

# Auto-timeout stale processing jobs on startup
db_manager.auto_timeout_stale_jobs(minutes=10)

app = FastAPI(title="AI Document Translator API")

# Periodic auto-timeout background task
@app.on_event("startup")
async def startup_periodic_timeout():
    async def _auto_timeout_loop():
        while True:
            await asyncio.sleep(300)  # Every 5 minutes
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

# Google SSO Setup
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID") or os.getenv("CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET") or os.getenv("CLIENT_SECRET")

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# --- Database Operations ---

def get_users_db():
    if supabase is None:
        print("ERROR: Supabase client is None. Check env vars.")
        return {}
    try:
        response = supabase.table("users").select("*").execute()
        return {user["email"]: user for user in response.data}
    except Exception as e:
        print(f"Error fetching users: {e}")
        return {}

def save_users_db(user_data):
    if supabase is None: return
    try:
        supabase.table("users").upsert(user_data).execute()
    except Exception as e:
        print(f"Error saving user: {e}")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid auth credentials")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid auth credentials")
    return {"username": username, "role": payload.get("role", "user")}

async def get_current_username(current_user: dict = Depends(get_current_user)):
    return current_user["username"]

# --- Authentication Endpoints ---

@app.post("/auth/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    users = get_users_db()
    user = users.get(form_data.username)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    password_str = user.get("password")
    if not password_str:
        raise HTTPException(status_code=400, detail="Please login with Google for this account")

    if not bcrypt.checkpw(form_data.password.encode("utf-8"), password_str.encode("utf-8")):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    token = jwt.encode({"sub": form_data.username, "role": user.get("role", "user")}, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}

def get_frontend_url(request: Request = None):
    url = os.getenv("FRONTEND_URL")
    if os.getenv("VERCEL") == "1" and request:
        detected_url = f"{request.url.scheme}://{request.url.netloc}"
        return detected_url.replace("/api", "").rstrip("/")
    return (url or "http://localhost:5173").rstrip("/")

def get_backend_url():
    url = os.getenv("BACKEND_URL")
    return (url or "http://localhost:8000").rstrip("/")

@app.get("/auth/google/login")
async def google_login(request: Request):
    import secrets
    from urllib.parse import urlencode
    
    redirect_uri = f"{get_backend_url()}/auth/google/callback"
    nonce = secrets.token_urlsafe(32)
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
    if error:
        raise HTTPException(status_code=400, detail=f"Google OAuth error: {error}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    try:
        nonce, signature = state.rsplit(".", 1)
        expected_sig = hmac.new(SECRET_KEY.encode(), nonce.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            raise ValueError("Invalid state")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    redirect_uri = f"{get_backend_url()}/auth/google/callback"

    async with httpx.AsyncClient() as client:
        # Token exchange
        token_res = await client.post("https://oauth2.googleapis.com/token", data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        })
        token_data = token_res.json()
        if "access_token" not in token_data:
            raise HTTPException(status_code=400, detail="Failed to exchange token")

        # User info fetch
        userinfo_res = await client.get("https://www.googleapis.com/oauth2/v3/userinfo", 
                                        headers={"Authorization": f"Bearer {token_data['access_token']}"})
        user_info = userinfo_res.json()
    
    email = user_info.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Google account has no email")

    save_users_db({
        "email": email,
        "name": user_info.get("name", email),
        "sso": "google",
        "role": "user"
    })

    jwt_token = jwt.encode({"sub": email, "role": "user", "name": user_info.get("name")}, SECRET_KEY, algorithm=ALGORITHM)
    return RedirectResponse(url=f"{get_frontend_url(request)}/login?token={jwt_token}")

# --- Translation & Core Logic ---

@app.get("/auth/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return current_user

@app.get("/glossary")
async def get_glossary(username: str = Depends(get_current_username)):
    return load_glossary()

class GlossaryUpdate(BaseModel):
    glossary: Dict[str, str]

@app.post("/glossary")
async def update_glossary(data: GlossaryUpdate, username: str = Depends(get_current_username)):
    save_glossary(data.glossary)
    return {"message": "Glossary saved successfully"}

class ChatRequest(BaseModel):
    message: str

@app.post("/chat")
async def chat_with_ai(req: ChatRequest, username: str = Depends(get_current_username)):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"response": "GEMINI_API_KEY가 설정되지 않았습니다."}
    
    client = genai.Client(api_key=api_key)
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"사용자 질문: {req.message}",
            config=types.GenerateContentConfig(temperature=0.7)
        )
        return {"response": response.text.strip()}
    except Exception as e:
        return {"response": f"오류 발생: {str(e)}"}

ACTIVE_JOBS: Dict[str, Dict[str, Any]] = {}
WS_CONNECTIONS: Dict[str, List[WebSocket]] = {}
main_loop = None

@app.on_event("startup")
async def startup_event():
    global main_loop
    main_loop = asyncio.get_running_loop()

def update_job_progress(job_id: str, current: int, total: int, text: str = "", log_msg: str = ""):
    if job_id not in ACTIVE_JOBS: return
    job = ACTIVE_JOBS[job_id]
    job.update({"current": current, "total": total})
    if text: job["text"] = text
    if log_msg: job["logs"].append(log_msg)
    
    if job_id in WS_CONNECTIONS and main_loop:
        msg = {"current": current, "total": total, "text": job["text"], "cost": job.get("cost", 0.0), "log": log_msg}
        for ws in WS_CONNECTIONS[job_id]:
            main_loop.call_soon_threadsafe(lambda: asyncio.create_task(ws.send_json(msg)))

@app.websocket("/ws/progress/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    await websocket.accept()
    if job_id not in WS_CONNECTIONS: WS_CONNECTIONS[job_id] = []
    WS_CONNECTIONS[job_id].append(websocket)
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect:
        WS_CONNECTIONS[job_id].remove(websocket)

@app.get("/active-job/{job_id}")
async def get_active_job(job_id: str, username: str = Depends(get_current_username)):
    if job_id not in ACTIVE_JOBS: raise HTTPException(status_code=404, detail="Job not found")
    return ACTIVE_JOBS[job_id]

@app.post("/translate")
async def start_translation(
    file_url: str = Form(...),
    filename: str = Form(...),
    provider: str = Form(...),
    direction: str = Form(...),
    api_key: str = Form(""),
    system_instruction: str = Form("Translate business tone."),
    test_mode: bool = Form(False),
    username: str = Depends(get_current_username)
):
    job_id = str(uuid.uuid4())
    ext = os.path.splitext(filename)[1].lower()
    if ext not in [".pdf", ".pptx"]:
        raise HTTPException(status_code=400, detail="Unsupported format")

    ACTIVE_JOBS[job_id] = {
        "status": "processing", "current": 0, "total": 1, "text": "Downloading...",
        "logs": [], "output_path": None, "filename": filename, "file_size": 0, "cost": 0.0
    }

    input_path = os.path.join("/tmp", f"{job_id}{ext}")
    try:
        async with httpx.AsyncClient(timeout=600.0) as client:
            async with client.stream("GET", file_url) as res:
                if res.status_code != 200: raise Exception("Download failed")
                with open(input_path, "wb") as f:
                    size = 0
                    for chunk in res.aiter_bytes():
                        f.write(chunk)
                        size += len(chunk)
                ACTIVE_JOBS[job_id]["file_size"] = size
    except Exception as e:
        ACTIVE_JOBS[job_id]["status"] = "failed"
        raise HTTPException(status_code=500, detail=str(e))

    output_path = os.path.join("/tmp", f"{job_id}_out{ext}")
    db_manager.log_job(job_id, username, filename, provider, direction, "processing", "", file_size=ACTIVE_JOBS[job_id]["file_size"])
    
    # Sync wait for Vercel
    await run_translation_job(job_id, input_path, output_path, provider, direction, api_key, system_instruction, ext, test_mode, username)
    return {"job_id": job_id, "filename": filename}

async def run_translation_job(job_id, input_path, output_path, provider, direction, api_key, system_instruction, ext, test_mode, username):
    if main_loop:
        await main_loop.run_in_executor(None, _sync_translation, job_id, input_path, output_path, provider, direction, api_key, system_instruction, ext, test_mode, username)

def _sync_translation(job_id, input_path, output_path, provider, direction, api_key, system_instruction, ext, test_mode, username):
    dir_info = DIRECTION_MAP[direction]
    def cb(c, t, txt="", log_msg=""):
        update_job_progress(job_id, c, t, txt, log_msg)
        
    try:
        if provider == "Gemini":
            translator = GeminiTranslator(api_key, dir_info["src_code"], dir_info["tgt_code"], dir_info["src_lang_name"], dir_info["lang_name"], load_glossary(), system_instruction)
        elif provider == "Claude":
            translator = ClaudeTranslator(api_key, dir_info["src_code"], dir_info["tgt_code"], dir_info["src_lang_name"], dir_info["lang_name"], load_glossary(), system_instruction)
        elif provider == "Upstage":
            translator = UpstageTranslator(api_key, dir_info["src_code"], dir_info["tgt_code"], dir_info["src_lang_name"], dir_info["lang_name"], load_glossary(), system_instruction)
        else:
            translator = FreeTranslator(dir_info["src_code"], dir_info["tgt_code"], dir_info["src_lang_name"], dir_info["lang_name"], load_glossary(), system_instruction)
            
        processor = PDFProcessor(translator) if ext == ".pdf" else PPTXProcessor(translator)
        success = processor.process(input_path, output_path, cb, test_mode=test_mode)
        
        if success:
            out_filename = os.path.basename(output_path)
            out_storage_path = f"results/{job_id}/{out_filename}"
            with open(output_path, "rb") as f:
                supabase.storage.from("documents").upload(out_storage_path, f)
            res = supabase.storage.from("documents").get_public_url(out_storage_path)
            final_url = res.public_url
            ACTIVE_JOBS[job_id].update({"status": "completed", "output_path": final_url})
            db_manager.log_job(job_id, username, ACTIVE_JOBS[job_id]["filename"], provider, direction, "completed", final_url, file_size=ACTIVE_JOBS[job_id]["file_size"])
        else:
            ACTIVE_JOBS[job_id]["status"] = "failed"
    except Exception as e:
        ACTIVE_JOBS[job_id]["status"] = "failed"
    finally:
        if os.path.exists(input_path): os.remove(input_path)

@app.get("/history")
async def get_history(current_user: dict = Depends(get_current_user)):
    return db_manager.get_jobs(current_user["username"]) if current_user["role"] != "admin" else db_manager.get_jobs()

@app.post("/cancel/{job_id}")
async def cancel_job(job_id: str, username: str = Depends(get_current_username)):
    if job_id in ACTIVE_JOBS: ACTIVE_JOBS[job_id]["status"] = "cancelled"
    db_manager.update_job_status(job_id, "cancelled")
    return {"message": "Cancelled"}

@app.get("/download/{job_id}")
async def download_file(job_id: str):
    job = ACTIVE_JOBS.get(job_id)
    if job and job["status"] == "completed": return RedirectResponse(url=job["output_path"])
    # Fallback to DB
    jobs = db_manager.get_jobs()
    for j in jobs:
        if j["job_id"] == job_id and j["output_path"]: return RedirectResponse(url=j["output_path"])
    raise HTTPException(status_code=404)
