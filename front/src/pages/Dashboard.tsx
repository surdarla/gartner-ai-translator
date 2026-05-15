import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { UploadCloud, Settings, ChevronDown, CheckCircle, AlertCircle, FileText, Download, X, Play, Ban } from 'lucide-react';
import clsx from 'clsx';
import { useTranslation } from 'react-i18next';
import { getApiUrl, getWsUrl } from '../api';

export const Dashboard: React.FC = () => {
  const { t } = useTranslation();
  const { token } = useAuth();
  
  const [file, setFile] = useState<File | null>(null);
  const [restoredInfo, setRestoredInfo] = useState<{ name: string, size: number, provider: string } | null>(null);
  const [provider, setProvider] = useState('Free (Google Translator)');
  const [direction, setDirection] = useState('한국어 → English');
  const [apiKey, setApiKey] = useState('');
  const [systemInstruction, setSystemInstruction] = useState('Translate maintaining a professional business tone.');
  const [dragging, setDragging] = useState(false);
  const [debugMode, setDebugMode] = useState(false);

  const [jobId, setJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState({ current: 0, total: 1, text: '', cost: 0.0 });
  const [logs, setLogs] = useState<{ text: string, category: string | null }[]>([]);
  const [status, setStatus] = useState<'idle' | 'processing' | 'completed' | 'failed' | 'cancelled'>('idle');
  const [eta, setEta] = useState<number | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const startTimeRef = useRef<number | null>(null);

  // Restore job on mount
  useEffect(() => {
    const savedJobId = localStorage.getItem('activeJobId');
    if (savedJobId && status === 'idle') {
      axios.get(getApiUrl(`/active-job/${savedJobId}`), {
        headers: { Authorization: `Bearer ${token}` }
      }).then(res => {
        if (res.data.status === 'processing') {
          setJobId(savedJobId);
          setStatus('processing');
          setRestoredInfo({ 
            name: res.data.filename, 
            size: res.data.file_size, 
            provider: res.data.provider 
          });
          setProgress({ current: res.data.current, total: res.data.total, text: res.data.text, cost: res.data.cost || 0 });
          const initialLogs = (res.data.logs || []).map((l: string) => ({
            text: l,
            category: (l.startsWith('[') && l.includes(']')) ? l.split(']')[0].slice(1) : null
          }));
          setLogs(initialLogs);
        } else if (res.data.status === 'completed') {
           setJobId(savedJobId);
           setStatus('completed');
           setRestoredInfo({ 
            name: res.data.filename, 
            size: res.data.file_size, 
            provider: res.data.provider 
          });
           setProgress({ current: 1, total: 1, text: '완료!', cost: res.data.cost || 0 });
        }
      }).catch(() => localStorage.removeItem('activeJobId'));
    }
  }, [token]);

  useEffect(() => {
    if (jobId && status === 'processing') {
      const ws = new WebSocket(getWsUrl(`/ws/progress/${jobId}`));
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        setProgress(data);
        if (data.log) {
          setLogs((prev) => {
            if (data.category) {
              const existingIdx = prev.findIndex(l => l.category === data.category);
              if (existingIdx > -1) {
                const updated = [...prev];
                updated[existingIdx] = { text: data.log, category: data.category };
                return updated;
              }
            }
            return [...prev, { text: data.log, category: data.category || null }];
          });
        }
        if (data.current > 0 && data.total > 0 && startTimeRef.current) {
          const elapsed = (Date.now() - startTimeRef.current) / 1000;
          setEta((elapsed / data.current) * (data.total - data.current));
        }
        if (data.text === '완료!') setStatus('completed');
        if (data.text === '오류 발생') setStatus('failed');
        if (data.text === '취소됨') setStatus('cancelled');
      };
      wsRef.current = ws;
      return () => ws.close();
    }
  }, [jobId, status]);

  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  const handleDrag = (e: React.DragEvent) => { e.preventDefault(); e.stopPropagation(); setDragging(e.type === 'dragenter' || e.type === 'dragover'); };
  const handleDrop = (e: React.DragEvent) => { e.preventDefault(); e.stopPropagation(); setDragging(false); if (e.dataTransfer.files?.[0]) setFile(e.dataTransfer.files[0]); };

  const startTranslation = async (testMode: boolean = false) => {
    if (!file) return alert(t('upload_title'));
    if (provider !== 'Free (Google Translator)' && !apiKey) return alert(t('api_key_placeholder'));
    
    setStatus('processing'); setLogs([]); setEta(null); startTimeRef.current = Date.now();
    setRestoredInfo(null);
    setProgress({ current: 0, total: 1, text: 'Uploading to storage...', cost: 0.0 });

    try {
      // 1. Vercel Blob에 파일 업로드 (50MB 제한 없음!)
      const { upload } = await import('@vercel/blob/client');
      
      // 파일명 정제 강화 (영문, 숫자만 남기고 나머지 제거)
      const extension = file.name.split('.').pop() || 'bin';
      const cleanBaseName = file.name
        .split('.')[0]
        .replace(/[^a-zA-Z0-9]/g, '') // 영문 숫자 외 전멸
        .substring(0, 20); // 너무 길면 자름
      
      // 1. 서버에서 직접 업로드 토큰 받아오기 (리다이렉트 방지)
      const tokenResponse = await fetch('/api/upload', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          type: 'blob.generate-client-token', 
          payload: { pathname: safePath, callbackUrl: window.location.origin + '/api/upload' } 
        })
      });

      if (!tokenResponse.ok) {
        const errorData = await tokenResponse.json();
        throw new Error(`토큰 발급 실패: ${errorData.message || '로그인을 확인하세요'}`);
      }

      const { clientToken } = await tokenResponse.json();

      // 2. Vercel 스토리지로 직접 PUT 업로드 (SDK 우회)
      const uploadUrl = `https://blob.vercel-storage.com/${safePath}`;
      const uploadResponse = await fetch(uploadUrl, {
        method: 'PUT',
        body: file,
        headers: {
          'Authorization': `Bearer ${clientToken}`,
          'x-api-version': '2023-01-30',
        },
      });

      if (!uploadResponse.ok) {
        const errorText = await uploadResponse.text();
        throw new Error(`업로드 실패: ${errorText}`);
      }

      const blob = await uploadResponse.json();
      const publicUrl = blob.url;

      setProgress({ current: 0, total: 1, text: 'Triggering translation...', cost: 0.0 });

      // 3. 백엔드에는 파일 본문 대신 URL 전달
      const formData = new FormData();
      formData.append('file_url', publicUrl);
      formData.append('filename', file.name);
      formData.append('provider', provider.split(' ')[0]);
      formData.append('direction', direction);
      formData.append('api_key', apiKey);
      formData.append('system_instruction', systemInstruction);
      formData.append('test_mode', String(testMode));

      const res = await axios.post(getApiUrl('/translate'), formData, { 
        headers: { Authorization: `Bearer ${token}` } 
      });
      
      setJobId(res.data.job_id); 
      localStorage.setItem('activeJobId', res.data.job_id);
    } catch (err: any) { 
      console.error(err);
      const errorMessage = err.response?.data?.detail || err.message || 'Unknown error';
      setStatus('failed'); 
      setProgress(p => ({ ...p, text: `실패: ${errorMessage}` }));
    }
  };

  const getDirectionOptions = () => [
    { value: "한국어 → English", label: t('dir_ko_en', 'KOR → ENG') },
    { value: "한국어 → 日本語", label: t('dir_ko_ja', 'KOR → JPN') },
    { value: "English → 한국어", label: t('dir_en_ko', 'ENG → KOR') },
    { value: "日本語 → 한국어", label: t('dir_ja_ko', 'JPN → KOR') }
  ];

  const downloadResult = () => {
    if (status === 'completed' && progress.text === '완료!') {
      // The backend should send the public URL in a way we can access it.
      // For now, let's assume if it's completed, we can get the path from active job.
      axios.get(getApiUrl(`/active-job/${jobId}`), {
        headers: { Authorization: `Bearer ${token}` }
      }).then(res => {
        if (res.data.output_path) {
          window.open(res.data.output_path, '_blank');
        }
      });
    }
  };

  const cancelJob = async () => {
    if (!jobId) return;
    try {
      await axios.post(getApiUrl(`/cancel/${jobId}`), {}, { headers: { Authorization: `Bearer ${token}` } });
      setStatus('cancelled');
      localStorage.removeItem('activeJobId');
    } catch (err) {
      console.error('Cancel failed:', err);
    }
  };

  return (
    <div className="w-full grid grid-cols-1 lg:grid-cols-12 gap-10">
      
      {/* --- Sidebar (Controls) --- */}
      <aside className="lg:col-span-4 space-y-8">
        <div className="bg-white rounded-[2.5rem] shadow-xl shadow-slate-200/50 border border-slate-100 p-8">
          <h3 className="text-xl font-black mb-8 flex items-center gap-3 text-slate-800">
            <Settings className="w-6 h-6 text-blue-500"/>
            {t('config_title')}
          </h3>
          
          <div className="space-y-6">
            <div className="space-y-2">
              <label className="text-xs font-black text-slate-400 uppercase tracking-widest ml-1">{t('ai_provider')}</label>
              <div className="relative">
                <select value={provider} onChange={e => setProvider(e.target.value)} className="w-full appearance-none bg-slate-50 border border-slate-200 text-slate-800 text-sm font-bold rounded-2xl p-4 pr-10 focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 outline-none transition-all">
                  <option>Free (Google Translator)</option>
                  <option>Gemini</option>
                  <option>Claude</option>
                  <option>Upstage</option>
                </select>
                <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400 pointer-events-none" />
              </div>
            </div>

            {provider !== 'Free (Google Translator)' && (
              <div className="space-y-2 animate-fade-in">
                <label className="text-xs font-black text-slate-400 uppercase tracking-widest ml-1">{t('api_key')}</label>
                <input type="password" value={apiKey} onChange={e => setApiKey(e.target.value)} className="w-full bg-slate-50 border border-slate-200 text-slate-800 text-sm font-bold rounded-2xl p-4 focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 outline-none transition-all" placeholder={t('api_key_placeholder')} />
              </div>
            )}

            <div className="space-y-2">
              <label className="text-xs font-black text-slate-400 uppercase tracking-widest ml-1">{t('target_lang')}</label>
              <div className="relative">
                <select value={direction} onChange={e => setDirection(e.target.value)} className="w-full appearance-none bg-slate-50 border border-slate-200 text-slate-800 text-sm font-bold rounded-2xl p-4 pr-10 focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 outline-none transition-all">
                  {getDirectionOptions().map(opt => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
                <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400 pointer-events-none" />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-black text-slate-400 uppercase tracking-widest ml-1">{t('sys_instruction')}</label>
              <textarea rows={4} value={systemInstruction} onChange={e => setSystemInstruction(e.target.value)} className="w-full bg-slate-50 border border-slate-200 text-slate-800 text-sm font-bold rounded-2xl p-4 focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 outline-none transition-all custom-scrollbar" />
            </div>

            <div className="flex items-center justify-between bg-slate-50 p-4 rounded-2xl border border-slate-100">
              <span className="text-sm font-bold text-slate-600">{t('debug_mode')}</span>
              <button onClick={() => setDebugMode(!debugMode)} className={clsx("relative inline-flex h-7 w-12 items-center rounded-full transition-all focus:outline-none", debugMode ? "bg-indigo-600 shadow-lg shadow-indigo-200" : "bg-slate-300")}>
                <span className={clsx("inline-block h-5 w-5 transform rounded-full bg-white shadow-sm transition-transform", debugMode ? "translate-x-6" : "translate-x-1")} />
              </button>
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="bg-white rounded-3xl p-8 border border-slate-100 shadow-sm text-center">
            <h4 className="text-xs font-black text-slate-400 uppercase tracking-[0.2em] mb-4">{t('contact_title', 'Contact')}</h4>
            <p className="text-slate-600 font-bold text-sm leading-relaxed mb-4">
              {t('contact_desc', 'For any inquiries, please contact us via email.')}
            </p>
            <a href="mailto:js222@bubblecon.io" className="text-indigo-600 font-black hover:underline tracking-tight">
              js222@bubblecon.io
            </a>
          </div>
        </div>
      </aside>

      {/* --- Main Area (Uploader & Progress) --- */}
      <div className="lg:col-span-8 space-y-8">
        
        {/* Guide Alert */}
        <div className="bg-linear-to-br from-blue-50 to-indigo-50 border border-blue-100 rounded-[2.5rem] p-8 shadow-sm">
          <h4 className="text-lg font-black text-blue-900 flex items-center gap-3 mb-6">
            <AlertCircle className="w-6 h-6 text-blue-600"/>
            {t('guide_title')}
          </h4>
          <ul className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[t('guide_pros'), t('guide_cons'), t('guide_warn1'), t('guide_warn2'), t('guide_warn3')].map((g, i) => (
              <li key={i} className="flex gap-3 text-sm text-blue-800/80 font-bold bg-white/40 p-4 rounded-2xl border border-blue-200/50">
                <CheckCircle className="w-5 h-5 text-blue-500 shrink-0 mt-0.5" />
                {g}
              </li>
            ))}
          </ul>
        </div>

        {/* Uploader Box */}
        <div 
          className={clsx(
            "border-4 border-dashed rounded-[3rem] p-20 text-center transition-all relative overflow-hidden group",
            dragging ? "border-blue-500 bg-blue-50 scale-[0.99]" : "border-slate-200 bg-white hover:border-blue-300 hover:bg-slate-50/50",
            status !== 'idle' && status !== 'failed' && "opacity-50 pointer-events-none"
          )}
          onDragEnter={handleDrag} onDragLeave={handleDrag} onDragOver={handleDrag} onDrop={handleDrop}
          onClick={() => status === 'idle' && fileInputRef.current?.click()}
        >
          <input type="file" ref={fileInputRef} className="hidden" accept=".pdf,.pptx" onChange={e => setFile(e.target.files?.[0] || null)} />
          <div className={clsx(
            "w-24 h-24 rounded-full flex items-center justify-center mx-auto mb-8 transition-transform group-hover:scale-110",
            file ? "bg-blue-600 text-white shadow-xl shadow-blue-200" : "bg-slate-100 text-slate-400"
          )}>
            {file ? <FileText className="w-10 h-10" /> : <UploadCloud className="w-10 h-10" />}
          </div>
          <h4 className="text-2xl font-black text-slate-800 mb-3">
            {file ? file.name : t('upload_title')}
          </h4>
          <p className="text-slate-400 font-bold uppercase tracking-widest text-xs">
            {file ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : t('upload_supported')}
          </p>
        </div>

        {/* Action Buttons */}
        {status === 'idle' && (
          <div className="flex gap-6">
            <button 
              onClick={() => startTranslation(false)}
              className="flex-1 bg-linear-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-black py-5 rounded-4xl shadow-2xl shadow-blue-200 transition-all hover:-translate-y-1 active:scale-95 flex items-center justify-center gap-3 text-lg"
            >
              <Play className="w-6 h-6 fill-current" />
              {t('start_trans')}
            </button>
            <button 
              onClick={() => startTranslation(true)}
              className="flex-1 bg-white border-4 border-slate-100 hover:border-blue-100 text-slate-700 font-black py-5 rounded-4xl shadow-xl shadow-slate-200 transition-all hover:-translate-y-1 active:scale-95 flex items-center justify-center gap-3 text-lg"
            >
              <FileText className="w-6 h-6" />
              {t('test_run')}
            </button>
          </div>
        )}

        {/* Progress Section */}
        {status !== 'idle' && (
          <div className="bg-white rounded-[3rem] shadow-2xl shadow-slate-200/50 border border-slate-100 p-10 animate-fade-in">
            <div className="flex flex-col lg:flex-row items-center justify-between gap-8 mb-12">
              <div className="flex items-center gap-6 flex-1 min-w-0">
                <div className="bg-blue-500 p-5 rounded-4xl shadow-xl shadow-blue-100 shrink-0">
                  <FileText className="w-10 h-10 text-white" />
                </div>
                <div className="min-w-0">
                  <h3 className="text-2xl font-black text-slate-800 tracking-tight mb-1 truncate w-full" title={file?.name || restoredInfo?.name}>
                    {file?.name || restoredInfo?.name || 'File Info Missing'}
                  </h3>
                  <div className="flex items-center gap-3">
                    <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest bg-slate-50 px-3 py-1 rounded-full border border-slate-100 shrink-0">
                      {((file?.size || restoredInfo?.size || 0)) > 1024 * 1024 
                        ? `${(((file?.size || restoredInfo?.size || 0)) / (1024 * 1024)).toFixed(2)} MB` 
                        : `${(((file?.size || restoredInfo?.size || 0)) / 1024).toFixed(1)} KB`}
                    </span>
                    <span className="w-1.5 h-1.5 bg-slate-200 rounded-full shrink-0"></span>
                    <span className="text-[10px] font-black text-blue-600 uppercase tracking-widest bg-blue-50 px-3 py-1 rounded-full border border-blue-100 shrink-0">
                      {restoredInfo?.provider || provider}
                    </span>
                  </div>
                </div>
              </div>
              
              <div className="flex items-center gap-10 shrink-0 border-l border-slate-100 pl-10">
                <div className="text-right min-w-[100px]">
                  <p className="text-[9px] font-black text-slate-400 uppercase tracking-[0.2em] mb-1 leading-none">Estimated Cost</p>
                  <p className="text-2xl font-black text-indigo-600 tabular-nums leading-none">${progress.cost.toFixed(4)}</p>
                </div>
                
                <div className="flex flex-col items-end gap-2 min-w-[120px]">
                  {eta !== null && status === 'processing' && (
                    <span className="text-[10px] font-black text-indigo-600 bg-indigo-50 px-3 py-1 rounded-full border border-indigo-100 whitespace-nowrap animate-pulse">
                      {t('eta')} {Math.round(eta)}{t('sec')}
                    </span>
                  )}
                  <span className="text-5xl font-black text-blue-600 tabular-nums leading-none tracking-tighter">
                    {Math.round((progress.current / Math.max(progress.total, 1)) * 100)}%
                  </span>
                </div>
              </div>
            </div>

            <div className="w-full bg-slate-100 rounded-full h-5 mb-10 overflow-hidden p-1 shadow-inner">
              <div 
                className="bg-linear-to-r from-blue-500 to-indigo-600 h-full rounded-full transition-all duration-500 ease-out shadow-lg" 
                style={{ width: `${(progress.current / Math.max(progress.total, 1)) * 100}%` }}
              ></div>
            </div>

            {status === 'processing' && (
              <div className="flex justify-center mb-8">
                <button 
                  onClick={cancelJob}
                  className="inline-flex items-center gap-2 bg-red-50 hover:bg-red-600 text-red-600 hover:text-white font-black text-sm px-8 py-3 rounded-2xl border border-red-200 hover:border-red-600 transition-all active:scale-95 shadow-sm"
                >
                  <Ban className="w-4 h-4" /> {t('cancel_translation')}
                </button>
              </div>
            )}

            {status === 'completed' && (
              <div className="flex flex-col items-center py-6 animate-bounce-in">
                <div className="w-24 h-24 bg-green-500 text-white rounded-[2.5rem] flex items-center justify-center mb-6 shadow-2xl shadow-green-200">
                  <CheckCircle className="w-12 h-12" />
                </div>
                <h4 className="text-3xl font-black text-slate-800 mb-8">{t('trans_done')}</h4>
                <div className="flex gap-4">
                  <button 
                    onClick={downloadResult}
                    className="bg-slate-900 hover:bg-black text-white font-black py-4 px-10 rounded-2xl shadow-2xl transition-all flex items-center gap-3 hover:-translate-y-1"
                  >
                    <Download className="w-6 h-6" />
                    {t('download_ready')}
                  </button>
                  <button onClick={() => { setStatus('idle'); setFile(null); setJobId(null); localStorage.removeItem('activeJobId'); }} className="p-4 bg-slate-100 hover:bg-slate-200 text-slate-600 rounded-2xl transition-all">
                    <X className="w-6 h-6" />
                  </button>
                </div>
              </div>
            )}

            {status === 'failed' && (
              <div className="flex flex-col items-center py-6">
                <div className="w-20 h-20 bg-red-100 text-red-600 rounded-3xl flex items-center justify-center mb-6">
                  <AlertCircle className="w-10 h-10" />
                </div>
                <h4 className="text-2xl font-black text-slate-800 mb-2">{t('trans_failed')}</h4>
                <p className="text-red-500 font-bold mb-6 px-10 text-center">{progress.text}</p>
                <button onClick={() => { setStatus('idle'); setFile(null); setJobId(null); localStorage.removeItem('activeJobId'); setProgress(p => ({ ...p, text: '' })); }} className="text-blue-600 font-bold hover:underline">{t('try_again')}</button>
              </div>
            )}

            {status === 'cancelled' && (
              <div className="flex flex-col items-center py-6">
                <div className="w-20 h-20 bg-amber-100 text-amber-600 rounded-3xl flex items-center justify-center mb-6">
                  <Ban className="w-10 h-10" />
                </div>
                <h4 className="text-2xl font-black text-slate-800 mb-4">{t('trans_cancelled')}</h4>
                <button onClick={() => { setStatus('idle'); setFile(null); setJobId(null); localStorage.removeItem('activeJobId'); }} className="text-blue-600 font-bold hover:underline">{t('try_again')}</button>
              </div>
            )}

            {/* Terminal Logs */}
            {(debugMode || status === 'failed') && (
              <div className="mt-10 bg-slate-950 rounded-4xl p-8 shadow-2xl border border-white/5 animate-slide-up">
                <div className="flex items-center gap-3 mb-6">
                  <div className="flex gap-1.5">
                    <div className="w-3 h-3 rounded-full bg-red-500/50"></div>
                    <div className="w-3 h-3 rounded-full bg-yellow-500/50"></div>
                    <div className="w-3 h-3 rounded-full bg-green-500/50"></div>
                  </div>
                  <span className="text-[10px] font-black text-slate-600 uppercase tracking-widest ml-2">process-stream</span>
                </div>
                <div className="h-64 overflow-y-auto font-mono text-xs text-blue-300/80 space-y-2 custom-scrollbar">
                  {logs.length === 0 && <span className="text-slate-700 italic">Waiting for logs...</span>}
                  {logs.map((log, i) => (
                    <div key={i} className={clsx(
                      "flex gap-4",
                      log.category ? "text-indigo-400 font-bold" : "text-blue-300/80"
                    )}>
                      <span className="text-slate-800 tabular-nums">{(i+1).toString().padStart(3, '0')}</span>
                      <span className="wrap-break-word">{log.text}</span>
                    </div>
                  ))}
                  <div ref={logEndRef} />
                </div>
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  );
};
