# Gartner AI Translator

현대적인 AI 기반 문서 번역 서비스 (FastAPI + React). 사내 팀원 누구나 드래그 앤 드롭으로 PDF/PPTX 문서를 **서식/레이아웃 유지**하며 번역할 수 있습니다.

---

## 🐳 Docker Deployment (One-line)

Docker와 Docker Compose가 설치되어 있으면 다음 명령어로 전체 시스템(Backend + Frontend)을 한 번에 배포할 수 있습니다.

```bash
docker-compose up -d --build
```

- **Frontend:** `http://localhost` (80 포트)
- **Backend API:** `http://localhost:8000`
- **주요 기능:** 다국어 지원(KO, EN, JA), 번역 히스토리 DB, 테스트 모드, 실시간 로그 스트리밍.

---

## 🏗️ 로컬 개발 환경 실행

### 1. Backend (FastAPI)
```bash
uv run uvicorn py.api.main:app --port 8000 --reload
```

### 2. Frontend (React/Vite)
```bash
cd frontend
npm install
npm run dev
```

---

## ⚙️ Confluence 연동 및 사용 방법

이 프로젝트는 Confluence 페이지 내부에 Iframe 매크로를 사용하여 삽입되도록 설계되었습니다.

1. **Confluence 위키에 임베딩하기**
   - Confluence 페이지 편집 모드에서 **Iframe 매크로**를 추가합니다.
   - URL 입력란에 서버 주소를 입력합니다 (예: `http://[서버IP]`).
   - 현대적인 React 기반 UI로 깔끔하게 위젯처럼 연동됩니다.

2. **팀원용 사용 가이드**
   - 접속 후 부여받은 계정으로 로그인합니다.
   - 번역할 파일을 업로드하고 언어와 엔진을 선택합니다.
   - **Test Run**으로 일부 페이지 번역 품질을 먼저 확인해볼 수 있습니다.
   *※ 용어집(Glossary) 관리를 통해 사내 고유 명사의 번역을 고정할 수 있습니다.*
