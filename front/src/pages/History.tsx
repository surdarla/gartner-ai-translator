import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { useTranslation } from 'react-i18next';
import { History as HistoryIcon, Download, CheckCircle, AlertCircle, Loader2, FileText, Ban, Clock, Trash2, Filter } from 'lucide-react';
import clsx from 'clsx';

interface Job {
  job_id: string;
  timestamp: string;
  username: string;
  filename: string;
  provider: string;
  target_lang: string;
  status: string;
  output_path: string;
  file_size?: number;
  cost?: number;
}

export const History: React.FC = () => {
  const { token, isAdmin } = useAuth();
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [statusFilter, setStatusFilter] = useState<Set<string>>(new Set(['completed', 'processing', 'failed', 'cancelled', 'timeout']));
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const fetchHistory = async () => {
    try {
      const res = await axios.get('http://localhost:8000/history', {
        headers: { Authorization: `Bearer ${token}` }
      });
      setJobs(res.data);
    } catch (err) {
      console.error("Failed to fetch history:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (token) fetchHistory();
  }, [token]);

  const toggleStatus = (s: string) => {
    setStatusFilter(prev => {
      const next = new Set(prev);
      if (next.has(s)) next.delete(s);
      else next.add(s);
      return next;
    });
  };

  const deleteJob = async (jobId: string) => {
    if (!confirm(t('admin_delete_confirm'))) return;
    try {
      await axios.delete(`http://localhost:8000/admin/delete-job/${jobId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setJobs(prev => prev.filter(j => j.job_id !== jobId));
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  const filteredJobs = jobs.filter(job => {
    if (!statusFilter.has(job.status)) return false;
    if (dateFrom) {
      const jobDate = new Date(job.timestamp).toISOString().split('T')[0];
      if (jobDate < dateFrom) return false;
    }
    if (dateTo) {
      const jobDate = new Date(job.timestamp).toISOString().split('T')[0];
      if (jobDate > dateTo) return false;
    }
    return true;
  });

  const getStatusBadge = (status: string) => {
    const map: Record<string, { icon: React.ReactNode, cls: string, label: string }> = {
      completed: { icon: <CheckCircle className="w-3 h-3"/>, cls: "text-green-600 bg-green-50 border-green-100", label: t('status_completed') },
      processing: { icon: <Loader2 className="w-3 h-3 animate-spin"/>, cls: "text-blue-600 bg-blue-50 border-blue-100", label: t('status_processing') },
      failed: { icon: <AlertCircle className="w-3 h-3"/>, cls: "text-red-600 bg-red-50 border-red-100", label: t('status_failed') },
      cancelled: { icon: <Ban className="w-3 h-3"/>, cls: "text-amber-600 bg-amber-50 border-amber-100", label: t('status_cancelled') },
      timeout: { icon: <Clock className="w-3 h-3"/>, cls: "text-slate-600 bg-slate-50 border-slate-200", label: t('status_timeout') },
    };
    const s = map[status] || { icon: null, cls: "text-slate-400 bg-slate-50 border-slate-100", label: status };
    return (
      <span className={clsx("inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-black border shadow-sm whitespace-nowrap", s.cls)}>
        {s.icon} {s.label}
      </span>
    );
  };

  const statusOptions = [
    { key: 'completed', label: t('status_completed'), color: 'bg-green-500' },
    { key: 'processing', label: t('status_processing'), color: 'bg-blue-500' },
    { key: 'failed', label: t('status_failed'), color: 'bg-red-500' },
    { key: 'cancelled', label: t('status_cancelled'), color: 'bg-amber-500' },
    { key: 'timeout', label: t('status_timeout'), color: 'bg-slate-400' },
  ];

  return (
    <div className="max-w-7xl mx-auto space-y-8 pb-16 animate-fade-in px-4">
      <div className="bg-white rounded-[2.5rem] shadow-xl shadow-slate-200/50 border border-slate-100 overflow-hidden">
        <div className="p-8 border-b border-slate-50 flex flex-col md:flex-row md:items-center justify-between gap-6 bg-slate-50/30">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 bg-linear-to-br from-indigo-500 to-purple-600 rounded-2xl flex items-center justify-center text-white shadow-lg shadow-indigo-200 shrink-0">
              <HistoryIcon className="w-7 h-7" />
            </div>
            <div>
              <h2 className="text-3xl font-black text-slate-800 tracking-tight">{t('history_title')}</h2>
              <p className="text-slate-400 font-black uppercase tracking-widest text-[10px] mt-1">Management Archive</p>
            </div>
          </div>
          <div className="bg-white px-6 py-3 rounded-2xl border border-slate-200 shadow-sm shrink-0">
            <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest block mb-1">{t('history_filtered')}</span>
            <span className="text-xl font-black text-indigo-600 tabular-nums">{filteredJobs.length}<span className="text-slate-300 text-sm">/{jobs.length}</span></span>
          </div>
        </div>

        {/* Filters Bar */}
        <div className="px-8 py-5 border-b border-slate-50 bg-slate-50/20">
          <div className="flex flex-col md:flex-row gap-4 items-start md:items-center">
            <div className="flex items-center gap-2 shrink-0">
              <Filter className="w-4 h-4 text-slate-400" />
              <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">{t('history_filter_status')}</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {statusOptions.map(opt => (
                <button
                  key={opt.key}
                  onClick={() => toggleStatus(opt.key)}
                  className={clsx(
                    "inline-flex items-center gap-2 px-3 py-1.5 rounded-xl text-[10px] font-black border transition-all",
                    statusFilter.has(opt.key)
                      ? "bg-white border-slate-200 text-slate-700 shadow-sm"
                      : "bg-slate-100 border-transparent text-slate-400 line-through"
                  )}
                >
                  <div className={clsx("w-2 h-2 rounded-full", opt.color, !statusFilter.has(opt.key) && "opacity-30")}></div>
                  {opt.label}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-2 ml-auto">
              <input 
                type="date" 
                value={dateFrom} 
                onChange={e => setDateFrom(e.target.value)}
                className="text-[11px] font-bold text-slate-600 border border-slate-200 rounded-xl px-3 py-1.5 bg-white focus:ring-2 focus:ring-blue-500 outline-none"
              />
              <span className="text-slate-300 text-xs">~</span>
              <input 
                type="date" 
                value={dateTo} 
                onChange={e => setDateTo(e.target.value)}
                className="text-[11px] font-bold text-slate-600 border border-slate-200 rounded-xl px-3 py-1.5 bg-white focus:ring-2 focus:ring-blue-500 outline-none"
              />
            </div>
          </div>
        </div>

        <div className="overflow-hidden">
          {loading ? (
            <div className="py-32 flex flex-col justify-center items-center gap-4">
              <div className="relative">
                <div className="w-16 h-16 border-4 border-indigo-100 rounded-full"></div>
                <div className="w-16 h-16 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin absolute top-0"></div>
              </div>
              <p className="text-slate-400 font-black uppercase tracking-widest text-[10px]">Syncing Data...</p>
            </div>
          ) : filteredJobs.length === 0 ? (
            <div className="text-center py-32 space-y-4">
              <div className="w-20 h-20 bg-slate-50 rounded-full flex items-center justify-center mx-auto">
                <HistoryIcon className="w-10 h-10 text-slate-200" />
              </div>
              <p className="text-slate-400 font-bold text-lg">
                {t('history_empty')}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto scrollbar-thin scrollbar-thumb-slate-200 scrollbar-track-transparent">
              <table className="w-full text-left border-collapse min-w-[1000px]">
                <thead>
                  <tr className="bg-slate-50/50">
                    <th className="px-6 py-5 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] w-48">{t('history_date')}</th>
                    <th className="px-6 py-5 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">{t('history_filename')}</th>
                    <th className="px-6 py-5 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] w-24 text-center">{t('history_size')}</th>
                    <th className="px-6 py-5 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] w-32 text-center">{t('history_engine')}</th>
                    <th className="px-6 py-5 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] w-32 text-center">{t('history_status')}</th>
                    <th className="px-6 py-5 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] w-32 text-right">{t('history_cost')}</th>
                    <th className="px-6 py-5 text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] text-right w-48">{t('history_actions')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {filteredJobs.map((job) => (
                    <tr 
                      key={job.job_id} 
                      className={clsx(
                        "hover:bg-slate-50/80 transition-all group",
                        job.status === 'processing' && "cursor-pointer"
                      )}
                      onClick={() => {
                        if (job.status === 'processing') {
                          localStorage.setItem('activeJobId', job.job_id);
                          navigate('/');
                        }
                      }}
                    >
                      <td className="px-6 py-6 whitespace-nowrap text-[11px] font-bold text-slate-400 tabular-nums">
                        {new Date(job.timestamp).toLocaleString(i18n.language === 'ko' ? 'ko-KR' : i18n.language === 'ja' ? 'ja-JP' : 'en-US')}
                      </td>
                      <td className="px-6 py-6 min-w-[240px]">
                        <div className="flex items-center gap-3">
                          <div className="p-2 bg-slate-100 rounded-xl group-hover:bg-blue-100 group-hover:text-blue-600 transition-colors shrink-0">
                            <FileText className="w-4 h-4" />
                          </div>
                          <div className="flex flex-col min-w-0">
                            <span className="font-bold text-slate-700 text-sm truncate max-w-[300px]" title={job.filename}>
                              {job.filename}
                            </span>
                            <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest mt-0.5">{job.target_lang}</span>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-6 whitespace-nowrap text-center">
                        <span className="text-[10px] font-black text-slate-500 tabular-nums bg-slate-100 px-2 py-1 rounded-md">
                          {job.file_size 
                            ? (job.file_size > 1024 * 1024 
                                ? `${(job.file_size / (1024 * 1024)).toFixed(2)} MB` 
                                : `${(job.file_size / 1024).toFixed(1)} KB`)
                            : '-'}
                        </span>
                      </td>
                      <td className="px-6 py-6 text-center">
                        <span className="text-[10px] font-black text-slate-500 bg-white border border-slate-200 px-2.5 py-1 rounded-lg uppercase tracking-tight shadow-sm">
                          {job.provider}
                        </span>
                      </td>
                      <td className="px-6 py-6 text-center">
                        {getStatusBadge(job.status)}
                      </td>
                      <td className="px-6 py-6 text-right">
                        <span className="text-xs font-black text-indigo-600 tabular-nums">
                          ${job.cost?.toFixed(4) || "0.0000"}
                        </span>
                      </td>
                      <td className="px-6 py-6 text-right whitespace-nowrap">
                        <div className="flex items-center justify-end gap-2">
                          {job.status === 'completed' && job.output_path ? (
                            <a 
                              href={`http://localhost:8000/download/${job.job_id}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="inline-flex items-center gap-2 text-blue-600 hover:text-white hover:bg-blue-600 font-black text-[10px] uppercase tracking-widest bg-blue-50 px-4 py-2 rounded-xl border border-blue-100 transition-all hover:shadow-lg hover:shadow-blue-200 active:scale-95 whitespace-nowrap"
                            >
                              <Download className="w-3.5 h-3.5" /> {t('history_download')}
                            </a>
                          ) : (
                            <span className="text-slate-300 font-bold">-</span>
                          )}
                          {isAdmin && (
                            <button
                              onClick={(e) => { e.stopPropagation(); deleteJob(job.job_id); }}
                              className="p-2 text-slate-300 hover:text-red-600 hover:bg-red-50 rounded-xl transition-all"
                              title={t('admin_delete')}
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
