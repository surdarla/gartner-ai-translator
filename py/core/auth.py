import os
import logging
import streamlit as st
from streamlit_oauth import OAuth2Component

class AuthManager:
    def __init__(self):
        self._init_session_state()

    def _init_session_state(self):
        if "logged_in" not in st.session_state:
            st.session_state.logged_in = False
        if "role" not in st.session_state:
            st.session_state.role = None
        if "username" not in st.session_state:
            st.session_state.username = None

    def login(self, username, password):
        if username == "user" and password == "1234":
            st.session_state.logged_in = True
            st.session_state.role = "user"
            st.session_state.username = username
            logging.info(f"사용자 로그인 성공: {username}")
            return True
        elif username == "admin" and password == "admin123":
            st.session_state.logged_in = True
            st.session_state.role = "admin"
            st.session_state.username = username
            logging.info(f"관리자 로그인 성공: {username}")
            return True
        return False

    def logout(self):
        logging.info(f"로그아웃: {st.session_state.username}")
        st.session_state.logged_in = False
        st.session_state.role = None
        st.session_state.username = None

    def is_logged_in(self):
        return st.session_state.logged_in

    def get_role(self):
        return st.session_state.role

    def get_username(self):
        return st.session_state.username

    def render_login_guard(self):
        if self.is_logged_in():
            return True

        st.title("🔒 로그인 (Gartner AI Translator)")
        tab1, tab2, tab3 = st.tabs(["일반 로그인", "Google SSO", "Microsoft SSO"])
        
        with tab1:
            with st.form("login_form"):
                st.markdown("사내 번역 시스템에 접근하려면 소속 및 권한 확인을 위해 로그인하세요.")
                st.info("💡 접속 가이드 (체험판)\n- 👨‍💻 일반 사용자: ID `user` / PW `1234`\n- 👑 시스템 관리자: ID `admin` / PW `admin123`")
                u_input = st.text_input("Username")
                p_input = st.text_input("Password", type="password")
                submit = st.form_submit_button("로그인")
                if submit:
                    if self.login(u_input, p_input):
                        st.rerun()
                    else:
                        logging.warning(f"로그인 실패 시도: {u_input}")
                        st.error("❌ 아이디 또는 비밀번호가 올바르지 않습니다.")
                        
        with tab2:
            st.subheader("Google 계정으로 로그인")
            GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
            GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
            if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
                google_oauth2 = OAuth2Component(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, "https://accounts.google.com/o/oauth2/v2/auth", "https://oauth2.googleapis.com/token", "https://oauth2.googleapis.com/token", "https://oauth2.googleapis.com/revoke")
                result = google_oauth2.authorize_button("Google Login", "http://localhost:8501/oauth2callback", scope="email profile")
                if result and "token" in result:
                    st.session_state.logged_in = True
                    st.session_state.role = "user"
                    st.session_state.username = "Google User"
                    st.rerun()
            else:
                st.warning("⚠️ Google SSO가 설정되지 않았습니다. 관리자에게 문의하세요 (.env 파일에 GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET 설정 필요).")

        with tab3:
            st.subheader("Microsoft 계정으로 로그인")
            MS_CLIENT_ID = os.environ.get("MICROSOFT_CLIENT_ID", "")
            MS_CLIENT_SECRET = os.environ.get("MICROSOFT_CLIENT_SECRET", "")
            MS_TENANT_ID = os.environ.get("MICROSOFT_TENANT_ID", "common")
            if MS_CLIENT_ID and MS_CLIENT_SECRET:
                ms_oauth2 = OAuth2Component(MS_CLIENT_ID, MS_CLIENT_SECRET, f"https://login.microsoftonline.com/{MS_TENANT_ID}/oauth2/v2.0/authorize", f"https://login.microsoftonline.com/{MS_TENANT_ID}/oauth2/v2.0/token", f"https://login.microsoftonline.com/{MS_TENANT_ID}/oauth2/v2.0/token", "")
                result = ms_oauth2.authorize_button("Microsoft Login", "http://localhost:8501/oauth2callback", scope="openid email profile")
                if result and "token" in result:
                    st.session_state.logged_in = True
                    st.session_state.role = "user"
                    st.session_state.username = "Microsoft User"
                    st.rerun()
            else:
                st.warning("⚠️ Microsoft SSO가 설정되지 않았습니다. 관리자에게 문의하세요 (.env 파일에 MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET 설정 필요).")
        
        st.stop()
        return False
