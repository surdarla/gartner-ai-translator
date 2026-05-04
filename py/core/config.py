import os
import json
import logging
from pathlib import Path

# 공통 방향성 맵핑
DIRECTION_MAP = {
    "한국어 → English":  {"src_code": "ko", "tgt_code": "en", "src_lang_name": "Korean",   "lang_name": "Business English",  "src_regex": "[가-힣]"},
    "한국어 → 日本語":   {"src_code": "ko", "tgt_code": "ja", "src_lang_name": "Korean",   "lang_name": "Business Japanese", "src_regex": "[가-힣]"},
    "English → 한국어":  {"src_code": "en", "tgt_code": "ko", "src_lang_name": "English",  "lang_name": "Professional Korean", "src_regex": "[a-zA-Z]"},
    "日本語 → 한국어":   {"src_code": "ja", "tgt_code": "ko", "src_lang_name": "Japanese", "lang_name": "Professional Korean", "src_regex": "[ぁ-ゖァ-ヶ一-鿿]"},
}

def get_base_dir():
    """프로젝트 루트 디렉토리를 반환합니다."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_glossary_path():
    return os.path.join(get_base_dir(), "edtech_glossary.json")

def load_glossary():
    path = get_glossary_path()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_glossary(new_glossary):
    path = get_glossary_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(new_glossary, f, ensure_ascii=False, indent=4)
        
def get_log_path():
    log_dir = os.path.join(get_base_dir(), "logs")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "app.log")

def get_db_path():
    log_dir = os.path.join(get_base_dir(), "logs")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, "usage.db")

def setup_logging():
    logging.basicConfig(
        filename=get_log_path(),
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
