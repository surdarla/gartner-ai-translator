import os
import sys

# 프로젝트 루트(/)를 path에 추가
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# back/src를 path에 추가 (core 모듈 임포트용)
back_src = os.path.join(root_dir, "back", "src")
if back_src not in sys.path:
    sys.path.insert(0, back_src)

# back/src/api를 path에 추가 (main 모듈 직접 임포트용)
back_api = os.path.join(back_src, "api")
if back_api not in sys.path:
    sys.path.insert(0, back_api)

app = None

try:
    # 1. 가장 직접적인 임포트 시도
    from main import app as _app
    app = _app
except ImportError:
    try:
        # 2. 패키지 경로를 통한 임포트 시도
        from api.main import app as _app
        app = _app
    except ImportError:
        # 3. 최후의 수단: 경로를 직접 타격
        import importlib.util
        main_path = os.path.join(back_api, "main.py")
        if os.path.exists(main_path):
            spec = importlib.util.spec_from_file_location("main", main_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            app = module.app

except ImportError as e:
    import traceback
    print(f"CRITICAL: Final import failed: {e}")
    traceback.print_exc()
    raise e

if app is None:
    raise ImportError("Could not find FastAPI 'app' in main.py or api.main.py")

# Vercel이 찾는 변수들 명시
handler = app
application = app

# root_path 설정
app.root_path = "/api"
