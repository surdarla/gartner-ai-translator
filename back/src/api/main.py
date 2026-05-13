import os
import sys
import json
import uuid
import tempfile
import asyncio
from dotenv import load_dotenv
from typing import Dict, Any, List

# Python 3.11+ has tomllib. If not available, use tomli.
try:
    import tomllib
except ImportError:
    import tomli as tomllib

import bcrypt
import jwt
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from google import genai
from google.genai import types

# Add back/src to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import load_glossary, save_glossary, DIRECTION_MAP, get_base_dir
from core.translators import GeminiTranslator, ClaudeTranslator, FreeTranslator, UpstageTranslator
from core.document_processor import PDFProcessor, PPTXProcessor
from core.db import DatabaseManager

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

SECRET_KEY = "supersecretkey"  # In production, move to env
ALGORITHM = "HS256"

# Google SSO Setup
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID") or os.getenv("CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET") or os.getenv("CLIENT_SECRET")

oauth = OAuth()
oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_users_db():
    from core.config import get_back_dir
    users_path = os.path.join(get_back_dir(), "data", "users.json")
    if not os.path.exists(users_path):
        return {}
    with open(users_path, "r", encoding="utf-8") as f:
        return json.load(f)

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

@app.post("/auth/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    users = get_users_db()
    user = users.get(form_data.username)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    hashed_password = user.get("password", "").encode("utf-8")
    if not bcrypt.checkpw(form_data.password.encode("utf-8"), hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    token = jwt.encode({"sub": form_data.username, "role": "admin" if form_data.username == "admin" else "user"}, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}

def save_users_db(users):
    from core.config import get_back_dir
    users_path = os.path.join(get_back_dir(), "data", "users.json")
    with open(users_path, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4, ensure_ascii=False)

@app.get("/auth/google/login")
async def google_login(request: Request):
    # Use the origin of the request for redirect back
    origin = request.headers.get("origin") or f"{request.url.scheme}://{request.url.netloc}"
    # But for Authlib redirect_uri must be fixed or registered
    redirect_uri = "http://localhost:8000/auth/google/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)

@app.get("/auth/google/callback")
async def google_callback(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get('userinfo')
        if not user_info:
            raise HTTPException(status_code=400, detail="Google authentication failed")
        
        email = user_info.get("email")
        name = user_info.get("name")
        
        # Auto-register user if not exists
        users = get_users_db()
        if email not in users:
            users[email] = {
                "email": email,
                "name": name,
                "password": "", # No password for SSO users
                "sso": "google"
            }
            save_users_db(users)
        
        jwt_token = jwt.encode({"sub": email, "role": "user", "name": name}, SECRET_KEY, algorithm=ALGORITHM)
        
        # Redirect back to frontend. Try to determine frontend URL.
        # If in docker-compose, port 80 is mapped to 5173. 
        # But if user is on localhost:5173 directly, we should redirect there.
        # We'll use the Referer or a fixed env var. For now, let's try to be smart.
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost")
        return RedirectResponse(url=f"{frontend_url}/login?token={jwt_token}")
    except OAuthError as e:
        raise HTTPException(status_code=400, detail=str(e))

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
    # Reload .env to pick up changes in real-time
    load_dotenv(os.path.join(get_base_dir(), ".env"), override=True)
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"response": "GEMINI_API_KEY가 설정되지 않아 챗봇을 사용할 수 없습니다."}
    
    client = genai.Client(api_key=api_key)
    system_prompt = f"""당신은 AI 문서 번역 플랫폼의 헬프봇입니다. 다음 정보를 바탕으로 사용자에게 친절하고 간결하게 답변하세요.
- 사용법: 파일을 대시보드에 드래그 앤 드롭 후 '번역 시작' 버튼 클릭.
- 지원 형식: PDF, PPTX. 
- 엔진: Gemini, Claude, Upstage, Free(Google).
- 용어집(Glossary): 사내 약어나 특정 용어를 고정 번역할 때 사용.
- 문제 해결: PPTX 레이아웃이 깨지면 다운로드 후 폰트 크기 조절 권장.
한국어로 질문하면 한국어로, 영어로 질문하면 영어로 답변하세요.

사용자 질문: {req.message}"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=system_prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=500,
                thinking_config=types.ThinkingConfig(thinking_budget=0)
            )
        )
        return {"response": response.text.strip()}
    except Exception as e:
        return {"response": f"죄송합니다. 챗봇 처리 중 오류가 발생했습니다: {str(e)}"}

# Background job manager
ACTIVE_JOBS: Dict[str, Dict[str, Any]] = {}
WS_CONNECTIONS: Dict[str, List[WebSocket]] = {}

# Global loop reference to use from background threads
main_loop = None

@app.on_event("startup")
async def startup_event():
    global main_loop
    main_loop = asyncio.get_running_loop()

def update_job_progress(job_id: str, current: int, total: int, text: str = "", log_msg: str = ""):
    if job_id not in ACTIVE_JOBS:
        return
    job = ACTIVE_JOBS[job_id]
    job["current"] = current
    job["total"] = total
    if text:
        job["text"] = text
    if log_msg:
        job["logs"].append(log_msg)
    
    # Broadcast to connected websockets using the captured main loop
    if job_id in WS_CONNECTIONS and main_loop:
        msg = {
            "current": current,
            "total": total,
            "text": job["text"],
            "cost": job.get("cost", 0.0),
            "log": log_msg,
            "category": log_msg.split(']')[0][1:] if ']' in log_msg else None
        }
        for ws in WS_CONNECTIONS[job_id]:
            main_loop.call_soon_threadsafe(
                lambda: asyncio.create_task(ws.send_json(msg))
            )

@app.websocket("/ws/progress/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    await websocket.accept()
    
    # Send initial state/logs if job exists
    if job_id in ACTIVE_JOBS:
        job = ACTIVE_JOBS[job_id]
        await websocket.send_json({
            "current": job["current"],
            "total": job["total"],
            "text": job["text"],
            "cost": job.get("cost", 0.0),
            "log": "Restored session logs..."
        })
        for prev_log in job["logs"]:
            await websocket.send_json({
                "current": job["current"],
                "total": job["total"],
                "text": job["text"],
                "cost": job.get("cost", 0.0),
                "log": prev_log
            })

    if job_id not in WS_CONNECTIONS:
        WS_CONNECTIONS[job_id] = []
    WS_CONNECTIONS[job_id].append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        WS_CONNECTIONS[job_id].remove(websocket)

@app.get("/active-job/{job_id}")
async def get_active_job(job_id: str, username: str = Depends(get_current_username)):
    if job_id not in ACTIVE_JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    return ACTIVE_JOBS[job_id]

@app.post("/translate")
async def start_translation(
    file: UploadFile = File(...),
    provider: str = Form(...),
    direction: str = Form(...),
    api_key: str = Form(""),
    system_instruction: str = Form("Translate maintaining a professional business tone."),
    test_mode: bool = Form(False),
    username: str = Depends(get_current_username)
):
    job_id = str(uuid.uuid4())
    
    # Get actual file size
    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)

    ACTIVE_JOBS[job_id] = {
        "status": "processing",
        "current": 0,
        "total": 1,
        "text": "준비 중...",
        "logs": [],
        "output_path": None,
        "filename": file.filename,
        "file_size": file_size,
        "cost": 0.0
    }
    
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".pdf", ".pptx"]:
        raise HTTPException(status_code=400, detail="지원하지 않는 파일 형식입니다.")
        
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_in:
        tmp_in.write(await file.read())
        input_path = tmp_in.name
        
    # output/ directory in root
    output_dir = os.path.join(get_base_dir(), "output")
    os.makedirs(output_dir, exist_ok=True)
    
    # Save the file name properly with Job ID
    clean_name = os.path.basename(file.filename).replace(' ', '_')
    output_path = os.path.join(output_dir, f"{job_id}_translated_{clean_name}")
    
    # Log to DB initially
    db_manager.log_job(job_id, username, file.filename, provider, direction, "processing", "", file_size=file_size)
    db_manager.log_usage(username, "start_translation", provider, direction, ext)

    # Run in background thread
    asyncio.create_task(run_translation_job(job_id, input_path, output_path, provider, direction, api_key, system_instruction, ext, test_mode, username))
    
    return {"job_id": job_id, "filename": file.filename}

async def run_translation_job(job_id, input_path, output_path, provider, direction, api_key, system_instruction, ext, test_mode, username):
    if main_loop:
        await main_loop.run_in_executor(None, _sync_translation, job_id, input_path, output_path, provider, direction, api_key, system_instruction, ext, test_mode, username)

def _sync_translation(job_id, input_path, output_path, provider, direction, api_key, system_instruction, ext, test_mode, username):
    dir_info = DIRECTION_MAP[direction]
    glossary = load_glossary()
    
    def cb(c, t, txt="", log_msg=""):
        # Check if cancel was requested
        if job_id in ACTIVE_JOBS and ACTIVE_JOBS[job_id].get("cancel_requested"):
            raise InterruptedError("Translation cancelled by user")
        # Estimate cost based on processed characters
        rates = {
            "Gemini": 0.0001,  # $0.1 per 1M chars
            "Claude": 0.015,   # $15 per 1M chars
            "Upstage": 0.0002, # $0.2 per 1M chars
            "Free": 0.0
        }
        rate = rates.get(provider, 0.0)
        if txt and job_id in ACTIVE_JOBS:
            # Simple heuristic: increment cost per callback
            ACTIVE_JOBS[job_id]["cost"] += (2000 / 1000) * rate
        update_job_progress(job_id, c, t, txt, log_msg)
        
    try:
        if provider == "Gemini":
            translator = GeminiTranslator(api_key, dir_info["src_code"], dir_info["tgt_code"], dir_info["src_lang_name"], dir_info["lang_name"], glossary, system_instruction)
        elif provider == "Claude":
            translator = ClaudeTranslator(api_key, dir_info["src_code"], dir_info["tgt_code"], dir_info["src_lang_name"], dir_info["lang_name"], glossary, system_instruction)
        elif provider == "Upstage":
            translator = UpstageTranslator(api_key, dir_info["src_code"], dir_info["tgt_code"], dir_info["src_lang_name"], dir_info["lang_name"], glossary, system_instruction)
        else:
            translator = FreeTranslator(dir_info["src_code"], dir_info["tgt_code"], dir_info["src_lang_name"], dir_info["lang_name"], glossary, system_instruction)
            
        translator.src_regex = dir_info.get("src_regex", ".*")
        
        processor = PDFProcessor(translator) if ext == ".pdf" else PPTXProcessor(translator)
        success = processor.process(input_path, output_path, cb, test_mode=test_mode)
        
        # Check cancel after processing
        if job_id in ACTIVE_JOBS and ACTIVE_JOBS[job_id].get("cancel_requested"):
            ACTIVE_JOBS[job_id]["status"] = "cancelled"
            cb_skip = lambda *a, **k: None
            db_manager.log_job(job_id, username, ACTIVE_JOBS[job_id]["filename"], provider, direction, "cancelled", "",
                               file_size=ACTIVE_JOBS[job_id]["file_size"], cost=ACTIVE_JOBS[job_id]["cost"])
        elif success:
            ACTIVE_JOBS[job_id]["status"] = "completed"
            ACTIVE_JOBS[job_id]["output_path"] = output_path
            cb(1, 1, "완료!", "번역이 완료되었습니다.")
            db_manager.log_job(job_id, username, ACTIVE_JOBS[job_id]["filename"], provider, direction, "completed", output_path, 
                               file_size=ACTIVE_JOBS[job_id]["file_size"], cost=ACTIVE_JOBS[job_id]["cost"])
        else:
            ACTIVE_JOBS[job_id]["status"] = "failed"
            cb(1, 1, "오류 발생", "번역 중 오류가 발생했습니다.")
            db_manager.log_job(job_id, username, ACTIVE_JOBS[job_id]["filename"], provider, direction, "failed", "",
                               file_size=ACTIVE_JOBS[job_id]["file_size"], cost=ACTIVE_JOBS[job_id]["cost"])
            
    except InterruptedError:
        ACTIVE_JOBS[job_id]["status"] = "cancelled"
        update_job_progress(job_id, 1, 1, "취소됨", "사용자가 번역을 취소했습니다.")
        db_manager.log_job(job_id, username, ACTIVE_JOBS[job_id]["filename"], provider, direction, "cancelled", "",
                           file_size=ACTIVE_JOBS[job_id]["file_size"], cost=ACTIVE_JOBS[job_id]["cost"])
    except Exception as e:
        ACTIVE_JOBS[job_id]["status"] = "failed"
        cb(1, 1, "오류 발생", f"오류: {str(e)}")
        db_manager.log_job(job_id, username, ACTIVE_JOBS[job_id]["filename"], provider, direction, "failed", "",
                           file_size=ACTIVE_JOBS[job_id]["file_size"], cost=ACTIVE_JOBS[job_id]["cost"])
    finally:
        if os.path.exists(input_path):
            os.remove(input_path)

@app.get("/history")
async def get_history(current_user: dict = Depends(get_current_user)):
    username = current_user["username"]
    role = current_user["role"]
    if role == "admin":
        jobs = db_manager.get_jobs()
    else:
        jobs = db_manager.get_jobs(username)
    return jobs

# --- Admin Endpoints ---
async def require_admin(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

@app.get("/admin/users")
async def get_admin_users(admin: dict = Depends(require_admin)):
    return db_manager.get_user_stats()

@app.get("/admin/user-jobs/{target_username}")
async def get_admin_user_jobs(target_username: str, admin: dict = Depends(require_admin)):
    return db_manager.get_jobs(target_username)

@app.delete("/admin/delete-job/{job_id}")
async def admin_delete_job(job_id: str, admin: dict = Depends(require_admin)):
    success = db_manager.delete_job(job_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete job")
    # Also remove from active jobs if present
    if job_id in ACTIVE_JOBS:
        del ACTIVE_JOBS[job_id]
    return {"message": "Job deleted"}

@app.post("/cancel/{job_id}")
async def cancel_job(job_id: str, username: str = Depends(get_current_username)):
    """Cancel a running translation job."""
    if job_id in ACTIVE_JOBS:
        ACTIVE_JOBS[job_id]["status"] = "cancelled"
        ACTIVE_JOBS[job_id]["cancel_requested"] = True
    db_manager.update_job_status(job_id, "cancelled")
    return {"message": "Job cancelled"}

from fastapi.responses import FileResponse
@app.get("/download/{job_id}")
async def download_file(job_id: str):
    if job_id in ACTIVE_JOBS and ACTIVE_JOBS[job_id]["status"] == "completed" and ACTIVE_JOBS[job_id]["output_path"]:
        return FileResponse(ACTIVE_JOBS[job_id]["output_path"], filename=f"translated_{ACTIVE_JOBS[job_id]['filename']}")
    
    jobs = db_manager.get_jobs()
    for job in jobs:
        if job["job_id"] == job_id and job["status"] == "completed" and job["output_path"]:
            if os.path.exists(job["output_path"]):
                return FileResponse(job["output_path"], filename=f"translated_{job['filename']}")
            else:
                raise HTTPException(status_code=404, detail="File has been deleted or moved")
                
    raise HTTPException(status_code=404, detail="Job not found or not ready")
