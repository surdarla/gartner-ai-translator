import React, { useState, useEffect } from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { useTranslation } from 'react-i18next';
import { BookOpen, LogOut, Clock, MessageCircle, FileText, X, Trash2, Plus, Save, Shield } from 'lucide-react';
import clsx from 'clsx';
import { HelpChatbot } from './HelpChatbot';

// --- Glossary Modal Component (Global) ---
const GlossaryModal: React.FC<{ isOpen: boolean, onClose: () => void, token: string | null }> = ({ isOpen, onClose, token }) => {
  const { t } = useTranslation();
  const [glossary, setGlossary] = useState<{key: string, value: string}[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen && token) {
      axios.get('http://localhost:8000/glossary', { headers: { Authorization: `Bearer ${token}` } })
        .then(res => setGlossary(Object.entries(res.data).map(([key, value]) => ({ key, value: value as string }))))
        .catch(console.error);
    }
  }, [isOpen, token]);

  if (!isOpen) return null;

  const handleSave = async () => {
    setLoading(true);
    try {
      const data = Object.fromEntries(glossary.filter(i => i.key.trim() !== '').map(i => [i.key, i.value]));
      await axios.post('http://localhost:8000/glossary', { glossary: data }, { headers: { Authorization: `Bearer ${token}` } });
      alert(t('save') + '!');
      onClose();
    } catch (err) {
      alert(t('trans_failed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-60 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-md animate-fade-in">
      <div className="bg-white rounded-[2.5rem] shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col overflow-hidden border border-slate-200">
        <div className="p-8 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
          <div className="flex items-center gap-3">
            <div className="bg-indigo-100 p-2 rounded-xl text-indigo-600">
              <BookOpen className="w-6 h-6" />
            </div>
            <h2 className="text-2xl font-black text-slate-800 tracking-tight">{t('glossary_manage')}</h2>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-slate-200 rounded-full transition-colors"><X className="w-6 h-6 text-slate-400"/></button>
        </div>
        
        <div className="bg-blue-50/80 p-6 border-b border-blue-100/50">
          <p className="text-sm text-blue-900 leading-relaxed font-medium">
            <strong className="text-blue-600 block mb-1">{t('glossary_guide_title')}</strong>
            {t('glossary_guide_desc')}
          </p>
        </div>
        
        <div className="p-8 overflow-y-auto flex-1 space-y-3 custom-scrollbar">
          <div className="flex text-xs font-black text-slate-400 px-2 pb-3 uppercase tracking-widest border-b border-slate-100">
            <div className="flex-1">{t('glossary_source_label')}</div>
            <div className="flex-1 ml-4">{t('glossary_target_label')}</div>
            <div className="w-10"></div>
          </div>
          {glossary.map((item, i) => (
            <div key={i} className="flex gap-4 items-center group animate-slide-in">
              <input type="text" value={item.key} onChange={e => { const newG = [...glossary]; newG[i].key = e.target.value; setGlossary(newG); }} className="flex-1 bg-slate-50 border border-slate-200 rounded-2xl p-3 text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none transition-all font-medium" placeholder="..." />
              <input type="text" value={item.value} onChange={e => { const newG = [...glossary]; newG[i].value = e.target.value; setGlossary(newG); }} className="flex-1 bg-slate-50 border border-slate-200 rounded-2xl p-3 text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none transition-all font-medium" placeholder="..." />
              <button onClick={() => setGlossary(glossary.filter((_, idx) => idx !== i))} className="p-2 text-slate-300 hover:text-red-500 hover:bg-red-50 rounded-xl transition-all opacity-0 group-hover:opacity-100"><Trash2 className="w-5 h-5" /></button>
            </div>
          ))}
          <button onClick={() => setGlossary([...glossary, {key:'', value:''}])} className="w-full py-4 mt-4 border-2 border-dashed border-slate-200 text-slate-400 rounded-2xl hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-600 transition-all flex items-center justify-center gap-2 text-sm font-bold">
            <Plus className="w-5 h-5"/> {t('glossary_add_btn')}
          </button>
        </div>

        <div className="p-8 border-t border-slate-100 bg-slate-50/50 flex justify-end gap-4">
          <button onClick={onClose} className="px-6 py-3 rounded-2xl font-bold text-slate-500 hover:bg-slate-200 transition-all">{t('cancel')}</button>
          <button onClick={handleSave} disabled={loading} className="px-8 py-3 rounded-2xl font-bold text-white bg-indigo-600 hover:bg-indigo-700 transition-all flex items-center gap-2 shadow-xl shadow-indigo-200 active:scale-95 disabled:opacity-50">
            {loading ? <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <Save className="w-5 h-5" />}
            {t('save')}
          </button>
        </div>
      </div>
    </div>
  );
};

export const Layout: React.FC = () => {
  const { user, logout, token, isAdmin } = useAuth();
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const [showGlossary, setShowGlossary] = useState(false);

  const tabs = [
    { path: '/', label: t('tab_translator'), icon: <FileText className="w-4 h-4" /> },
    { path: '/history', label: t('tab_history'), icon: <Clock className="w-4 h-4" /> },
    { path: '/faq', label: t('tab_faq'), icon: <MessageCircle className="w-4 h-4" /> },
    ...(isAdmin ? [{ path: '/admin', label: t('admin_tab'), icon: <Shield className="w-4 h-4" /> }] : []),
  ];

  return (
    <div className="min-h-screen bg-slate-50 font-sans selection:bg-blue-100 selection:text-blue-900 flex flex-col relative">
      <GlossaryModal isOpen={showGlossary} onClose={() => setShowGlossary(false)} token={token} />
      
      {/* --- Premium Single Header --- */}
      <header className="sticky top-0 z-40 bg-white/80 backdrop-blur-xl border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-6 lg:px-8">
          <div className="flex justify-between items-center h-20">
            <div className="flex items-center gap-4">
              <div className="bg-linear-to-br from-blue-600 to-indigo-600 p-2.5 rounded-2xl shadow-lg shadow-blue-500/20 shrink-0">
                <BookOpen className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-black tracking-tight text-slate-800 leading-none mb-1">
                  {t('app_title')}
                </h1>
                <p className="text-[10px] font-black text-blue-600 uppercase tracking-widest">Platform</p>
              </div>
            </div>
            
            <div className="flex items-center gap-8">
              {/* Global Glossary Toggle */}
              <button 
                onClick={() => setShowGlossary(true)} 
                className="flex items-center gap-2 text-[10px] font-black text-slate-400 uppercase tracking-widest hover:text-indigo-600 transition-colors"
              >
                <BookOpen className="w-4 h-4" />
                {t('glossary_manage')}
              </button>

              <div className="h-6 w-px bg-slate-200 hidden md:block"></div>

              {/* Lang Switcher (Button Type) */}
              <div className="hidden md:flex gap-1 bg-slate-100 p-1 rounded-2xl border border-slate-200">
                {['ko', 'en', 'ja'].map((lng) => (
                  <button
                    key={lng}
                    onClick={() => i18n.changeLanguage(lng)}
                    className={clsx(
                      "px-4 py-1.5 rounded-xl text-[10px] font-black transition-all uppercase tracking-widest",
                      i18n.language === lng ? "bg-white text-blue-600 shadow-md" : "text-slate-400 hover:text-slate-600 hover:bg-white/50"
                    )}
                  >
                    {lng}
                  </button>
                ))}
              </div>

              <div className="h-6 w-px bg-slate-200 hidden md:block"></div>

              <div className="flex items-center gap-5">
                <div className="hidden sm:flex flex-col items-end">
                  <span className="text-[10px] font-black text-slate-400 uppercase tracking-tighter leading-none mb-1">Authenticated</span>
                  <span className="text-sm font-bold text-slate-700 leading-none">{user?.username}</span>
                </div>
                <button 
                  onClick={logout} 
                  className="p-3 bg-slate-100 hover:bg-red-50 text-slate-500 hover:text-red-600 rounded-2xl transition-all border border-slate-200 hover:border-red-100 group"
                  title={t('logout')}
                >
                  <LogOut className="w-5 h-5 transition-transform group-hover:translate-x-0.5" />
                </button>
              </div>
            </div>
          </div>
        </div>
        
        {/* Navigation Tabs Bar */}
        <div className="max-w-7xl mx-auto px-6 lg:px-8 border-t border-slate-100">
          <nav className="flex space-x-1 -mb-px">
            {tabs.map((tab) => {
              const isActive = location.pathname === tab.path;
              return (
                <Link
                  key={tab.path}
                  to={tab.path}
                  className={clsx(
                    "whitespace-nowrap py-4 px-6 border-b-2 font-bold text-xs uppercase tracking-widest flex items-center gap-2.5 transition-all",
                    isActive
                      ? "border-blue-600 text-blue-600"
                      : "border-transparent text-slate-400 hover:text-slate-600 hover:border-slate-300"
                  )}
                >
                  <span className={clsx("transition-transform", isActive && "scale-110")}>{tab.icon}</span>
                  {tab.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>
      
      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto px-6 lg:px-8 py-10 w-full flex-1 animate-fade-in">
        <Outlet />
      </main>
      
      {/* Global Footer */}
      <footer className="py-10 border-t border-slate-200/60 text-center">
        <p className="text-slate-300 text-[10px] font-black uppercase tracking-[0.2em]">
          Bubblecon PS Team
        </p>
      </footer>

      <HelpChatbot />
    </div>
  );
};
