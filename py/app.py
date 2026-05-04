import os
import sys
import tempfile
import pandas as pd
import streamlit as st
import traceback

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from py.core.config import DIRECTION_MAP, load_glossary, save_glossary, setup_logging, get_log_path
from py.core.auth import AuthManager
from py.core.db import DatabaseManager
from py.core.translators import GeminiTranslator, ClaudeTranslator, FreeTranslator
from py.core.document_processor import PDFProcessor, PPTXProcessor

st.set_page_config(page_title="Gartner AI Translator", page_icon="🤖", layout="wide")
setup_logging()

db = DatabaseManager()
auth = AuthManager()

if not auth.render_login_guard():
    st.stop()

# --- Main App ---

st.sidebar.title("🤖 번역 AI 선택")
provider = st.sidebar.radio("엔진을 선택하세요", ["Free (Google Translator)", "Gemini", "Claude"], index=0)

api_key = ""
if provider == "Gemini":
    api_key = st.sidebar.text_input("Gemini API Key", type="password", value=os.environ.get("GEMINI_API_KEY", ""))
elif provider == "Claude":
    api_key = st.sidebar.text_input("Claude API Key", type="password", value=os.environ.get("ANTHROPIC_API_KEY", ""))

if st.sidebar.button("로그아웃"):
    auth.logout()
    st.rerun()

st.title("📄 Gartner AI Translator")
st.markdown("PDF 및 PPTX 문서를 원본 디자인 그대로 유지하며 번역합니다.")

# ... Admin Dashboard ...
if auth.get_role() == "admin":
    with st.expander("🛠 시스템 관리자 대시보드"):
        st.subheader("사용자 활동 로그")
        df_logs = db.get_recent_logs()
        if df_logs is not None:
            st.dataframe(df_logs, use_container_width=True)
            
        st.subheader("에듀테크 용어집 관리")
        glossary = load_glossary()
        glossary_df = pd.DataFrame(list(glossary.items()), columns=["원문", "번역"])
        edited_df = st.data_editor(glossary_df, num_rows="dynamic", use_container_width=True)
        if st.button("용어집 저장"):
            new_glossary = {row["원문"]: row["번역"] for _, row in edited_df.iterrows() if row["원문"]}
            save_glossary(new_glossary)
            st.success("용어집이 저장되었습니다.")

direction = st.selectbox("번역 방향", list(DIRECTION_MAP.keys()))
system_instruction = st.text_area("번역 지침 (System Prompt)", "Translate maintaining a professional business tone.", height=100)
uploaded_file = st.file_uploader("파일 업로드 (PDF 또는 PPTX)", type=["pdf", "pptx"])

if st.button("🚀 번역 시작"):
    if not uploaded_file:
        st.warning("파일을 업로드해주세요.")
    elif provider != "Free (Google Translator)" and not api_key:
        st.warning(f"{provider} API Key를 입력해주세요.")
    else:
        st.info("번역을 시작합니다. 화면을 닫지 마세요.")
        my_bar = st.progress(0.0, text="준비 중...")
        
        def progress_callback(current, total, text=""):
            percent = min(max(current / max(total, 1), 0.0), 1.0)
            if text:
                st.session_state._prog_text = text
            else:
                st.session_state._prog_text = st.session_state.get('_prog_text', '번역 중...')
            my_bar.progress(percent, text=st.session_state._prog_text)

        dir_info = DIRECTION_MAP[direction]
        glossary = load_glossary()
        
        try:
            if provider == "Gemini":
                translator = GeminiTranslator(api_key, dir_info["src_code"], dir_info["tgt_code"], dir_info["src_lang_name"], dir_info["lang_name"], glossary, system_instruction)
            elif provider == "Claude":
                translator = ClaudeTranslator(api_key, dir_info["src_code"], dir_info["tgt_code"], dir_info["src_lang_name"], dir_info["lang_name"], glossary, system_instruction)
            else:
                translator = FreeTranslator(dir_info["src_code"], dir_info["tgt_code"], dir_info["src_lang_name"], dir_info["lang_name"], glossary, system_instruction)
        except Exception as e:
            st.error(f"AI 클라이언트 초기화 실패: {e}")
            st.stop()

        ext = os.path.splitext(uploaded_file.name)[1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_in:
            tmp_in.write(uploaded_file.read())
            input_path = tmp_in.name
            
        output_path = input_path.replace(ext, f"_translated{ext}")
        
        processor = None
        if ext == ".pdf":
            processor = PDFProcessor(translator)
        elif ext == ".pptx":
            processor = PPTXProcessor(translator)
            
        if processor:
            try:
                success = processor.process(input_path, output_path, progress_callback)
                if success:
                    my_bar.progress(1.0, text="완료!")
                    st.success("🎉 번역이 완료되었습니다!")
                    with open(output_path, "rb") as f:
                        st.download_button(
                            label="📥 번역본 다운로드",
                            data=f.read(),
                            file_name=f"translated_{uploaded_file.name}",
                            mime="application/octet-stream"
                        )
                    db.log_usage(auth.get_username(), "Translate", provider, direction, ext)
                else:
                    st.error("번역 중 오류가 발생했습니다. 로그를 확인하세요.")
            except Exception as e:
                st.error(f"오류 발생: {e}")
                st.code(traceback.format_exc())
            finally:
                if os.path.exists(input_path): os.remove(input_path)
                if os.path.exists(output_path): os.remove(output_path)
        else:
            st.error("지원하지 않는 파일 형식입니다.")
