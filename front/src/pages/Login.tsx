import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { Navigate, useSearchParams } from 'react-router-dom';
import { Lock, User, LogIn, Globe } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import clsx from 'clsx';
import { getApiUrl } from '../api';

export const Login: React.FC = () => {
  const { t, i18n } = useTranslation();
  const [searchParams] = useSearchParams();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login, token } = useAuth();

  // Handle Google SSO Token from URL
  useEffect(() => {
    const ssoToken = searchParams.get('token');
    if (ssoToken) {
      login(ssoToken);
      // Clean URL
      window.history.replaceState({}, document.title, "/");
    }
  }, [searchParams, login]);

  if (token) return <Navigate to="/" />;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.append('username', username);
      params.append('password', password);
      
      const res = await axios.post(getApiUrl('/auth/login'), params, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
      });
      login(res.data.access_token);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('trans_failed'));
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLogin = () => {
    window.location.href = getApiUrl('/auth/google/login');
  };

  const changeLanguage = (lng: string) => {
    i18n.changeLanguage(lng);
  };

  return (
    <div className="min-h-screen bg-linear-to-br from-slate-900 via-blue-900 to-indigo-900 flex items-center justify-center p-4 relative overflow-hidden">
      {/* Language Switcher */}
      <div className="absolute top-6 right-6 flex gap-2">
        {['ko', 'en', 'ja'].map((lng) => (
          <button
            key={lng}
            onClick={() => changeLanguage(lng)}
            className={clsx(
              "px-3 py-1 rounded-full text-xs font-medium transition-all border",
              i18n.language === lng 
                ? "bg-white/20 border-white/40 text-white shadow-lg" 
                : "bg-black/20 border-white/10 text-white/60 hover:bg-white/10"
            )}
          >
            {lng.toUpperCase()}
          </button>
        ))}
      </div>

      {/* Animated background blobs */}
      <div className="absolute top-0 left-0 w-full h-full -z-10">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-blue-500/20 rounded-full blur-[120px] animate-pulse"></div>
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-purple-500/20 rounded-full blur-[120px] animate-pulse delay-700"></div>
      </div>

      <div className="max-w-md w-full bg-white/10 backdrop-blur-2xl rounded-[2.5rem] p-10 shadow-2xl border border-white/10">
        <div className="text-center mb-10">
          <div className="bg-linear-to-br from-blue-500 to-indigo-600 w-20 h-20 rounded-3xl flex items-center justify-center mx-auto mb-6 shadow-xl transform -rotate-6">
            <Globe className="w-10 h-10 text-white" />
          </div>
          <h2 className="text-4xl font-black text-white tracking-tight mb-2">{t('login_title')}</h2>
          <p className="text-blue-200/60 text-sm font-medium">Enterprise Workspace</p>
        </div>

        <div className="space-y-6">
          <button
            onClick={handleGoogleLogin}
            className="w-full bg-white text-slate-900 rounded-2xl py-4 px-4 font-bold shadow-xl hover:bg-slate-50 transition-all flex items-center justify-center gap-3 group"
          >
            <svg className="w-5 h-5 group-hover:scale-110 transition-transform" viewBox="0 0 24 24">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
            </svg>
            {t('login_google')}
          </button>

          <div className="relative flex items-center py-2">
            <div className="grow border-t border-white/10"></div>
            <span className="shrink mx-4 text-white/30 text-xs font-bold uppercase tracking-widest">OR</span>
            <div className="grow border-t border-white/10"></div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label className="text-white/50 text-xs font-bold ml-1 uppercase tracking-wider">{t('login_id')}</label>
              <div className="relative">
                <User className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-white/30" />
                <input
                  type="text"
                  required
                  className="w-full bg-white/5 border border-white/10 rounded-2xl py-4 pl-12 pr-4 text-white placeholder-white/20 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                  placeholder="admin"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-white/50 text-xs font-bold ml-1 uppercase tracking-wider">{t('login_pw')}</label>
              <div className="relative">
                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-white/30" />
                <input
                  type="password"
                  required
                  className="w-full bg-white/5 border border-white/10 rounded-2xl py-4 pl-12 pr-4 text-white placeholder-white/20 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
            </div>

            {error && (
              <div className="bg-red-500/10 border border-red-500/20 text-red-400 px-4 py-3 rounded-2xl text-sm font-medium text-center animate-shake">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className={clsx(
                "w-full bg-blue-600 hover:bg-blue-500 text-white rounded-2xl py-4 px-4 font-bold shadow-lg shadow-blue-900/40 transition-all flex items-center justify-center gap-2",
                loading ? "opacity-70 cursor-not-allowed" : "hover:-translate-y-1 active:translate-y-0"
              )}
            >
              {loading ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>
                  <LogIn className="w-5 h-5" />
                  {t('login_btn')}
                </>
              )}
            </button>
          </form>
        </div>
      </div>
      
      <p className="absolute bottom-8 text-white/20 text-xs font-medium uppercase tracking-widest">
        © 2026 AI Core Solution • Professional Document Intelligence
      </p>
    </div>
  );
};
