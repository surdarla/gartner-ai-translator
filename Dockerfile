FROM python:3.12-slim

# 작업 디렉토리 설정
WORKDIR /app

# 기본 시스템 컬(curl) 모듈 설치
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# 파이썬 가장 최신형 패키지 매니저(UV) 설치 환경
ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh
ENV PATH="/root/.local/bin/:$PATH"

# 필요한 소스 복사 (서버에서는 이 4가지 파일 세트만 있으면 끝)
COPY pyproject.toml .python-version edtech_glossary.json ./
COPY py ./py

# UV 동기화 인스톨
RUN uv sync

# Streamlit 전용 포트 노출
EXPOSE 8501

# 컨테이너 헬스체크 설정
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# 기본 서버 실행 명령어 박제
ENTRYPOINT ["uv", "run", "streamlit", "run", "py/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
